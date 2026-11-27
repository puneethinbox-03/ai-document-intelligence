import logging
import time

from app.core.logging import configure_logging
from app.services.outbox_dispatcher_service import (
    dispatch_pending_document_jobs,
    reconcile_dispatched_document_jobs,
)

logger = logging.getLogger(__name__)

# Dispatcher polling configuration.
OUTBOX_DISPATCH_INTERVAL_SECONDS = 5
OUTBOX_DISPATCH_BATCH_SIZE = 100

# Run reconciliation approximately once per minute.
OUTBOX_RECONCILIATION_INTERVAL_CYCLES = 12


def run_outbox_dispatcher() -> None:
    """
    Periodically dispatch and reconcile document-processing jobs.

    This process is independent of the document worker.

    Responsibilities:
    - Dispatch pending outbox records from PostgreSQL to Redis.
    - Reconcile previously dispatched records against Redis.
    - Recover queued jobs whose Redis delivery is missing or terminal.
    - Continue running when temporary infrastructure failures occur.

    Document content and file paths are never handled here.
    """

    logger.info(
        "Outbox dispatcher started",
        extra={
            "event": "outbox_dispatcher_started",
        },
    )

    cycles_since_reconciliation = 0

    while True:
        try:
            result = dispatch_pending_document_jobs(
                batch_size=OUTBOX_DISPATCH_BATCH_SIZE,
            )

            if result["claimed"] > 0:
                logger.info(
                    (
                        "Outbox dispatch cycle completed: "
                        f"claimed={result['claimed']}, "
                        f"dispatched={result['dispatched']}, "
                        f"failed={result['failed']}, "
                        f"stale={result['stale']}"
                    ),
                    extra={
                        "event": "outbox_dispatch_cycle_completed",
                    },
                )

        except Exception as exc:
            # Do not log exception messages; they may contain
            # connection details or other sensitive information.
            logger.error(
                "Outbox dispatch cycle failed",
                extra={
                    "event": "outbox_dispatch_cycle_failed",
                    "exception_type": type(exc).__name__,
                },
            )

        cycles_since_reconciliation += 1

        if (
            cycles_since_reconciliation
            >= OUTBOX_RECONCILIATION_INTERVAL_CYCLES
        ):
            try:
                result = reconcile_dispatched_document_jobs(
                    batch_size=OUTBOX_DISPATCH_BATCH_SIZE,
                )

                if result["claimed"] > 0:
                    logger.info(
                        (
                            "Outbox reconciliation cycle completed: "
                            f"claimed={result['claimed']}, "
                            f"reopened={result['reopened']}, "
                            f"active={result['active']}, "
                            f"unverified={result['unverified']}, "
                            f"stale={result['stale']}"
                        ),
                        extra={
                            "event": "outbox_reconciliation_cycle_completed",
                        },
                    )

            except Exception as exc:
                # Reconciliation failure must not stop dispatching.
                logger.error(
                    "Outbox reconciliation cycle failed",
                    extra={
                        "event": "outbox_reconciliation_cycle_failed",
                        "exception_type": type(exc).__name__,
                    },
                )

            finally:
                cycles_since_reconciliation = 0

        try:
            time.sleep(OUTBOX_DISPATCH_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.info(
                "Outbox dispatcher stopped",
                extra={
                    "event": "outbox_dispatcher_stopped",
                },
            )
            break


def main() -> None:
    configure_logging()
    run_outbox_dispatcher()


if __name__ == "__main__":
    main()
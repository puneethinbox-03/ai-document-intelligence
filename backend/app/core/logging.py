
import json
import logging
import sys

from datetime import datetime, timezone

from app.core.config import settings
from app.middleware.request_id import request_id_context


# ------------------------------------------------------------
# Structured JSON formatter
# ------------------------------------------------------------

class StructuredFormatter(logging.Formatter):
    """
    Format log records as structured JSON.

    Supported context fields:
        - event
        - request_id
        - user_id

    Sensitive document contents, prompts, responses,
    credentials, and tokens must never be logged.
    """

    CONTEXT_FIELDS = (
        "event",
        "request_id",
        "user_id",
    )

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(
            record.created,
            tz=timezone.utc,
        ).isoformat(timespec="milliseconds")

        log_entry = {
            "timestamp": timestamp.replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Automatically attach the active HTTP request ID.
        request_id = request_id_context.get()

        if request_id is not None:
            log_entry["request_id"] = request_id

        # Add other approved contextual fields when available.
        for field in self.CONTEXT_FIELDS:
            if field == "request_id":
                continue

            value = getattr(record, field, None)

            if value is not None:
                log_entry[field] = value

        # Record exception type without exposing potentially
        # sensitive exception messages.
        if record.exc_info and record.exc_info[0]:
            log_entry["exception_type"] = (
                record.exc_info[0].__name__
            )

        return json.dumps(
            log_entry,
            ensure_ascii=False,
            default=str,
        )


# ------------------------------------------------------------
# Centralized logging configuration
# ------------------------------------------------------------

def configure_logging() -> None:
    """
    Configure application-wide structured logging.

    Uses the log level from centralized application settings.
    """

    root_logger = logging.getLogger()

    log_level = getattr(
        logging,
        settings.log_level,
    )

    root_logger.setLevel(log_level)

    # Replace existing root handlers to avoid duplicate
    # log output from multiple configurations.
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(
        StructuredFormatter()
    )

    root_logger.addHandler(handler)


# ------------------------------------------------------------
# Logger factory
# ------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger for an application module.
    """

    return logging.getLogger(name)

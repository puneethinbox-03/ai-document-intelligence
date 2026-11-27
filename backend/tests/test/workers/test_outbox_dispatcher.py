
import logging

import pytest

from app.workers import run_outbox_dispatcher


def test_dispatcher_calls_dispatcher_with_expected_batch_size(
    monkeypatch,
):
    dispatch_calls = []
    sleep_calls = []

    def mock_dispatch(**kwargs):
        dispatch_calls.append(kwargs)

        return {
            "claimed": 1,
            "dispatched": 1,
            "failed": 0,
            "stale": 0,
        }

    def stop_after_one_cycle(seconds):
        sleep_calls.append(seconds)
        raise KeyboardInterrupt

    monkeypatch.setattr(
        run_outbox_dispatcher,
        "dispatch_pending_document_jobs",
        mock_dispatch,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher.time,
        "sleep",
        stop_after_one_cycle,
    )

    run_outbox_dispatcher.run_outbox_dispatcher()

    assert dispatch_calls == [
        {"batch_size": 100},
    ]

    assert sleep_calls == [5]


def test_dispatcher_repeats_polling_cycles(monkeypatch):
    dispatch_calls = []
    sleep_calls = []

    def mock_dispatch(**kwargs):
        dispatch_calls.append(kwargs)

        return {
            "claimed": 0,
            "dispatched": 0,
            "failed": 0,
            "stale": 0,
        }

    def stop_after_two_cycles(seconds):
        sleep_calls.append(seconds)

        if len(sleep_calls) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(
        run_outbox_dispatcher,
        "dispatch_pending_document_jobs",
        mock_dispatch,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher.time,
        "sleep",
        stop_after_two_cycles,
    )

    run_outbox_dispatcher.run_outbox_dispatcher()

    assert len(dispatch_calls) == 2
    assert sleep_calls == [5, 5]


def test_dispatcher_continues_after_dispatch_failure(
    monkeypatch,
    caplog,
):
    dispatch_calls = []
    sleep_calls = []

    def mock_dispatch(**kwargs):
        dispatch_calls.append(kwargs)

        if len(dispatch_calls) == 1:
            raise RuntimeError(
                "Sensitive Redis connection details"
            )

        return {
            "claimed": 1,
            "dispatched": 1,
            "failed": 0,
            "stale": 0,
        }

    def stop_after_two_cycles(seconds):
        sleep_calls.append(seconds)

        if len(sleep_calls) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(
        run_outbox_dispatcher,
        "dispatch_pending_document_jobs",
        mock_dispatch,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher.time,
        "sleep",
        stop_after_two_cycles,
    )

    with caplog.at_level(logging.ERROR):
        run_outbox_dispatcher.run_outbox_dispatcher()

    assert len(dispatch_calls) == 2

    failure_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None)
        == "outbox_dispatch_cycle_failed"
    ]

    assert len(failure_records) == 1
    assert failure_records[0].exception_type == "RuntimeError"

    # The underlying exception message must not be logged.
    assert "Sensitive Redis connection details" not in caplog.text


def test_dispatcher_logs_start_and_graceful_shutdown(
    monkeypatch,
    caplog,
):
    def mock_dispatch(**kwargs):
        return {
            "claimed": 0,
            "dispatched": 0,
            "failed": 0,
            "stale": 0,
        }

    def stop_immediately(seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        run_outbox_dispatcher,
        "dispatch_pending_document_jobs",
        mock_dispatch,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher.time,
        "sleep",
        stop_immediately,
    )

    with caplog.at_level(logging.INFO):
        run_outbox_dispatcher.run_outbox_dispatcher()

    events = [
        getattr(record, "event", None)
        for record in caplog.records
    ]

    assert "outbox_dispatcher_started" in events
    assert "outbox_dispatcher_stopped" in events

def test_dispatcher_runs_reconciliation_after_configured_cycles(
    monkeypatch,
):
    dispatch_calls = []
    reconciliation_calls = []
    sleep_calls = []

    def mock_dispatch(**kwargs):
        dispatch_calls.append(kwargs)

        return {
            "claimed": 0,
            "dispatched": 0,
            "failed": 0,
            "stale": 0,
        }

    def mock_reconciliation(**kwargs):
        reconciliation_calls.append(kwargs)

        return {
            "claimed": 1,
            "reopened": 1,
            "active": 0,
            "unverified": 0,
            "stale": 0,
        }

    def stop_after_two_cycles(seconds):
        sleep_calls.append(seconds)

        if len(sleep_calls) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(
        run_outbox_dispatcher,
        "OUTBOX_RECONCILIATION_INTERVAL_CYCLES",
        2,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher,
        "dispatch_pending_document_jobs",
        mock_dispatch,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher,
        "reconcile_dispatched_document_jobs",
        mock_reconciliation,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher.time,
        "sleep",
        stop_after_two_cycles,
    )

    run_outbox_dispatcher.run_outbox_dispatcher()

    assert len(dispatch_calls) == 2
    assert reconciliation_calls == [
        {"batch_size": 100},
    ]
    assert sleep_calls == [5, 5]


def test_dispatcher_continues_after_reconciliation_failure(
    monkeypatch,
    caplog,
):
    dispatch_calls = []
    reconciliation_calls = []
    sleep_calls = []

    def mock_dispatch(**kwargs):
        dispatch_calls.append(kwargs)

        return {
            "claimed": 0,
            "dispatched": 0,
            "failed": 0,
            "stale": 0,
        }

    def mock_reconciliation(**kwargs):
        reconciliation_calls.append(kwargs)

        if len(reconciliation_calls) == 1:
            raise RuntimeError(
                "Sensitive reconciliation connection details"
            )

        return {
            "claimed": 0,
            "reopened": 0,
            "active": 0,
            "unverified": 0,
            "stale": 0,
        }

    def stop_after_two_cycles(seconds):
        sleep_calls.append(seconds)

        if len(sleep_calls) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(
        run_outbox_dispatcher,
        "OUTBOX_RECONCILIATION_INTERVAL_CYCLES",
        1,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher,
        "dispatch_pending_document_jobs",
        mock_dispatch,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher,
        "reconcile_dispatched_document_jobs",
        mock_reconciliation,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher.time,
        "sleep",
        stop_after_two_cycles,
    )

    with caplog.at_level(logging.ERROR):
        run_outbox_dispatcher.run_outbox_dispatcher()

    assert len(dispatch_calls) == 2
    assert len(reconciliation_calls) == 2

    failure_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None)
        == "outbox_reconciliation_cycle_failed"
    ]

    assert len(failure_records) == 1
    assert failure_records[0].exception_type == "RuntimeError"

    # The underlying exception message must never be logged.
    assert (
        "Sensitive reconciliation connection details"
        not in caplog.text
    )


def test_dispatcher_does_not_reconcile_before_interval(
    monkeypatch,
):
    reconciliation_calls = []
    sleep_calls = []

    def mock_dispatch(**kwargs):
        return {
            "claimed": 0,
            "dispatched": 0,
            "failed": 0,
            "stale": 0,
        }

    def mock_reconciliation(**kwargs):
        reconciliation_calls.append(kwargs)

        return {
            "claimed": 0,
            "reopened": 0,
            "active": 0,
            "unverified": 0,
            "stale": 0,
        }

    def stop_after_two_cycles(seconds):
        sleep_calls.append(seconds)

        if len(sleep_calls) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(
        run_outbox_dispatcher,
        "OUTBOX_RECONCILIATION_INTERVAL_CYCLES",
        3,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher,
        "dispatch_pending_document_jobs",
        mock_dispatch,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher,
        "reconcile_dispatched_document_jobs",
        mock_reconciliation,
    )
    monkeypatch.setattr(
        run_outbox_dispatcher.time,
        "sleep",
        stop_after_two_cycles,
    )

    run_outbox_dispatcher.run_outbox_dispatcher()

    assert reconciliation_calls == []
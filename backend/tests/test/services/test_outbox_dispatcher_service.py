from uuid import uuid4

import pytest

import app.services.outbox_dispatcher_service as dispatcher


def make_claimed_record():
    return {
        "outbox_id": uuid4(),
        "processing_job_id": uuid4(),
        "dispatch_id": uuid4(),
        "lease_token": uuid4(),
        "delivery_attempts": 1,
    }


def test_dispatch_success_marks_record_dispatched(monkeypatch):
    record = make_claimed_record()
    enqueue_calls = []
    mark_calls = []

    monkeypatch.setattr(
        dispatcher,
        "_claim_pending_outbox_records",
        lambda *args, **kwargs: [record],
    )

    def fake_enqueue(processing_job_id, *, dispatch_id):
        enqueue_calls.append((processing_job_id, dispatch_id))

    def fake_mark(session_factory, *, outbox_id, lease_token):
        mark_calls.append((outbox_id, lease_token))
        return True

    monkeypatch.setattr(
        dispatcher,
        "_mark_outbox_dispatched",
        fake_mark,
    )

    monkeypatch.setattr(
        dispatcher,
        "_schedule_outbox_delivery_retry",
        lambda *args, **kwargs: pytest.fail(
            "Successful delivery must not schedule a retry"
        ),
    )

    result = dispatcher.dispatch_pending_document_jobs(
        session_factory=object(),
        enqueue_func=fake_enqueue,
    )

    assert result == {
        "claimed": 1,
        "dispatched": 1,
        "failed": 0,
        "stale": 0,
    }

    assert enqueue_calls == [
        (record["processing_job_id"], record["dispatch_id"])
    ]

    assert mark_calls == [
        (record["outbox_id"], record["lease_token"])
    ]


def test_dispatch_failure_schedules_retry(monkeypatch):
    record = make_claimed_record()
    retry_calls = []

    monkeypatch.setattr(
        dispatcher,
        "_claim_pending_outbox_records",
        lambda *args, **kwargs: [record],
    )

    def fake_enqueue(*args, **kwargs):
        raise RuntimeError("Private Redis connection detail")

    def fake_retry(
        session_factory,
        *,
        outbox_id,
        lease_token,
        delivery_attempts,
    ):
        retry_calls.append(
            (outbox_id, lease_token, delivery_attempts)
        )
        return True

    monkeypatch.setattr(
        dispatcher,
        "_schedule_outbox_delivery_retry",
        fake_retry,
    )

    monkeypatch.setattr(
        dispatcher,
        "_mark_outbox_dispatched",
        lambda *args, **kwargs: pytest.fail(
            "Failed delivery must not be marked dispatched"
        ),
    )

    result = dispatcher.dispatch_pending_document_jobs(
        session_factory=object(),
        enqueue_func=fake_enqueue,
    )

    assert result == {
        "claimed": 1,
        "dispatched": 0,
        "failed": 1,
        "stale": 0,
    }

    assert retry_calls == [
        (
            record["outbox_id"],
            record["lease_token"],
            record["delivery_attempts"],
        )
    ]


def test_dispatch_failure_with_lost_lease_is_stale(monkeypatch):
    record = make_claimed_record()

    monkeypatch.setattr(
        dispatcher,
        "_claim_pending_outbox_records",
        lambda *args, **kwargs: [record],
    )

    monkeypatch.setattr(
        dispatcher,
        "_schedule_outbox_delivery_retry",
        lambda *args, **kwargs: False,
    )

    result = dispatcher.dispatch_pending_document_jobs(
        session_factory=object(),
        enqueue_func=lambda *args, **kwargs: (
            (_ for _ in ()).throw(RuntimeError("Redis unavailable"))
        ),
    )

    assert result == {
        "claimed": 1,
        "dispatched": 0,
        "failed": 0,
        "stale": 1,
    }


def test_successful_delivery_with_lost_lease_is_stale(monkeypatch):
    record = make_claimed_record()

    monkeypatch.setattr(
        dispatcher,
        "_claim_pending_outbox_records",
        lambda *args, **kwargs: [record],
    )

    monkeypatch.setattr(
        dispatcher,
        "_mark_outbox_dispatched",
        lambda *args, **kwargs: False,
    )

    result = dispatcher.dispatch_pending_document_jobs(
        session_factory=object(),
        enqueue_func=lambda *args, **kwargs: object(),
    )

    assert result == {
        "claimed": 1,
        "dispatched": 0,
        "failed": 0,
        "stale": 1,
    }


def test_dispatch_passes_batch_size_to_claim(monkeypatch):
    claim_calls = []

    def fake_claim(session_factory, *, batch_size):
        claim_calls.append(batch_size)
        return []

    monkeypatch.setattr(
        dispatcher,
        "_claim_pending_outbox_records",
        fake_claim,
    )

    result = dispatcher.dispatch_pending_document_jobs(
        batch_size=25,
        session_factory=object(),
        enqueue_func=lambda *args, **kwargs: None,
    )

    assert claim_calls == [25]
    assert result == {
        "claimed": 0,
        "dispatched": 0,
        "failed": 0,
        "stale": 0,
    }


@pytest.mark.parametrize(
    "batch_size",
    [0, -1, 101, True, False, 1.5, "10", None],
)
def test_dispatch_rejects_invalid_batch_size(batch_size):
    with pytest.raises(ValueError):
        dispatcher.dispatch_pending_document_jobs(
            batch_size=batch_size,
            session_factory=object(),
            enqueue_func=lambda *args, **kwargs: None,
        )


@pytest.mark.parametrize(
    ("attempts", "expected_delay"),
    [
        (1, 30),
        (2, 120),
        (3, 300),
        (4, 300),
        (10, 300),
    ],
)
def test_outbox_retry_backoff_is_bounded(
    attempts,
    expected_delay,
):
    assert dispatcher._get_retry_delay(attempts) == expected_delay


def test_dispatch_uses_only_processing_and_dispatch_ids(monkeypatch):
    record = make_claimed_record()
    received = []

    monkeypatch.setattr(
        dispatcher,
        "_claim_pending_outbox_records",
        lambda *args, **kwargs: [record],
    )

    def fake_enqueue(processing_job_id, *, dispatch_id):
        received.append(
            {
                "processing_job_id": processing_job_id,
                "dispatch_id": dispatch_id,
            }
        )

    monkeypatch.setattr(
        dispatcher,
        "_mark_outbox_dispatched",
        lambda *args, **kwargs: True,
    )

    dispatcher.dispatch_pending_document_jobs(
        session_factory=object(),
        enqueue_func=fake_enqueue,
    )

    assert received == [
        {
            "processing_job_id": record["processing_job_id"],
            "dispatch_id": record["dispatch_id"],
        }
    ]

    assert set(received[0]) == {
        "processing_job_id",
        "dispatch_id",
    }

def test_reconciliation_reopens_missing_redis_job(monkeypatch):
    record = make_claimed_record()
    reopen_calls = []
    release_calls = []

    monkeypatch.setattr(
        dispatcher,
        "_claim_dispatched_outbox_records",
        lambda *args, **kwargs: [record],
    )

    def fake_reopen(session_factory, *, outbox_id, lease_token):
        reopen_calls.append((outbox_id, lease_token))
        return True

    monkeypatch.setattr(
        dispatcher,
        "_reopen_dispatched_outbox_record",
        fake_reopen,
    )

    monkeypatch.setattr(
        dispatcher,
        "_release_reconciliation_lease",
        lambda *args, **kwargs: (
            release_calls.append(args) or True
        ),
    )

    verify_calls = []

    def fake_verify(processing_job_id, dispatch_id):
        verify_calls.append((processing_job_id, dispatch_id))
        return dispatcher.DISPATCH_MISSING

    result = dispatcher.reconcile_dispatched_document_jobs(
        session_factory=object(),
        verify_func=fake_verify,
    )

    assert result == {
        "claimed": 1,
        "reopened": 1,
        "active": 0,
        "unverified": 0,
        "stale": 0,
    }

    assert verify_calls == [
        (record["processing_job_id"], record["dispatch_id"])
    ]

    assert reopen_calls == [
        (record["outbox_id"], record["lease_token"])
    ]

    assert release_calls == []


def test_reconciliation_reopens_terminal_redis_job(monkeypatch):
    record = make_claimed_record()

    monkeypatch.setattr(
        dispatcher,
        "_claim_dispatched_outbox_records",
        lambda *args, **kwargs: [record],
    )

    reopen_calls = []

    def fake_reopen(session_factory, *, outbox_id, lease_token):
        reopen_calls.append(outbox_id)
        return True

    monkeypatch.setattr(
        dispatcher,
        "_reopen_dispatched_outbox_record",
        fake_reopen,
    )

    result = dispatcher.reconcile_dispatched_document_jobs(
        session_factory=object(),
        verify_func=lambda *args: dispatcher.DISPATCH_TERMINAL,
    )

    assert result["reopened"] == 1
    assert reopen_calls == [record["outbox_id"]]


def test_reconciliation_keeps_active_redis_job_dispatched(monkeypatch):
    record = make_claimed_record()
    release_calls = []

    monkeypatch.setattr(
        dispatcher,
        "_claim_dispatched_outbox_records",
        lambda *args, **kwargs: [record],
    )

    monkeypatch.setattr(
        dispatcher,
        "_reopen_dispatched_outbox_record",
        lambda *args, **kwargs: pytest.fail(
            "An active Redis job must not be reopened"
        ),
    )

    def fake_release(session_factory, *, outbox_id, lease_token):
        release_calls.append((outbox_id, lease_token))
        return True

    monkeypatch.setattr(
        dispatcher,
        "_release_reconciliation_lease",
        fake_release,
    )

    result = dispatcher.reconcile_dispatched_document_jobs(
        session_factory=object(),
        verify_func=lambda *args: dispatcher.DISPATCH_ACTIVE,
    )

    assert result == {
        "claimed": 1,
        "reopened": 0,
        "active": 1,
        "unverified": 0,
        "stale": 0,
    }

    assert release_calls == [
        (record["outbox_id"], record["lease_token"])
    ]


@pytest.mark.parametrize(
    "verification_result",
    [
        dispatcher.DISPATCH_UNVERIFIED,
        "unexpected_status",
    ],
)
def test_reconciliation_does_not_reopen_unverified_job(
    monkeypatch,
    verification_result,
):
    record = make_claimed_record()
    release_calls = []

    monkeypatch.setattr(
        dispatcher,
        "_claim_dispatched_outbox_records",
        lambda *args, **kwargs: [record],
    )

    monkeypatch.setattr(
        dispatcher,
        "_reopen_dispatched_outbox_record",
        lambda *args, **kwargs: pytest.fail(
            "An unverified Redis job must not be reopened"
        ),
    )

    def fake_release(session_factory, *, outbox_id, lease_token):
        release_calls.append(outbox_id)
        return True

    monkeypatch.setattr(
        dispatcher,
        "_release_reconciliation_lease",
        fake_release,
    )

    result = dispatcher.reconcile_dispatched_document_jobs(
        session_factory=object(),
        verify_func=lambda *args: verification_result,
    )

    assert result == {
        "claimed": 1,
        "reopened": 0,
        "active": 0,
        "unverified": 1,
        "stale": 0,
    }

    assert release_calls == [record["outbox_id"]]


def test_reconciliation_verification_exception_is_unverified(
    monkeypatch,
):
    record = make_claimed_record()

    monkeypatch.setattr(
        dispatcher,
        "_claim_dispatched_outbox_records",
        lambda *args, **kwargs: [record],
    )

    monkeypatch.setattr(
        dispatcher,
        "_reopen_dispatched_outbox_record",
        lambda *args, **kwargs: pytest.fail(
            "A verification exception must not reopen the record"
        ),
    )

    monkeypatch.setattr(
        dispatcher,
        "_release_reconciliation_lease",
        lambda *args, **kwargs: True,
    )

    def failing_verify(*args):
        raise RuntimeError("Private Redis connection details")

    result = dispatcher.reconcile_dispatched_document_jobs(
        session_factory=object(),
        verify_func=failing_verify,
    )

    assert result == {
        "claimed": 1,
        "reopened": 0,
        "active": 0,
        "unverified": 1,
        "stale": 0,
    }


def test_reconciliation_lost_lease_is_stale(monkeypatch):
    record = make_claimed_record()

    monkeypatch.setattr(
        dispatcher,
        "_claim_dispatched_outbox_records",
        lambda *args, **kwargs: [record],
    )

    monkeypatch.setattr(
        dispatcher,
        "_reopen_dispatched_outbox_record",
        lambda *args, **kwargs: False,
    )

    monkeypatch.setattr(
        dispatcher,
        "_release_reconciliation_lease",
        lambda *args, **kwargs: False,
    )

    result = dispatcher.reconcile_dispatched_document_jobs(
        session_factory=object(),
        verify_func=lambda *args: dispatcher.DISPATCH_MISSING,
    )

    assert result == {
        "claimed": 1,
        "reopened": 0,
        "active": 0,
        "unverified": 0,
        "stale": 1,
    }


def test_reconciliation_passes_batch_size_to_claim(monkeypatch):
    claim_calls = []

    def fake_claim(session_factory, *, batch_size):
        claim_calls.append(batch_size)
        return []

    monkeypatch.setattr(
        dispatcher,
        "_claim_dispatched_outbox_records",
        fake_claim,
    )

    result = dispatcher.reconcile_dispatched_document_jobs(
        batch_size=25,
        session_factory=object(),
        verify_func=lambda *args: dispatcher.DISPATCH_ACTIVE,
    )

    assert claim_calls == [25]

    assert result == {
        "claimed": 0,
        "reopened": 0,
        "active": 0,
        "unverified": 0,
        "stale": 0,
    }


@pytest.mark.parametrize(
    "batch_size",
    [0, -1, 101, True, False, 1.5, "10", None],
)
def test_reconciliation_rejects_invalid_batch_size(batch_size):
    with pytest.raises(ValueError):
        dispatcher.reconcile_dispatched_document_jobs(
            batch_size=batch_size,
            session_factory=object(),
            verify_func=lambda *args: dispatcher.DISPATCH_ACTIVE,
        )
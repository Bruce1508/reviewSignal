"""Sync run lifecycle persistence (`docs/data-model.md` §13)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from reviewsignal_api.repositories.sync_runs import SyncRunRepository

SOURCE = "google"


def test_start_inserts_running_row(session: Session) -> None:
    repo = SyncRunRepository(session)

    run = repo.start(SOURCE)

    assert run.status == "running"
    assert run.started_at is not None
    assert run.finished_at is None


def test_save_cursor_round_trips_a_dict(session: Session) -> None:
    repo = SyncRunRepository(session)
    run = repo.start(SOURCE)

    repo.save_cursor(run, {"page_token": "abc123"})
    session.flush()
    session.expire(run)

    assert run.cursor_state == {"page_token": "abc123"}


def test_finish_sets_finished_at_and_counts(session: Session) -> None:
    repo = SyncRunRepository(session)
    run = repo.start(SOURCE)

    repo.finish(run, "success", reviews_fetched=10, reviews_created=3, reviews_updated=2)
    session.flush()

    assert run.status == "success"
    assert run.finished_at is not None
    assert run.reviews_fetched == 10
    assert run.reviews_created == 3
    assert run.reviews_updated == 2
    assert run.error_message is None


def test_finish_stores_error_message_on_failure(session: Session) -> None:
    repo = SyncRunRepository(session)
    run = repo.start(SOURCE)

    repo.finish(
        run,
        "failed",
        reviews_fetched=0,
        reviews_created=0,
        reviews_updated=0,
        error_message="API unreachable",
    )
    session.flush()

    assert run.status == "failed"
    assert run.error_message == "API unreachable"


def test_finish_rejects_invalid_status(session: Session) -> None:
    repo = SyncRunRepository(session)
    run = repo.start(SOURCE)

    with pytest.raises(ValueError, match="running"):
        repo.finish(run, "running", reviews_fetched=0, reviews_created=0, reviews_updated=0)


def test_finish_rejects_unknown_status(session: Session) -> None:
    repo = SyncRunRepository(session)
    run = repo.start(SOURCE)

    with pytest.raises(ValueError):
        repo.finish(
            run, "not-a-real-status", reviews_fetched=0, reviews_created=0, reviews_updated=0
        )


def test_latest_returns_most_recent_run_by_started_at(session: Session) -> None:
    repo = SyncRunRepository(session)
    older = repo.start(SOURCE)
    older.started_at = datetime.now(UTC) - timedelta(hours=1)
    newer = repo.start(SOURCE)
    session.flush()

    latest = repo.latest(SOURCE)

    assert latest is not None
    assert latest.id == newer.id
    assert latest.id != older.id


def test_last_successful_ignores_failed_runs(session: Session) -> None:
    repo = SyncRunRepository(session)

    old_success = repo.start(SOURCE)
    old_success.started_at = datetime.now(UTC) - timedelta(hours=2)
    repo.finish(old_success, "success", reviews_fetched=1, reviews_created=1, reviews_updated=0)

    recent_failure = repo.start(SOURCE)
    recent_failure.started_at = datetime.now(UTC) - timedelta(hours=1)
    repo.finish(recent_failure, "failed", reviews_fetched=0, reviews_created=0, reviews_updated=0)
    session.flush()

    watermark = repo.last_successful(SOURCE)

    assert watermark is not None
    assert watermark.id == old_success.id


def test_last_successful_returns_none_when_no_run_succeeded(session: Session) -> None:
    repo = SyncRunRepository(session)
    run = repo.start(SOURCE)
    repo.finish(run, "failed", reviews_fetched=0, reviews_created=0, reviews_updated=0)
    session.flush()

    assert repo.last_successful(SOURCE) is None

"""Contract tests for `/evaluation/*` (`docs/api-spec.md` §10, §12).

One run is one row: a single `evaluation_runs` record carries every metric family in
its `metrics` body (`docs/data-model.md` §16). These tests assert that shape directly,
because the alternative reading — a row per family — was a live ambiguity until it was
settled, and nothing else in the suite would catch a regression to it.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from reviewsignal_api.ai.evaluation.protocols import PredictedAspect
from reviewsignal_api.ai.evaluation.registry import PREDICTORS
from reviewsignal_api.db.models import EvaluationRun
from reviewsignal_worker.db import session_scope

# Shaped like `EvaluationResult.metrics_payload()`: three families under one row.
METRICS = {
    "classification": {
        "micro": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
        "macro": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
        "item_count": 2,
        "label_count": 3,
    },
    "sentiment": {"accuracy": 1.0, "pair_count": 2},
    "calibration": {"expected_error": 0.0, "prediction_count": 2},
}


def _record_run(
    evaluation_type: str = "classification",
    model_name: str = "stub",
    created_at: datetime | None = None,
    metrics: dict | None = None,
    notes: str | None = None,
) -> uuid.UUID:
    with session_scope() as session:
        run = EvaluationRun(
            evaluation_type=evaluation_type,
            model_name=model_name,
            model_version="v1",
            taxonomy_version="taxonomy-2026-09-01",
            dataset_version="v0-test",
            metrics=metrics if metrics is not None else METRICS,
            notes=notes,
        )
        if created_at is not None:
            run.created_at = created_at
        session.add(run)
        session.flush()
        return run.id


async def test_listing_runs_with_none_recorded_returns_an_empty_list(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/evaluation/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"] == []


async def test_listing_runs_returns_newest_first(client: AsyncClient) -> None:
    older = datetime.now(UTC) - timedelta(hours=1)
    first = _record_run(model_name="older", created_at=older)
    second = _record_run(model_name="newer")

    response = await client.get("/api/v1/evaluation/runs")

    assert response.status_code == 200
    ids = [run["id"] for run in response.json()["data"]]
    assert ids == [str(second), str(first)]


async def test_the_list_omits_the_metrics_body(client: AsyncClient) -> None:
    """`api-spec.md` §10 splits the contract: the list is run history, while
    metrics come from the detail route."""
    _record_run()

    response = await client.get("/api/v1/evaluation/runs")

    summary = response.json()["data"][0]
    assert "metrics" not in summary
    assert summary["evaluation_type"] == "classification"
    assert summary["dataset_version"] == "v0-test"
    assert summary["model_name"] == "stub"


async def test_one_run_is_one_row_carrying_every_metric_family(
    client: AsyncClient,
) -> None:
    """The settled shape: three families nested in one row, not three rows."""
    run_id = _record_run()

    response = await client.get(f"/api/v1/evaluation/runs/{run_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data["metrics"]) == {"classification", "sentiment", "calibration"}
    assert data["metrics"]["sentiment"]["pair_count"] == 2
    assert data["evaluation_type"] == "classification"

    listed = (await client.get("/api/v1/evaluation/runs")).json()["data"]
    assert len(listed) == 1, "a run with three metric families must not become three rows"


async def test_an_unmeasured_family_is_reported_as_null_not_zero(
    client: AsyncClient,
) -> None:
    """`evaluation.md` §30: a family that could not be measured is null, never zero."""
    run_id = _record_run(
        metrics={
            "classification": METRICS["classification"],
            "sentiment": None,
            "calibration": None,
        }
    )

    response = await client.get(f"/api/v1/evaluation/runs/{run_id}")

    metrics = response.json()["data"]["metrics"]
    assert metrics["sentiment"] is None
    assert metrics["calibration"] is None


async def test_detail_returns_notes_and_taxonomy_provenance(client: AsyncClient) -> None:
    run_id = _record_run(notes="synthetic smoke run")

    response = await client.get(f"/api/v1/evaluation/runs/{run_id}")

    data = response.json()["data"]
    assert data["notes"] == "synthetic smoke run"
    assert data["taxonomy_version"] == "taxonomy-2026-09-01"
    assert data["taxonomy_version_id"] is None


async def test_an_unknown_run_is_a_404_resource_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/evaluation/runs/{uuid.uuid4()}")

    assert response.status_code == 404
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_a_malformed_run_id_is_rejected(client: AsyncClient) -> None:
    """Request validation renders the failure envelope as 400, not FastAPI's raw 422."""
    response = await client.get("/api/v1/evaluation/runs/not-a-uuid")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_queueing_a_run_with_no_registered_predictor_is_model_unavailable(
    client: AsyncClient,
) -> None:
    """No classifier exists yet, so the documented failure is
    MODEL_UNAVAILABLE (`api-spec.md` §14)."""
    response = await client.post(
        "/api/v1/evaluation/run", json={"evaluation_type": "classification"}
    )

    assert response.status_code == 503
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "MODEL_UNAVAILABLE"


async def test_a_rejected_run_queues_no_job(client: AsyncClient) -> None:
    """Rejecting at request time keeps a doomed row out of `jobs` (`data-model.md` §14)."""
    await client.post("/api/v1/evaluation/run", json={"evaluation_type": "classification"})

    with session_scope() as session:
        queued = session.execute(text("SELECT count(*) FROM jobs")).scalar_one()
    assert queued == 0


async def test_an_empty_evaluation_type_is_a_validation_error(client: AsyncClient) -> None:
    response = await client.post("/api/v1/evaluation/run", json={"evaluation_type": ""})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


class _StubPredictor:
    """Backs the workflow so the route will queue. The route never calls `predict`."""

    name = "stub-classifier"
    version = "v0"
    prompt_version = None

    def predict(self, item: object) -> list[PredictedAspect]:
        return []


async def test_queueing_a_run_with_a_registered_predictor_is_accepted(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The accept path. `job_type` is asserted as a literal, not through the constant,
    so a typo in it cannot pass by agreeing with itself."""
    fake_job_id = uuid.uuid4()
    captured: dict = {}

    def fake_enqueue(job_type: str, payload: dict | None, max_attempts: int) -> uuid.UUID:
        captured["job_type"] = job_type
        captured["payload"] = payload
        return fake_job_id

    monkeypatch.setattr("reviewsignal_api.services.evaluation.enqueue", fake_enqueue)
    monkeypatch.setitem(PREDICTORS, "classification", _StubPredictor())

    response = await client.post(
        "/api/v1/evaluation/run", json={"evaluation_type": "classification"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["error"] is None
    assert body["data"] == {
        "job_id": str(fake_job_id),
        "status": "queued",
        "job_type": "evaluation_run",
    }
    assert captured["job_type"] == "evaluation_run"
    assert captured["payload"] == {"evaluation_type": "classification"}


async def test_an_unknown_workflow_is_a_validation_error_not_a_model_outage(
    client: AsyncClient,
) -> None:
    """`api-spec.md` §10 limits `evaluation_type` to the workflows `data-model.md` §16
    names. 503 would tell the caller to retry something that can never succeed."""
    response = await client.post("/api/v1/evaluation/run", json={"evaluation_type": "banana"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

# ReviewSignal AI — Model and Evaluation Runs
**Status:** Draft v1.1  
**Scope:** Records of a single model or workflow execution.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. These tables belong to
the schema owned by [`data-model.md`](data-model.md), record executions of the
workflows in [`ai-pipeline.md`](ai-pipeline.md), and hold the evidence
[`evaluation.md`](evaluation.md) scores and promotes against, within the boundaries of
[`architecture.md`](architecture.md).

Both tables answer "what happened during one run", not "what the product knows". That
is why they live here rather than beside the domain tables in
[`data-model.md`](data-model.md).

## 1. `model_runs`
```text
id UUID PK
task VARCHAR
provider VARCHAR
model_name VARCHAR
model_version VARCHAR NULL
prompt_version VARCHAR NULL
taxonomy_version_id UUID NULL
input_count INTEGER
latency_ms INTEGER
success BOOLEAN
fallback_used BOOLEAN
output_valid BOOLEAN
error_message TEXT NULL
metadata JSONB
created_at TIMESTAMPTZ
```

## 2. `evaluation_runs`
```text
id UUID PK
job_id UUID NULL UNIQUE FK jobs
evaluation_type VARCHAR
model_name VARCHAR
model_version VARCHAR NULL
prompt_version VARCHAR NULL
taxonomy_version_id UUID NULL
taxonomy_version VARCHAR NULL
dataset_version VARCHAR
metrics JSONB
notes TEXT NULL
created_at TIMESTAMPTZ
```
`evaluation_type` names the workflow evaluated — `classification` today, and later `taxonomy`, `anomaly`, or `recommendation`. One run records one row: every metric family that pass produced (classification, sentiment, calibration) is nested inside `metrics`, and a family it could not measure is stored as null (`evaluation.md` §30).
`job_id` names the queued job that produced the run, and is unique so a retried job cannot record a second one — `record` is insert-only, and a duplicate would silently corrupt the baseline `evaluation.md` §23 compares against. It is NULL for a run recorded outside the queue.
`taxonomy_version_id` links a run to a stored taxonomy; `taxonomy_version` is the version string the benchmark was labelled against, kept so a run still names its taxonomy when no `taxonomy_versions` row exists (`evaluation.md` §30).

`prompt_version` names the prompt a run scored and is NULL for a workflow that runs no prompt, which is every workflow in Phase 0. `evaluation.md` §30 requires it, and the `Predictor` protocol reports it so a prompted run cannot omit it silently: without it `evaluation.md` §23 could not attribute a regression to a prompt change.

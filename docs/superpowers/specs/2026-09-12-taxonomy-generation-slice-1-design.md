# Slice 1 — Single-Pass Taxonomy Generation
**Status:** Approved 2026-09-12
**Scope:** The first vertical slice of the AI pipeline: enqueue to Ollama to a stored
candidate taxonomy. Design only; `taxonomy-pipeline.md` remains the contract.

## Why this slice exists

`ai-pipeline.md` §40 puts taxonomy and Qwen classification first in the implementation
order. `ai-pipeline.md` §3 makes taxonomy the precondition for classification: with no
active version there is nothing to classify against. So the model-provider seam that
`ai-pipeline.md` §38 calls for is built here, inside a workflow that actually calls it,
rather than as a layer with no consumer.

Google Business Profile access is still not granted, so this runs against the 150
synthetic reviews the seeder writes. That is a deliberate limit: it proves the
mechanism, versioning, and persistence. It proves nothing about taxonomy quality, and
no quality claim may be made from a run over synthetic text.

## In scope

One pass: sample reviews, one model call, validate, persist a `candidate` version.

## Out of scope

Minibatching and the update loop (`taxonomy-pipeline.md` §3), the review gate and
refinement iterations (`taxonomy-pipeline.md` §5), automatic acceptance
(`taxonomy-pipeline.md` §6), LangGraph, and any new API endpoint. `architecture.md` §18.4
scopes LangGraph to iterative stateful workflows; a single pass is neither, so it
arrives with the refinement loop in slice 2.

## Trigger

`tools/generate_taxonomy.py` enqueues onto the existing RQ queue. The API surface does
not change. The dashboard's taxonomy page is already read-only and
`TaxonomyReader.list_versions` already returns candidates, so the stored version is
visible without new endpoints. `POST /taxonomy/generate` arrives in slice 2 alongside
automatic acceptance.

## Components

### `ai/provider.py`
`LLMProvider` protocol and `StructuredOutcome`. One method:
`generate_structured(prompt, schema_model, *, task)` takes a Pydantic model class and
returns a validated instance with `latency_ms`, `fallback_used`, and `output_valid`.

`StructuredOutcome` carries no field holding the model's raw text. Non-Negotiable Rule 3
forbids exposing or persisting hidden chain-of-thought, and qwen3 is a thinking model;
making the text unrepresentable enforces the rule through the type rather than through
discipline.

### `ai/ollama.py`
`OllamaProvider`, over `httpx`, already a dependency. Sends `format=<JSON Schema>`
derived from `model_json_schema()` and `think: false`, then validates the response with
Pydantic. Two layers: the schema makes malformed output rare, the validation is what the
code actually trusts.

Concrete, not behind a factory. There is one provider; the repository's simplicity rule forbids
configurability that was not requested. Future providers named in `ai-pipeline.md` §38
satisfy the same protocol.

### `ai/prompts/`
`get_prompt(prompt_id)` returning `Prompt(id, version, template)`, and
`taxonomy_generate_v1`. Prompts are Python constants, not external files: `model_runs`
must name exactly the prompt that ran, and a file outside version control can change
with no commit recording it. Changing a prompt means adding `_v2`, never editing `_v1`
(`ai-pipeline.md` §35).

### `repositories/model_runs.py`
`ModelRunRepository.record`, insert-only, following `EvaluationRunRepository`.

Records failures as well as successes. A run that fails schema validation and
dead-letters must still leave a row, or `ai-pipeline.md` §36 records only the happy path
and the observability it asks for does not exist.

`metadata` holds the input review count, model name, attempt count, and request options.
It never holds model output.

### `schemas/taxonomy_generation.py`
The Pydantic shape of the model's reply, mirroring the node structure in
`taxonomy-pipeline.md` §4. Descriptions are required there, so they are required here.

### `services/taxonomy_generation.py`
Samples reviews, calls the provider, flattens the returned tree into `taxonomy_nodes`
rows with `depth`, `slug`, and `sort_order`, and writes a `taxonomy_versions` row with
`status='candidate'`, `created_by='model'`, and `generation_model_run_id` pointing at the
row just recorded.

`version_number` is the current maximum plus one. No version is activated. The
"only one active version" rule in `taxonomy-tables.md` §1 therefore cannot be violated by
this slice.

Slugs derive from names and are unique within a version per the
`UNIQUE(taxonomy_version_id, slug)` constraint in `taxonomy-tables.md` §2; collisions take
a numeric suffix.

### `workers/reviewsignal_worker/jobs/taxonomy.py`
The job handler, following `jobs/evaluation.py`.

## Failure handling

`ai-pipeline.md` §37 specifies schema failure to stricter retry to dead letter. One retry
with a stricter instruction, `fallback_used=True` on that attempt, then
`PermanentJobError`. A fixed bound, per Non-Negotiable Rule 7.

## Configuration

`core/config.py` defaults `ollama_model` to `qwen2.5:14b`, which is not present on the
development machine; the available models are `qwen3:8b` and `qwen3:30b-a3b`. The default
becomes `qwen3:8b` for development-loop speed. It is an environment variable, so moving to
`qwen3:30b-a3b` is a `.env` change, not a code change.

## Testing

Test-first throughout.

- Fake provider, no network: assert the `taxonomy_versions`, `taxonomy_nodes`, and
  `model_runs` rows, parent-child structure, depth, and slug collision handling.
- Failure path: a fake provider returning off-schema JSON must produce one retry, then
  `PermanentJobError`, and still leave a `model_runs` row with `success=False`.
- Contract test against a real Ollama, skipped when `localhost:11434` does not answer.
  This is the only test that proves `format=<schema>` works with qwen3; the rest prove
  only that our own code is correct.

Every table written is already in `MANAGED_TABLES` in `tests/conftest.py`, so no test
rows leak into the development database.

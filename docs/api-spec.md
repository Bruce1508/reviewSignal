# ReviewSignal AI — API Specification
**Status:** Draft v1.1  
**Base:** `/api/v1`  
**Style:** REST + async job endpoints.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. Product intent is
owned by [`PRD.md`](PRD.md); [`architecture.md`](architecture.md)
defines the API boundary. Endpoint data comes from [`data-model.md`](data-model.md),
async AI behavior comes from [`ai-pipeline.md`](ai-pipeline.md), operations and
health expectations come from [`deployment.md`](deployment.md), and quality
evidence comes from [`evaluation.md`](evaluation.md).

## 1. Conventions
Success:
```json
{"data":{},"error":null}
```
Failure:
```json
{"data":null,"error":{"code":"RESOURCE_NOT_FOUND","message":"Review not found."}}
```
Use ISO 8601 dates. Pagination: `page`, `page_size`; MVP max `page_size=100`.

## 2. Health & System
### `GET /health`
Returns API/database/Redis health.

### `GET /system/status`
Returns last sync, queue depth, failed jobs, active taxonomy, active model, and last insight run.

## 3. Overview
### `GET /overview`
Query: `start_date`, `end_date`; default last 7 days.
Returns review count, average rating, positive/negative themes, active insights, rating trend.

## 4. Reviews
### `GET /reviews`
Filters: `page`, `page_size`, `q`, `rating`, `sentiment`, `category_id`, `start_date`, `end_date`.

### `GET /reviews/{review_id}`
Returns raw metadata, owner reply, active analysis, aspects, sentiment, confidence, evidence, taxonomy version.

### `POST /reviews/{review_id}/reanalyze`
Queues reanalysis and returns HTTP `202` with job ID.

## 5. Taxonomy
### `GET /taxonomy`
Returns active taxonomy tree.

### `GET /taxonomy/versions`
Returns version history.

### `GET /taxonomy/versions/{version_id}`
Returns one historical taxonomy.

### `GET /taxonomy/versions/{version_id}/diff`
Returns changes against parent version.

### `POST /taxonomy/rebuild`
Queues automatic rebuild.

### `POST /taxonomy/nodes`
Request:
```json
{"parent_id":null,"name":"Wait Time","description":"Feedback about service delays."}
```

### `PATCH /taxonomy/nodes/{node_id}`
Rename, edit description, or move node.

### `POST /taxonomy/merge`
```json
{"source_node_ids":["uuid1","uuid2"],"target_name":"Staff Experience","target_description":"..."}
```

### `POST /taxonomy/split`
Creates replacement nodes from one node.

### `DELETE /taxonomy/nodes/{node_id}`
Deletes a node in a new taxonomy version.

### `POST /taxonomy/rollback/{version_id}`
Creates a new active version from historical state.

All taxonomy mutations create a new version and queue reclassification.

## 6. Trends
### `GET /trends/categories`
Filters: `start_date`, `end_date`, `sentiment`, `category_id`.

### `GET /trends/ratings`
Returns rating history.

### `GET /trends/summary`
Returns biggest positive/negative movements.

## 7. Insights
### `GET /insights`
Filters: `status`, `severity`, `category_id`, `start_date`, `end_date`.

### `GET /insights/{insight_id}`
Returns title, summary, severity, evidence, related reviews, status, actions, impact.

### `PATCH /insights/{insight_id}/status`
```json
{"status":"monitoring"}
```
Manual update records override metadata.

### `POST /insights/{insight_id}/actions`
```json
{"action_text":"Add extra coverage Friday evening.","action_date":"2026-09-05","note_text":"Two-week trial."}
```

### `PATCH /insights/{insight_id}/actions/{action_id}`
Updates action/note/status.

### `POST /insights/{insight_id}/recompute-impact`
Queues impact analysis.

## 8. Google Business Profile
### `GET /google/status`
Returns connection state.

### `GET /google/connect`
Starts OAuth.

### `GET /google/callback`
OAuth callback.

### `GET /google/accounts`
Lists the Google accounts the stored grant can see: `account_id`, `name`.

### `GET /google/locations`
Query: `account_id` (required). Lists that account's locations: `location_id`, `title`.

### `POST /google/location`
Selects the profile to ingest from and returns the updated connection state.
```json
{"account_id":"111111111111111111111","location_id":"222222222222222222222"}
```
OAuth grants access to a user, but reviews are fetched per location, so connecting is
two steps. `POST /google/backfill` and `POST /google/sync` queue jobs that fail until
a location is selected. Both ids must match `^[A-Za-z0-9_-]{1,128}$`; they become path
segments in the upstream request.

### `POST /google/disconnect`
Disconnects integration.

### `POST /google/backfill`
Queues full historical backfill.

### `POST /google/sync`
Queues manual incremental sync.

## 9. Jobs
### `GET /jobs`
Filters: `status`, `job_type`, `page`, `page_size`.

### `GET /jobs/{job_id}`
Returns status, attempts, timestamps, and error context.

### `POST /jobs/{job_id}/retry`
Requeues retryable failed/dead-letter job.

## 10. Evaluation
### `GET /evaluation/runs`
Returns historical evaluation runs.

### `GET /evaluation/runs/{run_id}`
Returns metrics and metadata.

### `POST /evaluation/run`
Queues benchmark evaluation.
```json
{"evaluation_type":"classification"}
```
`evaluation_type` names the workflow to evaluate, not a metric family: one run records
one `evaluation_runs` row holding every family it produced (`model-runs.md` §2).
`evaluation_type` must be one of the workflows `model-runs.md` §2 names; anything else
is `VALIDATION_ERROR`, because a workflow that does not exist is a malformed request
rather than a model that is temporarily down.
Returns `MODEL_UNAVAILABLE` when the workflow is known but no predictor is registered
for it, so no job is queued that cannot succeed.

These endpoints exist before the evaluation dashboard, which `PRD.md` places in Phase 3.

## 11. Settings
### `GET /settings`
Returns safe config such as default date range, daily sync time, active LLM model, embedding model, classification threshold.

### `PATCH /settings`
Updates supported non-secret settings. Secrets are never returned.

## 12. Async Convention
Long jobs return HTTP `202`:
```json
{"job_id":"uuid","status":"queued","job_type":"taxonomy_rebuild"}
```
Frontend polls `GET /jobs/{job_id}`. MVP does not require WebSockets.

## 13. Validation
- rating 1–5.
- confidence 0–1.
- valid taxonomy node IDs.
- valid insight statuses.
- `start_date <= end_date`.
- `page_size <= 100`.
Use Pydantic at the API boundary.

## 14. Error Codes
`VALIDATION_ERROR`, `UNAUTHORIZED`, `RESOURCE_NOT_FOUND`, `CONFLICT`, `GOOGLE_NOT_CONNECTED`, `GOOGLE_API_ERROR`, `JOB_NOT_RETRYABLE`, `TAXONOMY_VERSION_CONFLICT`, `MODEL_UNAVAILABLE`, `INTERNAL_ERROR`.

## 15. Authentication
MVP is single-user/internal: protected admin session, secure cookie, no public signup, no role system.

Mechanism: a single operator password, supplied by environment variable, is exchanged at `POST /auth/login` for a signed session cookie. A dependency guards every route under `/api/v1` except `/health`, which stays open for container health checks. `POST /auth/login` takes `{ "password": string }` and sets the `rs_session` cookie; `POST /auth/logout` clears it and is itself unguarded, so an expired session can always be dropped. The cookie is `HttpOnly`, `SameSite=lax`, `Secure` outside local, and lapses after 12 hours. Sessions are stateless, so rotating `SESSION_SECRET` is the revocation mechanism and invalidates all of them at once.

CORS is not configured: the dashboard has no browser-side calls yet. Adding one requires credentialed CORS and a `SameSite` review, because the dashboard and the API are served from different origins.

## 16. Design Rules
1. Keep business logic out of route handlers.
2. Keep long jobs asynchronous.
3. Use stable IDs for references.
4. Version API from day one.
5. Never return secrets.
6. Never expose raw model chain-of-thought.
7. Return evidence/confidence instead.

## 17. Summary
Endpoint groups:
```text
/overview
/reviews
/taxonomy
/trends
/insights
/google
/jobs
/evaluation
/settings
/system
```
REST is sufficient for MVP; GraphQL/WebSockets are unnecessary.

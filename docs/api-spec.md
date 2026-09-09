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

**Split out of this document:** [`api-dashboard.md`](api-dashboard.md) holds what was
sections 3-7, 9, and 11. Numbering here keeps its gaps so existing `§N` citations resolve.

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

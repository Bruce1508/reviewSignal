# ReviewSignal AI — Dashboard API
**Status:** Draft v1.1  
**Scope:** REST contracts for the dashboard pages: overview, reviews, taxonomy, trends, insights, and settings.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. These endpoints follow the conventions, validation,
authentication, and async rules owned by [`api-spec.md`](api-spec.md), return the
entities defined in [`data-model.md`](data-model.md), and back the pages listed in
`PRD.md` §5.

[`api-spec.md`](api-spec.md) owns how the API behaves. This document owns what the
page-facing endpoints return.

## 1. Overview
### `GET /overview`
Query: `start_date`, `end_date`; default last 7 days.
Returns review count, average rating, positive/negative themes, active insights, rating trend.

## 2. Reviews
### `GET /reviews`
Filters: `page`, `page_size`, `q`, `rating`, `sentiment`, `category_id`, `start_date`, `end_date`.

### `GET /reviews/{review_id}`
Returns raw metadata, owner reply, active analysis, aspects, sentiment, confidence, evidence, taxonomy version.

### `POST /reviews/{review_id}/reanalyze`
Queues reanalysis and returns HTTP `202` with job ID.

## 3. Taxonomy
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

## 4. Trends
### `GET /trends/categories`
Filters: `start_date`, `end_date`, `sentiment`, `category_id`.

### `GET /trends/ratings`
Returns rating history.

### `GET /trends/summary`
Returns biggest positive/negative movements.

## 5. Insights
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

## 6. Settings
### `GET /settings`
Returns safe config such as default date range, daily sync time, active LLM model, embedding model, classification threshold.

### `PATCH /settings`
Updates supported non-secret settings. Secrets are never returned.

## 7. Jobs
### `GET /jobs`
Filters: `status`, `job_type`, `page`, `page_size`.

### `GET /jobs/{job_id}`
Returns status, attempts, timestamps, and error context.

### `POST /jobs/{job_id}/retry`
Requeues retryable failed/dead-letter job.

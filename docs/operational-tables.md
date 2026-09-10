# ReviewSignal AI — Operational Tables
**Status:** Draft v1.1  
**Scope:** `sync_runs`, `jobs`, `settings`, and `source_credentials`.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. These tables belong to the schema owned by
[`data-model.md`](data-model.md) and hold how the system runs rather than what it knows:
they are written by ingestion and the queue in
[`architecture.md`](architecture.md) and operated per [`operations.md`](operations.md).

## 1. `sync_runs`
```text
id UUID PK
source VARCHAR
started_at TIMESTAMPTZ
finished_at TIMESTAMPTZ NULL
status VARCHAR
reviews_fetched INTEGER
reviews_created INTEGER
reviews_updated INTEGER
error_message TEXT NULL
cursor_state JSONB NULL
```
Statuses: `running`, `success`, `failed`, `partial`.

## 2. `jobs`
Application-level job tracking independent of the queue backend.
```text
id UUID PK
job_type VARCHAR
status VARCHAR
payload JSONB
attempt_count INTEGER
max_attempts INTEGER
queued_at TIMESTAMPTZ
started_at TIMESTAMPTZ NULL
finished_at TIMESTAMPTZ NULL
error_message TEXT NULL
```
Statuses: `queued`, `running`, `succeeded`, `failed`, `dead_letter`.

## 3. `settings`
```text
id UUID PK
key VARCHAR UNIQUE
value JSONB
updated_at TIMESTAMPTZ
```
Store non-secret configuration only. Secrets belong in environment/AWS secret storage.

## 4. `source_credentials`
Per-source OAuth credentials, encrypted at rest.
```text
id UUID PK
source VARCHAR UNIQUE
status VARCHAR
account_id VARCHAR NULL
location_id VARCHAR NULL
access_token_encrypted BYTEA NULL
refresh_token_encrypted BYTEA NULL
token_expires_at TIMESTAMPTZ NULL
scopes JSONB
connected_at TIMESTAMPTZ NULL
updated_at TIMESTAMPTZ
```
Statuses: `connected`, `disconnected`, `invalid`. A `connected` row must hold a
refresh token. Deploy-time secrets stay in the environment (§3); a refresh token is
issued at runtime by the OAuth callback, so it cannot be one, and ciphertext here is
never returned by the API.

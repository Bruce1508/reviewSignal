# ReviewSignal AI

Internal AI Customer Intelligence Platform for Maple Photo Imaging. Google
Business Profile reviews in, an evolving taxonomy, aspect-level sentiment,
statistical anomaly detection, and evidence-grounded insights out.

Specifications live in [`docs/`](docs/README.md); start with
[`docs/architecture.md`](docs/architecture.md) for system boundaries.

The product requirements document (`docs/PRD.md`) is client-confidential and is
not published here, so documents that link to it will 404 on GitHub.

## Status

Milestone 0 — Project Foundation. The repository, local runtime, database
schema, job lifecycle, and quality gates exist. There is no Google integration,
taxonomy discovery, or classification yet; those begin with PRD Phase 0.

## Local setup

Requires Docker, `uv`, and Node 22+.

```bash
cp .env.example .env      # then edit as needed; .env is never committed
make install
make up                   # PostgreSQL + Redis
make migrate              # apply the baseline schema
```

Run the services in separate shells:

```bash
make api      # http://localhost:8000/api/v1/health
make worker
make web      # http://localhost:3000
```

Ollama runs natively on macOS for hardware acceleration
([`docs/deployment.md`](docs/deployment.md) §3). Point `OLLAMA_BASE_URL` at it.
A containerized Ollama is available via `docker compose --profile ollama up`.

## Checks

```bash
make check    # ruff, pyright, pytest, eslint, tsc, next build
```

`make up` must be running first — the tests exercise real PostgreSQL constraints
rather than mocking them.

## Layout

```text
apps/api/      FastAPI: api → services → repositories
apps/web/      Next.js dashboard
workers/       RQ worker and job lifecycle
packages/      reserved seams for ai, analytics, integrations
migrations/    Alembic
infra/         Dockerfiles
docs/          specifications
tests/         api, db, workers
```

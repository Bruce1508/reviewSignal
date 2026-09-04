---
name: fastapi-patterns
description: FastAPI patterns for ReviewSignal AI. Use for API routes, Pydantic schemas, services, repositories, async endpoints, errors, and background-job submission.
allowed-tools: Read, Grep, Glob
---
# FastAPI Patterns

Use:
```text
route → service → repository
```

## Route
- validate request,
- call service,
- map domain error to HTTP,
- return response schema,
- stay thin.

## Service
Own business rules and orchestration.

## Repository
Own persistence only.

## Long Work
Taxonomy rebuild, reclassification, embeddings, and LLM batches must return `202 + job_id` and run in workers.

## Pydantic
Use explicit request/response schemas and validate AI boundary objects.

## Errors
Prefer domain exception → centralized API mapping.

## Async
Use async for I/O, not CPU work by habit.

## Avoid
- business logic in routes,
- direct DB access in presentation handlers,
- unvalidated model JSON,
- synchronous LLM work in interactive requests,
- broad exception swallowing.

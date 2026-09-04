---
name: testing-patterns
description: Testing patterns for ReviewSignal AI. Use for tests, bugs, integrations, jobs, taxonomy/versioning logic, API behavior, and AI structured-output validation.
allowed-tools: Read, Grep, Glob
---
# Testing Patterns

Prefer:
1. unit tests for pure logic,
2. integration tests for DB/jobs,
3. focused API tests,
4. few end-to-end flows.

## AI
Normal unit tests should not depend on live Qwen.
Test schemas, graph routing, retries, fallback decisions, and mocked provider responses.
Keep benchmark evaluation separate.

## Taxonomy
Test one-active-version, merge/split/rename, rollback, reclassification trigger.

## Google Sync
Test idempotency, duplicates, updates, retry, partial failure.

## Jobs
Test success, retry, max attempts, DLQ.

## Frontend
Test loading, empty, error, success, destructive taxonomy actions.

## Bug Fix Rule
reproduce → failing regression test → fix → pass.

## Avoid
- huge AI-output snapshots,
- production OAuth in tests,
- live LLM calls in CI unit suite,
- happy-path-only tests.

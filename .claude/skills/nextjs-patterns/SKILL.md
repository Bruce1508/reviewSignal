---
name: nextjs-patterns
description: Next.js and TypeScript patterns for ReviewSignal dashboard pages, review tables, taxonomy editor, trends, insights, settings, API clients, and UI states.
allowed-tools: Read, Grep, Glob
---
# Next.js Patterns

Core routes:
`/overview`, `/reviews`, `/taxonomy`, `/trends`, `/insights`, `/settings`.

Frontend handles presentation and interaction.
Backend owns business rules and AI.

Never call Ollama, PostgreSQL, or Google Business Profile directly from client code.

## UI States
Every data-driven screen handles:
- loading,
- empty,
- error,
- success.

## API
Use a centralized typed API client.

## Review Detail
Show category, sentiment, confidence, evidence.
Never display chain-of-thought.

## Taxonomy Editor
Make version/reclassification effects clear for destructive actions.

## Filters
Support keyword, rating, sentiment, category, date range.

## TypeScript
Strict mode, avoid `any`, narrow unknown API errors safely.

## Avoid
- DB access from frontend,
- client secrets,
- duplicated analytics logic,
- silent API failures.

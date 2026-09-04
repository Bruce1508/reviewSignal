# ReviewSignal AI — Claude Project Memory

ReviewSignal is an internal AI Customer Intelligence Platform for Maple Photo Imaging.

## Start Here

Before meaningful work, read:

1. `docs/README.md` — documentation map and authority rules.
2. `docs/PRD.md` — product scope, requirements, and acceptance intent.
3. `docs/architecture.md` — system boundaries and technical constraints.
4. Only the subsystem docs relevant to the task.
5. Existing code and tests last; they describe implementation, not requirements.

Do not load every document by default.

## Workflow

Use as appropriate:

```text
/onboard
→ /implement
→ /review
→ /ai-eval     # AI changes only
→ /docs-sync   # contract/behavior changes only
```

Use `.claude/agents/code-reviewer.md` for meaningful reviews.

## Source of Truth

```text
PRD → product requirements
Architecture → system boundaries
Subsystem docs → detailed contracts
Code/tests → implementation evidence
```

Never invent missing requirements or change requirements to match existing code.

If authoritative docs disagree, stop and report:

```text
SPEC CONFLICT
Files:
Conflict:
Impact:
Decision Required:
```

Do not silently resolve specification conflicts.

## Requirement Trace

For meaningful feature work:

```text
Requirement
→ Architecture constraint
→ Subsystem contract
→ Implementation
→ Tests / Evaluation
```

Do not implement functionality that cannot be traced to a requirement or explicit task.

## MVP Guardrails

- One Maple Photo location.
- One internal user.
- Google Business Profile only.
- English review analysis only.
- Historical backfill plus daily sync.
- Data-driven taxonomy; never hard-code categories.
- Taxonomy changes are versioned and trigger historical reclassification.
- Multi-label, aspect-level analysis.
- Insights and recommendations must be evidence-grounded.

`docs/PRD.md` remains authoritative if this summary ever differs.

## Non-Negotiable Rules

1. PostgreSQL is the system of record.
2. Preserve raw inputs and historical analyses.
3. Never expose or persist hidden chain-of-thought.
4. Queue long-running AI work.
5. Keep API handlers thin; business logic belongs in services.
6. Validate structured AI outputs.
7. Bound iterative AI workflows.
8. Prefer deterministic code, ML, or statistics when an LLM is unnecessary.
9. Statistical logic detects anomalies before LLM explanation.
10. Model or prompt changes require evaluation before promotion.
11. Never commit secrets, credentials, or OAuth tokens.
12. Do not silently resolve pending technical decisions.

## Documentation Rules

- One authoritative owner per contract.
- Link instead of duplicating content.
- Keep technical docs ≤100 lines where practical.
- Update affected docs when documented behavior or contracts change.

## Git Rules

- Do not edit directly on `main`.
- Keep changes focused.
- Preserve existing user work.
- Inspect `git diff` before completion.
- Never claim checks passed unless they were actually run.

## Definition of Done

Work is complete only when:

- the relevant requirement is identified,
- implementation stays within scope,
- architecture/contracts remain valid,
- relevant tests and checks pass,
- failure paths are handled,
- required AI evaluation passes,
- affected docs are synchronized,
- unresolved risks or assumptions are reported.
---
description: Understand a ReviewSignal task before implementation.
allowed-tools: Read, Grep, Glob, Bash(git:*)
---
# Onboard
Task: $ARGUMENTS

## Documentation order
1. Read `CLAUDE.md` for project-wide rules.
2. Read `docs/README.md` for the documentation map and conflict rules.
3. If `docs/PRD.md` exists, locate the relevant product requirement first.
4. Read `docs/architecture.md` for system boundaries.
5. Read only the subsystem documents relevant to the task.

Do not invent a missing PRD requirement. If the PRD, architecture, subsystem
documents, code, or tests disagree, report a `SPEC CONFLICT` and identify the
exact statements before planning implementation.

## Investigation
1. Search the related code and tests.
2. Summarize current behavior and required behavior separately.
3. Trace the task through:
   `requirement → architecture → subsystem contract → code → tests`.
4. Identify affected components, constraints, risks, and likely files.
5. Produce a concise implementation plan.

## Document routing
- AI, taxonomy, classification, anomaly, or insight work:
  `docs/ai-pipeline.md` and `docs/evaluation.md`.
- Taxonomy persistence, versioning, or historical data:
  `docs/data-model.md`.
- API behavior: `docs/api-spec.md`.
- Runtime, worker, secrets, health, or infrastructure:
  `docs/deployment.md`.

## Handoff
Finish with the relevant requirement, documents read, current-vs-required gap,
affected files, risks, unresolved conflicts, and a plan ready for
`.claude/commands/implement.md`.

Do not edit files unless explicitly asked.

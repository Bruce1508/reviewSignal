---
description: Implement a ReviewSignal feature using project docs, tests, and quality gates.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
---
# Implement
Task: $ARGUMENTS

## Before editing
1. Read `CLAUDE.md`.
2. Read `docs/README.md` for the documentation map and conflict rules.
3. If `docs/PRD.md` exists, locate the requirement that authorizes the change.
4. Read `docs/architecture.md` and only the relevant subsystem documents.
5. Inspect the existing implementation and tests.
6. Confirm the trace:
   `requirement → architecture → subsystem contract → code → tests`.

If onboarding has not been completed, perform the checks in
`.claude/commands/onboard.md` first. If sources disagree, stop and report a
`SPEC CONFLICT`; do not silently choose one or rewrite requirements to match code.

## Implementation
1. Implement the smallest coherent change within the documented scope.
2. Add or update tests for required behavior and meaningful failure cases.
3. Run targeted tests, then relevant type and lint checks.
4. Inspect `git diff` for unintended or unrelated changes.
5. Apply `.claude/agents/code-reviewer.md` and the checks in
   `.claude/commands/review.md`.
6. For AI behavior changes, run the relevant evaluation through
   `.claude/commands/ai-eval.md`.
7. If contracts or behavior changed, follow
   `.claude/commands/docs-sync.md` for the affected documents only.

## Project rules
- Do not expand product scope or perform unrelated refactors.
- Do not hard-code taxonomy labels.
- Queue long-running AI work.
- Validate structured model outputs.
- Preserve historical and versioned data.
- Never expose or persist hidden chain-of-thought.
- Treat PostgreSQL as the system of record.
- Use statistics to detect anomalies before asking an LLM to explain them.

## Handoff
Finish with files changed, requirement satisfied, checks run, evaluation results
when applicable, risks, documentation updates, and follow-ups.

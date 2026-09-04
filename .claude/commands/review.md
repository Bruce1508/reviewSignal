---
description: Review current changes against ReviewSignal requirements, architecture, and quality rules.
allowed-tools: Read, Grep, Glob, Bash(git:*)
---
# Review

## Review order
1. Read `CLAUDE.md` and `docs/README.md`.
2. Inspect `git diff` and identify the behavior being changed.
3. If `docs/PRD.md` exists, locate the relevant product requirement.
4. Read `docs/architecture.md` and only the affected subsystem documents.
5. Apply `.claude/agents/code-reviewer.md`.

## Checks
- Verify the trace:
  `requirement → architecture → subsystem contract → code → tests`.
- Check correctness, scope, architecture boundaries, data integrity, security,
  retries, failure behavior, and test coverage.
- For AI changes, check grounding, structured-output validation, confidence and
  fallback behavior, model/prompt versioning, and `docs/evaluation.md` impact.
- Check whether API, data, deployment, evaluation, or AI documentation drifted.
- If sources disagree, report a `SPEC CONFLICT`; do not resolve it silently.

## Output
Return prioritized findings with file and line references, followed by a verdict:
`APPROVE`, `APPROVE WITH FOLLOW-UPS`, or `REQUEST CHANGES`.

Mention evaluation or documentation work that should continue through
`.claude/commands/ai-eval.md` or `.claude/commands/docs-sync.md`.
Do not edit unless explicitly asked.

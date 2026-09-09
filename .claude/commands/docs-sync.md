---
description: Check and, when requested, update ReviewSignal documentation to match approved requirements and contracts.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(git:*)
---
# Docs Sync

## Source order
1. Read `CLAUDE.md`.
2. Read `docs/README.md` for the documentation map and conflict rules.
3. If `docs/PRD.md` exists, treat it as the product source of truth.
4. Treat `docs/architecture.md` as the source for system boundaries.
5. Treat each subsystem document as the owner of its detailed contract.

## Sync workflow
1. Inspect recent or current code and test changes.
2. Identify the approved requirement or contract behind each change.
3. Compare only the affected documents:
   - AI behavior: `docs/ai-pipeline.md`,
   - persistence/versioning: `docs/data-model.md`,
   - API contracts: `docs/api-spec.md`,
   - runtime/operations: `docs/deployment.md`,
   - quality gates: `docs/evaluation.md`.
4. Report stale statements, broken links, duplicated ownership, missing contract
   changes, and conflicts.
5. When updates are explicitly requested, edit only the affected documents and
   preserve established product decisions and terminology.
6. Recheck links, terminology, document ownership, and physical line counts.

## Conflict rules
- Do not change `docs/PRD.md` merely to match existing code.
- Do not let code or tests silently redefine product requirements.
- If the PRD, architecture, subsystem docs, and implementation disagree, report
  a `SPEC CONFLICT` and pause that update until the intended behavior is resolved.
- After an approved decision, update the owning document first, then its dependents.

## Documentation rules
- Keep every technical document within the length limit `docs/README.md` sets.
- Keep one primary responsibility per file.
- Link to the owning document instead of duplicating details.
- Do not invent requirements, metrics, commands, or implementation status.

Finish with documents checked, drift found, files updated, unresolved conflicts,
and any follow-up for `.claude/commands/review.md` or
`.claude/commands/ai-eval.md`.

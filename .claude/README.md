# ReviewSignal AI — Claude Code Configuration

This directory defines how Claude Code works with ReviewSignal. Product and
system specifications remain in `docs/`; they are not duplicated here.

## Structure

```text
CLAUDE.md                         # project-wide memory and invariants
.claude/
├── README.md                    # this configuration map
├── agents/
│   └── code-reviewer.md         # project-specific review checklist
├── commands/
│   ├── onboard.md               # understand the task and relevant contracts
│   ├── implement.md             # implement and verify a scoped change
│   ├── review.md                # inspect changes against requirements
│   ├── ai-eval.md               # evaluate AI behavior and promotion evidence
│   └── docs-sync.md             # detect and repair documentation drift
├── hooks/
│   ├── block-main-edits.sh      # PreToolUse branch guard
│   └── post-edit-check.sh       # PostToolUse lint/type check
├── skills/
│   ├── fastapi-patterns/SKILL.md
│   ├── langgraph-patterns/SKILL.md
│   ├── database-patterns/SKILL.md
│   ├── ai-evaluation/SKILL.md
│   ├── testing-patterns/SKILL.md
│   └── nextjs-patterns/SKILL.md
├── settings.json                # executable hooks and permissions
└── settings.md                  # rationale and rollout order
```

`settings.json` holds the executable configuration; `settings.md` records the
rationale and rollout order behind it. Two hooks are active as of Milestone 0: a
branch guard on `Edit`/`Write`/`NotebookEdit`, and a per-file lint/type check
after `Edit`/`Write`. No LSP configuration is present — the settings schema
exposes no key for it.

## Knowledge Model

```text
CLAUDE.md
→ docs/README.md
→ docs/PRD.md
→ docs/architecture.md
→ relevant subsystem documents
→ code and tests
```

- `CLAUDE.md` owns project-wide memory, invariants, and working rules.
- `docs/README.md` owns the documentation map and reading order.
- `docs/PRD.md` owns product behavior, scope, and acceptance intent.
- `docs/architecture.md` owns system boundaries and component responsibilities.
- Other `docs/*.md` files own detailed subsystem contracts.
- `.claude/skills/` contains domain implementation patterns.
- `.claude/commands/` contains repeatable workflows.
- `.claude/agents/` contains specialist review instructions.
- Hooks and LSP are enforceable guardrails only when configured in settings.

Code and tests show the current implementation. They may reveal documentation
drift, but they do not silently redefine product requirements.

## Workflow

1. Run `/onboard <task>` for unfamiliar or cross-cutting work.
2. Run `/implement <task>` after the requirement and contracts are understood.
3. Run `/review` before considering implementation complete.
4. Run `/ai-eval <target>` when AI behavior, prompts, models, classifiers,
   taxonomy, or routing changes.
5. Run `/docs-sync` when approved behavior or contracts changed.

```text
onboard → implement → review → ai-eval when applicable → docs-sync when needed
```

Each command links to the next relevant workflow and reads only the subsystem
documents needed after consulting the documentation map.

## Conflict Policy

If `docs/PRD.md`, architecture, subsystem documents, code, or tests disagree:

1. Stop work on the disputed behavior.
2. Report `SPEC CONFLICT` with the exact files and statements.
3. Ask for the intended behavior to be resolved.
4. Update the owning source of truth first, then dependent documents and code.

Never invent missing requirements, expand MVP scope silently, or rewrite a
requirement merely to match existing code.

## Maintenance Rules

- Keep configuration instructions concise and project-specific.
- Keep each technical document at or below 300 physical lines.
- Keep one primary responsibility per file.
- Link to the owning file instead of copying its details.
- Add a skill, command, agent, or automation only for a recurring need.
- Keep personal preferences in local, gitignored configuration.
- Revisit this map whenever configuration files are added, removed, or renamed.

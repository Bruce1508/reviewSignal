# ReviewSignal AI — Claude Code Settings Guide
Actual executable config lives in `.claude/settings.json`; hook scripts live in
`.claude/hooks/`. This file records the reasoning and the rollout order.

## LSP
Pyright and the TypeScript language server are the intended tooling, and both
run through `make typecheck`. The settings schema exposes no LSP key, so there
is nothing to configure here — do not claim LSP is enabled via settings.

## Pre-Edit Guard
Use `PreToolUse` to block file edits on `main`.

## Post-Edit Checks
Python changes:
```text
ruff → pyright → targeted pytest
```
TypeScript changes:
```text
eslint → tsc --noEmit → targeted tests
```

Avoid running the entire suite after every tiny edit if it hurts iteration speed.

## Skill Routing
Do not build automatic skill-routing yet.
Add it later only when many skills exist and missed routing becomes a real problem.

## Permissions
Be conservative with destructive shell commands, Git history rewriting, production commands, and secret/config files.

## Secrets
Use environment variable references; never hard-code secrets in Claude settings.

## Rollout Order
1. LSP — not configurable via settings; covered by `make typecheck`.
2. protected-main hook — **done** (`hooks/block-main-edits.sh`).
3. lightweight post-edit lint/type checks — **done** (`hooks/post-edit-check.sh`).
4. targeted tests — deferred; `make check` runs them on demand.
5. more automation only when recurring pain appears.

The goal is reliable assistance, not maximum automation.

#!/usr/bin/env bash
# Blocks edits while HEAD is on a protected branch (CLAUDE.md: "Do not edit
# directly on main"). Exits 0 in every case; the decision is carried in JSON.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
# symbolic-ref also resolves an unborn branch, which rev-parse cannot.
branch="$(git -C "$root" symbolic-ref --short HEAD 2>/dev/null \
  || git -C "$root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"

case "$branch" in
  main|master)
    printf '%s' "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"Refusing to edit on '${branch}'. CLAUDE.md requires work on a feature branch — run: git checkout -b <branch>\"}}"
    ;;
  *)
    ;;
esac
exit 0

#!/usr/bin/env bash
# Lightweight per-file checks after an edit (docs: .claude/settings.md).
# Python: ruff then pyright. TypeScript: eslint. Tests stay manual (`make check`)
# so iteration speed is not sacrificed to automation.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
file="$(jq -r '.tool_response.filePath // .tool_input.file_path // empty' 2>/dev/null)"
[ -n "$file" ] || exit 0
[ -f "$file" ] || exit 0

output=""
case "$file" in
  *.py)
    output="$(cd "$root" && uv run ruff check "$file" 2>&1)" || true
    if [ -z "$output" ] || echo "$output" | grep -q "All checks passed"; then
      output="$(cd "$root" && uv run pyright "$file" 2>&1 | grep -v "^0 errors" || true)"
    fi
    ;;
  *.ts|*.tsx)
    output="$(cd "$root/apps/web" && npx --no-install eslint "$file" 2>&1)" || true
    ;;
  *)
    exit 0
    ;;
esac

# Only speak up when something is actually wrong.
if [ -n "$output" ] && ! echo "$output" | grep -qi "all checks passed"; then
  printf '%s' "$(jq -nc --arg ctx "$output" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$ctx}}')"
fi
exit 0

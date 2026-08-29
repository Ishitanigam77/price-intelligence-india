#!/usr/bin/env bash
# Fail if a command would print likely secrets. Used as a pipeline guard.
set -euo pipefail

PATTERN='(password|secret|token|apikey|api_key|connectionstring|private_key)'
if echo "${1:-}" | grep -Ei "${PATTERN}" >/dev/null; then
  echo "Refusing to echo a value whose name looks like a secret." >&2
  exit 1
fi

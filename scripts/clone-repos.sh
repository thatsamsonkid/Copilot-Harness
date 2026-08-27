#!/usr/bin/env bash
# Clone catalog repos as siblings of this harness (never inside it).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HARNESS_ROOT="${HARNESS_ROOT:-$ROOT}"

if [[ -x "$ROOT/.venv/bin/harness" ]]; then
  exec "$ROOT/.venv/bin/harness" clone "$@"
fi

if command -v harness >/dev/null 2>&1; then
  exec harness clone "$@"
fi

PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m harness clone "$@"

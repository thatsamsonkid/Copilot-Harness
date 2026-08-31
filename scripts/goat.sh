#!/usr/bin/env bash
# Run the goat CLI through uv when possible.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GOAT_ROOT="${GOAT_ROOT:-${COBOOSE_ROOT:-$ROOT}}"

if command -v uv >/dev/null 2>&1 && [[ -f "$ROOT/uv.lock" || -f "$ROOT/pyproject.toml" ]]; then
  exec uv run --project "$ROOT" goat "$@"
fi

if [[ -x "$ROOT/.venv/bin/goat" ]]; then
  exec "$ROOT/.venv/bin/goat" "$@"
fi

if command -v goat >/dev/null 2>&1; then
  exec goat "$@"
fi

echo "uv is required. See docs/install-uv.md (macOS/Linux: ./scripts/setup.sh, Windows: .\\scripts\\setup.ps1)" >&2
exit 127

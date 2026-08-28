#!/usr/bin/env bash
# Run the coboose CLI through uv when possible.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COBOOSE_ROOT="${COBOOSE_ROOT:-$ROOT}"

if command -v uv >/dev/null 2>&1 && [[ -f "$ROOT/uv.lock" || -f "$ROOT/pyproject.toml" ]]; then
  exec uv run --project "$ROOT" coboose "$@"
fi

if [[ -x "$ROOT/.venv/bin/coboose" ]]; then
  exec "$ROOT/.venv/bin/coboose" "$@"
fi

if command -v coboose >/dev/null 2>&1; then
  exec coboose "$@"
fi

echo "uv is required. See docs/install-uv.md (macOS/Linux: ./scripts/setup.sh, Windows: .\\scripts\\setup.ps1)" >&2
exit 127

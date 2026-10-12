#!/usr/bin/env bash
# Run the goat CLI. Do not `uv run goat`: a PATH shim of that name calls
# `uv run` again, and uv follows it until UV_RUN_RECURSION_DEPTH trips.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GOAT_ROOT="$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]] && "$ROOT/.venv/bin/python" -c "import goat" >/dev/null 2>&1; then
  exec "$ROOT/.venv/bin/python" -m goat "$@"
fi

if [[ -x "$ROOT/.venv/Scripts/python.exe" ]] && "$ROOT/.venv/Scripts/python.exe" -c "import goat" >/dev/null 2>&1; then
  exec "$ROOT/.venv/Scripts/python.exe" -m goat "$@"
fi

if command -v uv >/dev/null 2>&1 && [[ -f "$ROOT/pyproject.toml" ]]; then
  exec uv run --project "$ROOT" python -m goat "$@"
fi

echo "uv is required. See docs/install-uv.md (macOS/Linux: ./scripts/setup.sh, Windows: .\\scripts\\setup.ps1)" >&2
exit 127

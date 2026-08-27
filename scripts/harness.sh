#!/usr/bin/env bash
# Run the harness CLI through uv when possible.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HARNESS_ROOT="${HARNESS_ROOT:-$ROOT}"

if command -v uv >/dev/null 2>&1 && [[ -f "$ROOT/uv.lock" || -f "$ROOT/pyproject.toml" ]]; then
  exec uv run --project "$ROOT" harness "$@"
fi

if [[ -x "$ROOT/.venv/bin/harness" ]]; then
  exec "$ROOT/.venv/bin/harness" "$@"
fi

if command -v harness >/dev/null 2>&1; then
  exec harness "$@"
fi

echo "uv is required. Run ./scripts/setup.sh" >&2
exit 127

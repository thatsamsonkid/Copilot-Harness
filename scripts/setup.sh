#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv (macOS/Linux). Windows users should run .\\scripts\\setup.ps1 — see docs/install-uv.md"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

uv sync

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — fill in Jira values."
fi

uv run harness workspace generate
echo "Setup complete. First-run checklist:"
uv run harness init --format text || true

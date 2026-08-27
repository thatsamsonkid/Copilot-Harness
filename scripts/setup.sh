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
echo "Setup complete."
echo "Next:"
echo "  1. Create a Jira API token (docs/jira-api-token.md) and put email/token in .env"
echo "     or run: uv run harness init --interactive"
echo "  2. Edit repositories.yml, then ./scripts/clone-repos.sh"
echo "  3. In Copilot Chat: /get-started"
echo "Run the CLI with: uv run harness <command>"

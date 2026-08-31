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

uv run goat workspace generate
echo "Setup complete. First-run checklist:"
uv run goat init --format text || true
echo "Next:"
echo "  1. Create a Jira API token (docs/jira-api-token.md), set email/URL in .env,"
echo "     then run: uv run goat jira login"
echo "     (or: uv run goat init --interactive)"
echo "  2. Edit repositories.yml, then ./scripts/clone-repos.sh"
echo "  3. In Copilot Chat: /get-started"
echo "Run the CLI with: uv run goat <command>"
echo "From a sibling clone: uv run --project \"$ROOT\" goat <command>"
echo "  or: \"$ROOT/scripts/goat.sh\" <command>"

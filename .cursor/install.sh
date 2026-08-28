#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the Coboose.
# Installs uv (exposed on the system PATH), syncs the locked dependencies,
# and pre-generates the feature workspace files.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Install uv if it is not already available.
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$HOME/.local/bin" sh
fi

# Expose uv on the system PATH so every shell (and `uv run`) can find it,
# regardless of whether ~/.local/bin is on PATH.
UV_BIN="$(command -v uv || true)"
if [ -z "$UV_BIN" ] && [ -x "$HOME/.local/bin/uv" ]; then
  UV_BIN="$HOME/.local/bin/uv"
fi
if [ -n "$UV_BIN" ] && [ ! -e /usr/local/bin/uv ] && command -v sudo >/dev/null 2>&1; then
  sudo ln -sf "$UV_BIN" /usr/local/bin/uv || true
  [ -x "$(dirname "$UV_BIN")/uvx" ] && sudo ln -sf "$(dirname "$UV_BIN")/uvx" /usr/local/bin/uvx || true
fi
export PATH="$HOME/.local/bin:$PATH"

# Install locked dependencies into .venv (matches CI's `uv sync --frozen`).
uv sync --frozen

# Pre-generate the .code-workspace files so they are ready to open.
uv run coboose workspace generate >/dev/null

echo "Coboose environment ready. Run: uv run coboose <command>"

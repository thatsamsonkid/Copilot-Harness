#!/usr/bin/env bash
# Clone repositories.yml remotes under parent_dir (never inside this goat).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/scripts/goat.sh" clone "$@"

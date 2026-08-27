#!/usr/bin/env bash
# Clone repositories.yml remotes under parent_dir (never inside this harness).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/scripts/harness.sh" clone "$@"

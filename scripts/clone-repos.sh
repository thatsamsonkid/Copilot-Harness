#!/usr/bin/env bash
# Clone repositories.yml remotes as siblings of this harness (never inside it).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/scripts/harness.sh" clone "$@"

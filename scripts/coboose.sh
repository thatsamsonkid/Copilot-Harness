#!/usr/bin/env bash
# Backward-compatible alias. Prefer ./scripts/goat.sh
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/goat.sh" "$@"

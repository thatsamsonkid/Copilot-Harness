#!/usr/bin/env bash
# Clone a listed template from templates.yml as a sibling project.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/scripts/coboose.sh" bootstrap "$@"

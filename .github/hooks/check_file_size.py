#!/usr/bin/env python3
"""Copilot PreToolUse entry for check-file-size."""

from __future__ import annotations

import sys
from pathlib import Path


def _load():
    try:
        from goat.read_hooks import run_check_file_size
    except ImportError:
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / "src"))
        from read_hooks import run_check_file_size  # type: ignore
    return run_check_file_size


if __name__ == "__main__":
    try:
        raise SystemExit(_load()())
    except Exception:
        sys.stdout.write('{"permissionDecision":"allow"}\n')
        raise SystemExit(0)

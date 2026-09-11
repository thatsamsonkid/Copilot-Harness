#!/usr/bin/env python3
"""Arm /goat-implement and deny parent product-file edits (Code Writer must write them)."""

from __future__ import annotations

import sys
from pathlib import Path


def _load():
    try:
        from goat.implement_hooks import run_implement_gate
    except ImportError:
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / "src"))
        from implement_hooks import run_implement_gate  # type: ignore
    return run_implement_gate


if __name__ == "__main__":
    try:
        raise SystemExit(_load()())
    except Exception:
        sys.stdout.write('{"continue":true,"permissionDecision":"allow"}\n')
        raise SystemExit(0)

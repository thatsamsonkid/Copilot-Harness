#!/usr/bin/env python3
"""UserPromptSubmit: keep debugging / architecture / safety in the parent agent."""

from __future__ import annotations

import sys
from pathlib import Path


def _load():
    try:
        from goat.read_hooks import run_routing_context
    except ImportError:
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / "src"))
        from read_hooks import run_routing_context  # type: ignore
    return run_routing_context


if __name__ == "__main__":
    try:
        raise SystemExit(_load()())
    except Exception:
        sys.stdout.write('{"continue":true}\n')
        raise SystemExit(0)

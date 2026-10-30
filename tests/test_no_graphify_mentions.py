"""Graphify is gone except the migration note and the leftover-key warning."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEEDLES = ("graphify", "graph_report")
START = "graphify_removed_ok"
END = "graphify_removed_end"
SCAN_DIRS = ("src", ".github", "docs", "templates", "catalog")
SCAN_FILES = ("repositories.yml", "AGENTS.md", "README.md")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".venv"}


def _hits(text: str) -> list[tuple[int, str]]:
    skipping = False
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if START in lowered:
            if skipping:
                found.append((number, "nested GRAPHIFY_REMOVED_OK"))
            skipping = True
        if skipping:
            if END in lowered:
                skipping = False
            continue
        if any(needle in lowered for needle in NEEDLES):
            found.append((number, line.strip()))
    if skipping:
        found.append((0, "unclosed GRAPHIFY_REMOVED_OK block"))
    return found


def _scan_paths() -> list[Path]:
    paths: list[Path] = []
    for relative in SCAN_DIRS:
        root = ROOT / relative
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if SKIP_DIRS.intersection(path.parts):
                continue
            paths.append(path)
    for relative in SCAN_FILES:
        paths.append(ROOT / relative)
    return paths


def test_graphify_mentions_stay_inside_migration_note_and_warning():
    offenders: list[str] = []
    for path in _scan_paths():
        text = path.read_text(encoding="utf-8")
        for number, line in _hits(text):
            relative = path.relative_to(ROOT)
            offenders.append(f"{relative}:{number}: {line}")
    assert offenders == []

"""Always-on engineering principles stay short, attributed, and free of Cursor-only terms."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INSTRUCTIONS = ROOT / ".github" / "instructions" / "engineering-principles.instructions.md"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"

HEADINGS = (
    "## Laziness protocol",
    "## Subtract before you add",
    "## Fix root causes",
    "## Prove it works",
    "## Never block on the human",
    "## Guard the context window",
    "## Sequence verifiable units",
    "## Test behavior, not implementation",
    "## Migrate callers, then delete legacy APIs",
    "## Boundary discipline",
)

CURSOR_ONLY = (
    "subagent_type",
    "run_in_background",
    "Task tool",
    ".cursor/",
    "cloud agent",
)

ATTRIBUTION = "Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md"


def _split() -> tuple[dict, str]:
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    if body.startswith("\n"):
        body = body[1:]
    return meta, body


def test_instructions_file_applies_to_every_file():
    assert INSTRUCTIONS.is_file()
    meta, _body = _split()
    assert meta["applyTo"] == "**"
    assert isinstance(meta.get("description"), str)
    assert meta["description"].strip()


def test_body_is_at_most_60_lines():
    _meta, body = _split()
    assert len(body.splitlines()) <= 60


def test_each_principle_has_a_heading():
    _meta, body = _split()
    lines = [line.strip() for line in body.splitlines()]
    for heading in HEADINGS:
        assert heading in lines


def test_body_has_no_cursor_only_terms():
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    for term in CURSOR_ONLY:
        assert term not in text


def test_attribution_line_is_present():
    _meta, body = _split()
    assert ATTRIBUTION in body


def test_third_party_notices_include_the_mit_grant():
    text = NOTICES.read_text(encoding="utf-8")
    assert "Lauren Tan" in text
    assert "MIT" in text
    assert "Permission is hereby granted" in text
    assert "https://github.com/cursor/plugins/tree/main/pstack" in text

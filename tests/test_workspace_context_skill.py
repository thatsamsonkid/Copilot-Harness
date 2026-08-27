from __future__ import annotations

from pathlib import Path

import yaml

SKILL = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "skills"
    / "workspace-context"
    / "SKILL.md"
)


def _frontmatter_and_body() -> tuple[dict, str]:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def test_skill_name_matches_directory():
    meta, _ = _frontmatter_and_body()
    assert meta["name"] == SKILL.parent.name


def test_skill_covers_graphify_and_standards():
    meta, body = _frontmatter_and_body()
    description = meta["description"].lower()
    for token in ("graphify", "vague", "agents.md"):
        assert token in description
    lowered = body.lower()
    for token in (
        "uv run harness context",
        "graphify.report",
        "suggested_verify",
        "do not copy",
        "whole monorepo",
    ):
        assert token in lowered

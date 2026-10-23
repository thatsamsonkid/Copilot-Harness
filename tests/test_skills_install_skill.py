from __future__ import annotations

from pathlib import Path

import yaml

SKILL = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "skills"
    / "skills-install"
    / "SKILL.md"
)
SLASH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "skills"
    / "skills-install"
    / "SKILL.md"
)


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def test_skill_name_matches_directory():
    meta, _ = _frontmatter_and_body(SKILL)
    assert meta["name"] == SKILL.parent.name


def test_skill_description_covers_triggers():
    meta, _ = _frontmatter_and_body(SKILL)
    description = meta["description"].lower()
    for token in ("skills", "lift", "agents", "pull"):
        assert token in description
    assert meta.get("argument-hint")


def test_skill_body_is_the_cli_contract():
    _, body = _frontmatter_and_body(SKILL)
    lowered = body.lower()
    for token in (
        "uv run goat skills list",
        "--brief",
        "skills lift",
        "skills pull",
        "--only",
        "--all-skills",
        "needs_selection",
        "do not commit",
        "failed to spawn",
        "--project",
        "do not `git clone`",
        "first-party",
        "all",
    ):
        assert token in lowered


def test_slash_skill_is_user_triggered():
    meta, body = _frontmatter_and_body(SLASH)
    assert meta["name"] == "skills-install"
    assert meta.get("disable-model-invocation") is True
    assert "tools" not in meta
    assert "agent" not in meta
    lowered = body.lower()
    assert "skills list" in lowered
    assert "--brief" in lowered
    assert "skills lift" in lowered
    assert "--all-skills" in lowered
    assert "skills pull" in lowered

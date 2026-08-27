from __future__ import annotations

from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parents[1] / ".github" / "skills" / "jira-cli" / "SKILL.md"


def _frontmatter_and_body() -> tuple[dict, str]:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def test_skill_name_matches_directory():
    meta, _ = _frontmatter_and_body()
    assert meta["name"] == SKILL.parent.name


def test_skill_description_covers_triggers_and_forbidden_paths():
    meta, _ = _frontmatter_and_body()
    description = meta["description"]
    assert 1 <= len(description) <= 1024
    lowered = description.lower()
    for token in ("jira", "prepare", "harness", ".env", "mcp"):
        assert token in lowered
    assert meta.get("argument-hint") == "PROJ-123"


def test_skill_body_is_the_cli_contract():
    _, body = _frontmatter_and_body()
    lowered = body.lower()
    for token in (
        "uv run harness prepare",
        "jira get",
        "jira context",
        "jira search",
        "jira schema",
        "jira whoami",
        "harness init",
        "harness context",
        "routing.open_command",
        "jira.fields",
        "do not pass `--clone-missing`",
    ):
        assert token in lowered

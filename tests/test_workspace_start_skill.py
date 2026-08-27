from __future__ import annotations

from pathlib import Path

import yaml

SKILL = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "skills"
    / "workspace-start"
    / "SKILL.md"
)
PROMPT = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "prompts"
    / "start-workspace.prompt.md"
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


def test_skill_is_plan_then_sequential_start():
    meta, body = _frontmatter_and_body(SKILL)
    description = meta["description"].lower()
    for token in ("harness start", "angular", "java", "one"):
        assert token in description
    lowered = body.lower()
    for token in (
        "uv run harness start",
            "never launches",
        "one at a time",
        "proxy",
        "do not commit",
        "repositories.yml",
        "docker compose",
    ):
        assert token in lowered


def test_prompt_points_at_the_skill():
    meta, body = _frontmatter_and_body(PROMPT)
    assert meta["name"] == "start-workspace"
    lowered = body.lower()
    assert "workspace-start/skill.md" in lowered
    assert "harness start" in lowered
    assert "one process at a time" in lowered or "one at a time" in lowered

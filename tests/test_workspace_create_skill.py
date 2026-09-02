from __future__ import annotations

from pathlib import Path

import yaml

SKILL = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "skills"
    / "workspace-create"
    / "SKILL.md"
)
PROMPT = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "prompts"
    / "new-workspace.prompt.md"
)
AGENT = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "agents"
    / "workspace-creator.agent.md"
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
    for token in ("workspace", "menu", "repositories.yml", "commands", "skills"):
        assert token in description
    assert meta.get("argument-hint")


def test_skill_body_is_the_compact_picker_contract():
    _, body = _frontmatter_and_body(SKILL)
    lowered = body.lower()
    for token in (
        "workspace create --menu",
        "--no-prompt",
        "do not run `goat repos`",
        "goat commands",
        "goat skills list",
        "goat context",
        "goat workspace list",
        "more than 12",
        "tag:<tag>",
        "workspace.file",
        "open_command",
        "failed to spawn",
        "--project",
        "do not implement",
    ):
        assert token in lowered
    assert "goat repos --format json" not in lowered
    assert "goat workspace list --format json" not in lowered


def test_prompt_and_agent_point_at_the_skill():
    prompt_meta, prompt_body = _frontmatter_and_body(PROMPT)
    agent_meta, agent_body = _frontmatter_and_body(AGENT)
    assert prompt_meta["name"] == "new-workspace"
    assert agent_meta["name"] == "Workspace Creator"
    for body in (prompt_body, agent_body):
        lowered = body.lower()
        assert "workspace-create/skill.md" in lowered
        assert "workspace create --menu" in lowered
        assert "goat repos" in lowered
        assert "goat commands" in lowered
        assert "goat skills list" in lowered
        assert "do not" in lowered

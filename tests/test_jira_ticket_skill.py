from __future__ import annotations

from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parents[1] / ".github" / "skills" / "jira-ticket" / "SKILL.md"
PROMPT = Path(__file__).resolve().parents[1] / ".github" / "prompts" / "jira-ticket.prompt.md"


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} must start with YAML frontmatter"
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def test_skill_name_matches_directory():
    meta, _ = _frontmatter_and_body(SKILL)
    assert meta["name"] == SKILL.parent.name


def test_skill_description_covers_triggers_and_forbidden_paths():
    meta, _ = _frontmatter_and_body(SKILL)
    description = meta["description"]
    assert 1 <= len(description) <= 1024
    lowered = description.lower()
    for token in ("jira", "prepare", "/jira-ticket", ".env", "mcp"):
        assert token in lowered
    assert meta.get("argument-hint") == "PROJ-123"


def test_skill_is_planning_workflow_not_cli_catalog():
    _, body = _frontmatter_and_body(SKILL)
    lowered = body.lower()
    for token in (
        "jira-cli/skill.md",
        "uv run goat prepare",
        "routing.open_command",
        "done_when",
        "stop after the plan",
        "do not invent",
        "failed to spawn",
        "--project",
        "do not `cd`",
    ):
        assert token in lowered
    assert "jira mine" not in lowered


def test_prompt_targets_builtin_agent_and_skill():
    meta, body = _frontmatter_and_body(PROMPT)
    assert meta["name"] == "jira-ticket"
    assert meta.get("agent") == "agent"
    assert meta.get("argument-hint") == "PROJ-123"
    lowered = body.lower()
    assert "jira-ticket/skill.md" in lowered
    assert "jira-cli/skill.md" in lowered
    assert "${input:" not in body
    assert "agent: plan" not in body.lower()

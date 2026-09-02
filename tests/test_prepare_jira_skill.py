from __future__ import annotations

from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parents[1] / ".github" / "skills" / "prepare-jira" / "SKILL.md"
PROMPT = Path(__file__).resolve().parents[1] / ".github" / "prompts" / "prepare-jira.prompt.md"
GITIGNORE = Path(__file__).resolve().parents[1] / ".gitignore"
KEEP = Path(__file__).resolve().parents[1] / "jira-tickets" / ".gitkeep"


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} must start with YAML frontmatter"
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def test_skill_name_matches_directory():
    meta, _ = _frontmatter_and_body(SKILL)
    assert meta["name"] == SKILL.parent.name


def test_skill_description_covers_triggers():
    meta, _ = _frontmatter_and_body(SKILL)
    description = meta["description"]
    assert 1 <= len(description) <= 1024
    lowered = description.lower()
    for token in ("jira-tickets/", "templates/jira-ticket.md", "prepare-jira", ".env"):
        assert token in lowered


def test_skill_is_a_draft_walkthrough_not_jira_write():
    _, body = _frontmatter_and_body(SKILL)
    lowered = body.lower()
    for token in (
        "jira-tickets/",
        "templates/jira-ticket.md",
        "gitignored",
        "acceptance criteria",
        "out of scope",
        "role",
        "copy-paste",
        "not** `goat prepare`",
        "read-only",
        "do not invent",
        "catalog/stack.yaml",
        "no secrets",
    ):
        assert token in lowered


def test_prompt_points_at_the_skill_and_output_dir():
    meta, body = _frontmatter_and_body(PROMPT)
    assert meta["name"] == "prepare-jira"
    lowered = body.lower()
    for token in (
        ".github/skills/prepare-jira/skill.md",
        "templates/jira-ticket.md",
        "jira-tickets/",
        "goat prepare",
        "copy-paste",
    ):
        assert token in lowered


def test_jira_tickets_dir_is_gitignored_with_keep():
    text = GITIGNORE.read_text(encoding="utf-8")
    assert "jira-tickets/*.md" in text
    assert "!jira-tickets/.gitkeep" in text
    assert KEEP.exists()

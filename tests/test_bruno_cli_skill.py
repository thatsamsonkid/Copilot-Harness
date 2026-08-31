from __future__ import annotations

from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parents[1] / ".github" / "skills" / "bruno-cli" / "SKILL.md"
PROMPT = Path(__file__).resolve().parents[1] / ".github" / "prompts" / "bruno.prompt.md"
DOCS = Path(__file__).resolve().parents[1] / "docs" / "bruno.md"


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


def test_skill_description_covers_triggers_and_forbidden_paths():
    meta, _ = _frontmatter_and_body(SKILL)
    description = meta["description"]
    assert 1 <= len(description) <= 1024
    lowered = description.lower()
    for token in ("bruno", "bru", "collection", "goat", ".bru", "workflow"):
        assert token in lowered


def test_skill_body_is_the_cli_contract():
    _, body = _frontmatter_and_body(SKILL)
    lowered = body.lower()
    for token in (
        "uv run goat bruno collections",
        "bruno requests",
        "bruno envs",
        "bruno workflows",
        "bruno run",
        "bruno schema",
        "bru run",
        "--env-var",
        "never curl",
        "failed to spawn",
        "--project",
        "goat.workflows.yml",
        "clone_command",
        "npm install -g @usebruno/cli",
        "pick",
        "docs/bruno.md",
    ):
        assert token in lowered


def test_prompt_points_at_the_skill():
    meta, body = _frontmatter_and_body(PROMPT)
    assert meta["name"] == "bruno"
    lowered = body.lower()
    assert "bruno-cli/skill.md" in lowered
    assert "bruno collections" in lowered


def test_docs_explain_gap_versus_bru():
    text = DOCS.read_text(encoding="utf-8").lower()
    for token in (
        "repositories.yml",
        "tag `bruno`",
        "goat.workflows.yml",
        "goat.services.yml",
        "bru run",
        "--env-var",
        "never",
    ):
        assert token in text

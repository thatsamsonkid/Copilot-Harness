from __future__ import annotations

from pathlib import Path

import yaml

SKILL = (
    Path(__file__).resolve().parents[1] / ".github" / "skills" / "get-started" / "SKILL.md"
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


def test_skill_keeps_tokens_out_of_chat():
    meta, body = _frontmatter_and_body()
    description = meta["description"].lower()
    for token in ("token", ".env", "chat", "mcp"):
        assert token in description
    lowered = body.lower()
    for token in (
        "uv run goat init",
        "docs/jira-api-token.md",
        "never ask the user to paste a token",
        "init --interactive",
        "jira login",
        "env list",
        "catalog/env.yaml",
        "keychain",
        "docs/install-uv.md",
        "macos",
        "windows",
        "setup.ps1",
        "cannot spawn",
        "skills lift",
        "skills-install",
    ):
        assert token in lowered

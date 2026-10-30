"""Readiness Auditor is a dropdown agent. /ai-readiness is the user-typed slash."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / ".github" / "agents" / "readiness-auditor.agent.md"
SKILL = ROOT / ".github" / "skills" / "ai-readiness" / "SKILL.md"
CLI = ROOT / "docs" / "cli.md"

TOOLS = [
    "agent",
    "read",
    "search",
    "search/codebase",
    "search/usages",
    "runCommands",
]
GOAT_SUBCOMMAND = re.compile(r"\bgoat\s+([a-z][a-z0-9-]*)")
ALLOWED_GOAT = {"status", "context", "doctor"}


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} must start with YAML frontmatter"
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def test_readiness_auditor_frontmatter_is_dropdown_and_read_only():
    meta, body = _frontmatter_and_body(AGENT)
    assert meta["name"] == "Readiness Auditor"
    assert "user-invocable" not in meta
    assert meta.get("user-invocable") is not False
    assert meta["tools"] == TOOLS
    assert "edit" not in meta["tools"]
    assert meta["agents"] == ["Bulk Reader"]
    assert "model" not in meta
    assert "handoffs" not in meta
    lowered = body.lower()
    for token in (
        "read-only",
        "workspace.repos",
        "never read `.env`",
        "secrets/tokens",
        "uv run goat status --format json",
        "uv run goat context --format json",
        "uv run goat doctor",
        "python -m goat",
        "do not edit, create, or delete",
    ):
        assert token in lowered
    assert "graphify" not in lowered


def test_ai_readiness_skill_points_at_the_auditor():
    meta, body = _frontmatter_and_body(SKILL)
    assert meta["name"] == "ai-readiness"
    assert meta.get("disable-model-invocation") is True
    assert "tools" not in meta
    assert "agent" not in meta
    assert "model" not in meta
    lowered = body.lower()
    assert "follow `.github/agents/readiness-auditor.agent.md`" in lowered
    assert "readiness auditor" in lowered
    assert "workspace.repos" in lowered
    assert "do not edit, create, or delete" in lowered


def test_named_goat_subcommands_are_documented():
    cli = CLI.read_text(encoding="utf-8")
    named: set[str] = set()
    for path in (AGENT, SKILL):
        named.update(GOAT_SUBCOMMAND.findall(path.read_text(encoding="utf-8")))
    assert named == ALLOWED_GOAT
    for sub in sorted(named):
        assert f"goat {sub}" in cli


def test_docs_list_the_slash_and_the_agent():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    copilot = (ROOT / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    settings = yaml.safe_load((ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    for text in (agents, copilot, readme):
        assert "/ai-readiness" in text
    assert ".github/skills/ai-readiness/SKILL.md" in readme
    assert ".github/agents/readiness-auditor.agent.md" in readme
    assert "Readiness Auditor" in copilot
    assert "ai-readiness" in settings["chat.promptFilesRecommendations"]

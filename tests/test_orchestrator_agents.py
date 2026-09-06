from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / ".github" / "agents" / "bulk-reader.agent.md"
ORCHESTRATOR = ROOT / ".github" / "agents" / "orchestrator.agent.md"
PROMPT = ROOT / ".github" / "prompts" / "orchestrate.prompt.md"


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} must start with YAML frontmatter"
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def test_bulk_reader_is_a_hidden_read_only_subagent():
    meta, body = _frontmatter_and_body(READER)
    assert meta["name"] == "Bulk Reader"
    assert meta.get("user-invocable") is False
    assert meta.get("agents") == []
    tools = set(meta["tools"])
    assert "read" in tools
    assert "search/codebase" in tools
    assert "edit" not in tools
    assert "runCommands" not in tools
    assert "agent" not in tools
    lowered = body.lower()
    for token in (
        "precise code analyst",
        "structured bullets only",
        "no greetings",
        "no prose",
        "no preambles",
        "exact name, type, or line number",
        "nested bullets",
        "skip anything the caller did not ask for",
        "do not edit",
        "do not spawn other agents",
        "missing",
        ".env",
    ):
        assert token in lowered


def test_orchestrator_delegates_reads_to_bulk_reader():
    meta, body = _frontmatter_and_body(ORCHESTRATOR)
    assert meta["name"] == "Orchestrator"
    assert "agent" in meta["tools"]
    assert "read" not in meta["tools"]
    assert "edit" not in meta["tools"]
    assert meta["agents"] == ["Bulk Reader"]
    handoff_agents = {item["agent"] for item in meta["handoffs"]}
    assert handoff_agents == {"Implementer", "Reviewer"}
    lowered = body.lower()
    for token in (
        "bulk reader",
        "#tool:agent",
        "stateless",
        "uv run goat context",
        "workspace.repos",
        "do not edit",
        "planning/skill.md",
    ):
        assert token in lowered


def test_orchestrate_prompt_points_at_the_pair():
    meta, body = _frontmatter_and_body(PROMPT)
    assert meta["name"] == "orchestrate"
    lowered = body.lower()
    for token in (
        "orchestrator",
        "bulk reader",
        "#tool:agent",
        "goat context",
        "do not implement",
    ):
        assert token in lowered

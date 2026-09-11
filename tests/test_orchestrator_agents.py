from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / ".github" / "agents" / "bulk-reader.agent.md"
WRITER = ROOT / ".github" / "agents" / "code-writer.agent.md"
ORCHESTRATOR = ROOT / ".github" / "agents" / "orchestrator.agent.md"
PLANNER = ROOT / ".github" / "agents" / "jira-planner.agent.md"
IMPLEMENTER = ROOT / ".github" / "agents" / "implementer.agent.md"
VERIFIER = ROOT / ".github" / "agents" / "verifier.agent.md"
JIRA_PROMPT = ROOT / ".github" / "prompts" / "jira-ticket.prompt.md"
GOAT_IMPLEMENT = ROOT / ".github" / "prompts" / "goat-implement.prompt.md"
AUTO_MODEL = "Auto (copilot)"


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
    assert meta.get("model") == AUTO_MODEL
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
        "exact name, type, and `path:line`",
        "nested bullets",
        "skip anything the caller did not ask for",
        "do not edit",
        "do not spawn other agents",
        "missing",
        ".env",
    ):
        assert token in lowered


def test_code_writer_is_implementer_write_worker():
    meta, body = _frontmatter_and_body(WRITER)
    assert meta["name"] == "Code Writer"
    assert meta.get("user-invocable") is False
    assert meta.get("agents") == []
    assert meta.get("model") == AUTO_MODEL
    tools = set(meta["tools"])
    assert "edit" in tools
    assert "read" in tools
    assert "runCommands" not in tools
    assert "agent" not in tools
    lowered = body.lower()
    for token in (
        "you generate code files based on a spec and reference files",
        "match the existing patterns, conventions, naming, and style exactly",
        "output only the code",
        "no explanations",
        "no markdown fences unless asked",
        "if the spec is ambiguous",
        "reference code's patterns",
        "not a second implementer",
        "do not spawn other agents",
        "verifier",
        ".env",
        "tooling.generated",
    ):
        assert token in lowered


def test_verifier_is_implementer_verify_worker():
    meta, body = _frontmatter_and_body(VERIFIER)
    assert meta["name"] == "Verifier"
    assert meta.get("user-invocable") is False
    assert meta.get("agents") == []
    tools = set(meta["tools"])
    assert "runCommands" in tools
    assert "edit" not in tools
    assert "agent" not in tools
    lowered = body.lower()
    for token in (
        "verify worker",
        "not a second implementer",
        "not reviewer",
        "suggested_verify",
        "result: pass",
        "result: fail",
        "do not spawn other agents",
        "do not invent extra",
        "/goat-implement",
    ):
        assert token in lowered


def test_orchestrator_is_hidden_and_not_user_invocable():
    meta, body = _frontmatter_and_body(ORCHESTRATOR)
    assert meta["name"] == "Orchestrator"
    assert meta.get("user-invocable") is False
    assert "agent" in meta["tools"]
    assert "read" not in meta["tools"]
    assert "edit" not in meta["tools"]
    assert meta["agents"] == ["Bulk Reader", "Code Writer", "Verifier"]
    assert "handoffs" not in meta
    lowered = body.lower()
    for token in (
        "not user-invocable",
        "jira planner",
        "implementer",
        "do not invoke **code writer**",
        "do not invoke **verifier**",
        "bulk reader",
        "#tool:agent",
        "stateless",
        "auto (copilot)",
        "do not override the model",
    ):
        assert token in lowered


def test_jira_planner_auto_delegates_reads_not_writes():
    meta, body = _frontmatter_and_body(PLANNER)
    assert meta["name"] == "Jira Planner"
    assert "agent" in meta["tools"]
    assert meta["agents"] == ["Bulk Reader"]
    lowered = body.lower()
    for token in (
        "orchestration is automatic",
        "bulk reader",
        "do not invoke **code writer**",
        "do not edit product code",
        "do not spawn implementer",
        "you become implementer",
        "/goat-implement",
        "verifier",
        "debugging",
        "architectural decisions",
        "safety-critical",
        "auto (copilot)",
        "do not override the model",
    ):
        assert token in lowered


def test_implementer_owns_workflow_and_does_not_nest_when_already_a_subagent():
    meta, body = _frontmatter_and_body(IMPLEMENTER)
    assert meta["name"] == "Implementer"
    assert "agent" in meta["tools"]
    assert "edit" in meta["tools"]
    assert meta["agents"] == ["Bulk Reader", "Code Writer", "Verifier"]
    lowered = body.lower()
    for token in (
        "write worker",
        "verify worker",
        "not a second implementer",
        "goat branch",
        "suggested_verify",
        "feature-note.md",
        "#tool:agent",
        "targeted-",
        "debugging",
        "safety-critical",
        "do not nest agents",
        "write product files yourself",
        "subagents must not spawn",
        "wrote the plan in this chat",
        "/goat-implement",
        "your write worker",
        "verifier",
        "auto (copilot)",
        "do not override the model",
    ):
        assert token in lowered


def test_jira_ticket_prompt_uses_reader_not_writer():
    meta, body = _frontmatter_and_body(JIRA_PROMPT)
    assert meta["name"] == "jira-ticket"
    assert "agent" in meta.get("tools", [])
    lowered = body.lower()
    assert "bulk reader" in lowered
    assert "do not invoke **code writer**" in lowered
    assert "do not edit product code" in lowered
    assert "you become implementer" in lowered
    assert "do not spawn implementer" in lowered
    assert "/goat-implement" in lowered
    assert "verifier" in lowered
    assert "is the executor" in lowered or "you are the executor" in lowered
    assert "debugging" in lowered
    assert "safety-critical" in lowered
    assert "auto (copilot)" in lowered
    assert "do not override the model" in lowered


def test_goat_implement_prompt_requires_code_writer_and_verifier():
    meta, body = _frontmatter_and_body(GOAT_IMPLEMENT)
    assert meta["name"] == "goat-implement"
    assert "agent" in meta.get("tools", [])
    lowered = body.lower()
    for token in (
        "implementing/skill.md",
        "never spawn implementer",
        "you become implementer",
        "code writer",
        "verifier",
        "compaction",
        "goat branch",
        "done_when",
    ):
        assert token in lowered

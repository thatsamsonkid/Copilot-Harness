from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from goat.implement_hooks import (
    DENY_REASON,
    IMPLEMENT_CONTEXT,
    classify_prompt,
    decide,
    on_pre_compact,
    on_pre_tool,
    on_subagent_start,
    on_user_prompt,
)

HOOKS = Path(__file__).resolve().parents[1] / ".github" / "hooks"
GOAT_IMPLEMENT = (
    Path(__file__).resolve().parents[1] / ".github" / "prompts" / "goat-implement.prompt.md"
)
GOAT_PLAN = Path(__file__).resolve().parents[1] / ".github" / "prompts" / "goat-plan.prompt.md"
JIRA_TICKET = Path(__file__).resolve().parents[1] / ".github" / "prompts" / "jira-ticket.prompt.md"


def _goat(tmp_path: Path, *, plan: bool = False) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    tmp_path.joinpath("repositories.yml").write_text("repositories: []\n", encoding="utf-8")
    if plan:
        plans = tmp_path / "plans"
        plans.mkdir()
        plans.joinpath("2026-09-11-shop-1.plan.md").write_text("# plan\n", encoding="utf-8")
    return tmp_path


def _arm(root: Path, session: str = "s1") -> None:
    on_user_prompt(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": session,
            "prompt": "Start implementing an agreed plan. Load skills/implementing/SKILL.md",
        },
        goat_root=root,
    )


def test_classify_distinguishes_slash_command_from_planning_mentions():
    assert classify_prompt("/goat-implement SHOP-1", has_plan=False) == "arm"
    assert classify_prompt(GOAT_IMPLEMENT.read_text(encoding="utf-8"), has_plan=False) == "arm"
    assert classify_prompt(GOAT_PLAN.read_text(encoding="utf-8"), has_plan=True) == "ignore"
    assert classify_prompt(JIRA_TICKET.read_text(encoding="utf-8"), has_plan=True) == "ignore"
    assert classify_prompt("please implement the plan now", has_plan=True) == "arm"
    assert classify_prompt("please implement the plan now", has_plan=False) == "ignore"
    assert classify_prompt("click Implement plan to switch", has_plan=True) == "ignore"
    assert classify_prompt("/review SHOP-1", has_plan=True) == "disarm"


def test_user_prompt_arms_and_injects_context(tmp_path: Path):
    root = _goat(tmp_path)
    output = on_user_prompt(
        {
            "hookEventName": "UserPromptSubmit",
            "sessionId": "abc",
            "prompt": GOAT_IMPLEMENT.read_text(encoding="utf-8"),
        },
        goat_root=root,
    )
    assert IMPLEMENT_CONTEXT in output["additionalContext"]
    assert output["hookSpecificOutput"]["additionalContext"] == IMPLEMENT_CONTEXT
    lock = json.loads((root / ".goat" / "implement-lock.json").read_text(encoding="utf-8"))
    assert lock["sessions"]["abc"]["armed"] is True


def test_bare_implement_intent_arms_only_when_a_plan_file_exists(tmp_path: Path):
    empty = _goat(tmp_path / "empty", plan=False)
    planned = _goat(tmp_path / "planned", plan=True)
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "s",
        "prompt": "Ok, implement the plan.",
    }
    assert "additionalContext" not in on_user_prompt(payload, goat_root=empty)
    armed = on_user_prompt(payload, goat_root=planned)
    assert IMPLEMENT_CONTEXT in armed["additionalContext"]


def test_parent_product_edit_is_denied_when_armed(tmp_path: Path):
    root = _goat(tmp_path)
    _arm(root)
    sibling = tmp_path.parent / "shop-web"
    sibling.mkdir()
    target = sibling / "src" / "Bean.java"
    target.parent.mkdir(parents=True)
    target.write_text("class Bean {}\n", encoding="utf-8")
    decision = on_pre_tool(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "tool_name": "edit",
            "tool_input": {"file_path": str(target)},
            "cwd": str(root),
        },
        goat_root=root,
    )
    assert decision["permissionDecision"] == "deny"
    assert "Code Writer" in decision["permissionDecisionReason"]
    assert DENY_REASON in decision["permissionDecisionReason"]


def test_editfiles_list_is_denied(tmp_path: Path):
    root = _goat(tmp_path)
    _arm(root)
    decision = on_pre_tool(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "toolName": "editFiles",
            "toolArgs": {"files": ["../frontend/src/app.ts"]},
            "cwd": str(root),
        },
        goat_root=root,
    )
    assert decision["permissionDecision"] == "deny"


def test_code_writer_agent_type_may_edit_product_files(tmp_path: Path):
    root = _goat(tmp_path)
    _arm(root)
    decision = on_pre_tool(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "agent_type": "Code Writer",
            "tool_name": "edit",
            "tool_input": {"path": "../backend/src/Main.java"},
            "cwd": str(root),
        },
        goat_root=root,
    )
    assert decision["permissionDecision"] == "allow"


def test_subagent_start_allows_later_parent_looking_edits_from_writer(tmp_path: Path):
    root = _goat(tmp_path)
    _arm(root)
    on_subagent_start(
        {
            "hook_event_name": "SubagentStart",
            "session_id": "s1",
            "agent_type": "Code Writer",
        },
        goat_root=root,
    )
    decision = on_pre_tool(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "tool_name": "Write",
            "tool_input": {"path": "../api/src/Thing.java"},
            "cwd": str(root),
        },
        goat_root=root,
    )
    assert decision["permissionDecision"] == "allow"


def test_parent_may_edit_goat_and_feature_notes(tmp_path: Path):
    root = _goat(tmp_path)
    _arm(root)
    catalog = root / "catalog" / "stack.yaml"
    catalog.parent.mkdir()
    catalog.write_text("workspaces: []\n", encoding="utf-8")
    note = tmp_path.parent / "shop-web" / "docs" / "features" / "checkout.md"
    note.parent.mkdir(parents=True)
    note.write_text("# checkout\n", encoding="utf-8")
    for path in (catalog, note):
        decision = on_pre_tool(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "edit",
                "tool_input": {"file_path": str(path)},
                "cwd": str(root),
            },
            goat_root=root,
        )
        assert decision["permissionDecision"] == "allow", path


def test_unarmed_session_allows_product_edits(tmp_path: Path):
    root = _goat(tmp_path)
    decision = on_pre_tool(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "fresh",
            "tool_name": "edit",
            "tool_input": {"file_path": "../backend/src/A.java"},
            "cwd": str(root),
        },
        goat_root=root,
    )
    assert decision["permissionDecision"] == "allow"


def test_env_disables_the_edit_gate(tmp_path: Path):
    root = _goat(tmp_path)
    _arm(root)
    decision = on_pre_tool(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "tool_name": "edit",
            "tool_input": {"file_path": "../backend/src/A.java"},
            "cwd": str(root),
        },
        goat_root=root,
        environ={"GOAT_IMPLEMENT_EDIT_GATE": "off"},
    )
    assert decision["permissionDecision"] == "allow"


def test_precompact_reinjects_protocol_when_armed(tmp_path: Path):
    root = _goat(tmp_path)
    _arm(root)
    output = on_pre_compact(
        {"hook_event_name": "PreCompact", "session_id": "s1", "trigger": "auto"},
        goat_root=root,
    )
    assert IMPLEMENT_CONTEXT in output["additionalContext"]


def test_review_disarms_the_session(tmp_path: Path):
    root = _goat(tmp_path)
    _arm(root)
    on_user_prompt(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "prompt": "/review SHOP-1",
        },
        goat_root=root,
    )
    decision = on_pre_tool(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "tool_name": "edit",
            "tool_input": {"file_path": "../backend/src/A.java"},
            "cwd": str(root),
        },
        goat_root=root,
    )
    assert decision["permissionDecision"] == "allow"


def test_decide_dispatches_on_event_name(tmp_path: Path):
    root = _goat(tmp_path)
    output = decide(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "z",
            "prompt": "/goat-implement",
        },
        goat_root=root,
    )
    assert IMPLEMENT_CONTEXT in output["additionalContext"]


def test_hook_json_and_script_are_wired():
    data = json.loads((HOOKS / "implement-gate.json").read_text(encoding="utf-8"))
    events = data["hooks"]
    for name in (
        "UserPromptSubmit",
        "userPromptSubmitted",
        "PreToolUse",
        "preToolUse",
        "PreCompact",
        "preCompact",
        "SubagentStart",
        "subagentStart",
    ):
        assert name in events
    assert (HOOKS / "implement_gate.py").is_file()


def test_hook_script_emits_json(tmp_path: Path):
    root = _goat(tmp_path)
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "none",
            "tool_name": "edit",
            "tool_input": {"file_path": "README.md"},
            "cwd": str(root),
        }
    )
    import subprocess

    result = subprocess.run(
        [sys.executable, str(HOOKS / "implement_gate.py")],
        input=payload,
        text=True,
        capture_output=True,
        env={**os.environ, "GOAT_ROOT": str(root)},
        check=False,
    )
    assert result.returncode == 0
    body = json.loads(result.stdout)
    assert body.get("permissionDecision") == "allow" or body.get("continue") is True

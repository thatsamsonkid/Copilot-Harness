from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPILOT = ROOT / ".github" / "copilot-instructions.md"
AGENTS = ROOT / "AGENTS.md"


def test_copilot_instructions_do_not_require_a_plan_for_small_tasks():
    text = COPILOT.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "## when to write a plan" in lowered
    assert 'do **not** write an implementation plan' in lowered
    assert "just do this" in lowered
    assert "a jira key alone is not a request to write a plan" in lowered
    assert "skip the plan and implement" in lowered
    assert "write a plan covering impacted repos" not in lowered
    assert "do not implement until the user asks" not in lowered


def test_agents_md_does_not_treat_every_jira_key_as_a_plan():
    text = AGENTS.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "do not write a plan (chat or `plans/`) for small direct tasks" in lowered
    assert "and plan against those roots" not in text
    assert "do not write an implementation plan unless they asked" in lowered

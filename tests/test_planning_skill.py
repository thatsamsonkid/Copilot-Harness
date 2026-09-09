from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".github" / "skills" / "planning" / "SKILL.md"
TEMPLATE = ROOT / "templates" / "plan.md"
AGENTS = ROOT / "AGENTS.md"
COPILOT = ROOT / ".github" / "copilot-instructions.md"
GOAT_PLAN = ROOT / ".github" / "prompts" / "goat-plan.prompt.md"


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


def test_skill_targets_low_context_executors():
    meta, body = _frontmatter_and_body()
    description = meta["description"].lower()
    for token in ("plans/", "templates/plan.md", "executor"):
        assert token in description
    lowered = body.lower()
    for token in (
        "plans/",
        "templates/plan.md",
        "gitignored",
        "uv run goat prepare",
        "uv run goat context",
        "done_when",
        "file map",
        "repo-relative paths only",
        "exact file paths",
        "anchor by symbol",
        "model after",
        "preconditions",
        "exact commands",
        "expected result",
        "out of scope",
        "no secrets",
        "you are the executor",
        "do not spawn implementer",
        "must not spawn implementer",
        "you become implementer",
        "new chat",
        "code writer",
    ):
        assert token in lowered


def test_plan_template_has_required_sections():
    text = TEMPLATE.read_text(encoding="utf-8")
    for heading in (
        "## Objective",
        "## Context for the executor",
        "## Out of scope",
        "## Preconditions",
        "## File map",
        "## Steps",
        "## Verification",
        "## Done when",
        "## Risks and rollback",
    ):
        assert heading in text
    assert "- [ ]" in text
    assert "never a line number" in text
    assert "Model after:" in text
    assert "never absolute" in text
    assert "Never spawn Implementer" in text
    assert "you become Implementer" in text
    assert "Do not invoke Implementer or Code Writer" in text


def test_always_on_docs_support_same_chat_and_new_chat_implement_paths():
    """Never spawn Implementer. Same-chat planner uses Code Writer; new chat writes itself."""
    for path in (AGENTS, COPILOT, GOAT_PLAN):
        lowered = path.read_text(encoding="utf-8").lower()
        assert "never spawn implementer" in lowered or "do not spawn implementer" in lowered, path
        assert "become implementer" in lowered, path
        assert "code writer" in lowered, path
        assert (
            "you are the executor" in lowered
            or "is the executor" in lowered
            or "write product files yourself" in lowered
        ), path

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".github" / "skills" / "implementing" / "SKILL.md"
TEMPLATE = ROOT / "templates" / "plan.md"
AGENTS = ROOT / "AGENTS.md"
COPILOT = ROOT / ".github" / "copilot-instructions.md"
GOAT_IMPLEMENT = ROOT / ".github" / "prompts" / "goat-implement.prompt.md"
SETTINGS = ROOT / ".vscode" / "settings.json"


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


def test_skill_reloads_code_writer_and_verifier_after_compaction():
    meta, body = _frontmatter_and_body()
    description = meta["description"].lower()
    for token in ("/goat-implement", "code writer", "verifier", "compaction"):
        assert token in description
    lowered = body.lower()
    for token in (
        "compaction-proof",
        "never spawn implementer",
        "you become implementer",
        "code writer",
        "verifier",
        "#tool:agent",
        "goat branch",
        "done_when",
        "plans/",
        "suggested_verify",
        "do not nest",
        "/goat-plan",
        "feature-note.md",
        "parallel waves",
        "fan out",
        "wave",
    ):
        assert token in lowered


def test_prompt_points_at_the_skill():
    text = GOAT_IMPLEMENT.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert meta["name"] == "goat-implement"
    lowered = body.lower()
    assert "implementing/skill.md" in lowered
    assert "code writer" in lowered
    assert "verifier" in lowered
    assert "never spawn implementer" in lowered
    assert "parallel waves" in lowered
    assert "fan out" in lowered


def test_plan_template_and_always_on_docs_name_goat_implement():
    for path in (TEMPLATE, AGENTS, COPILOT):
        lowered = path.read_text(encoding="utf-8").lower()
        assert "/goat-implement" in lowered, path
        assert "verifier" in lowered, path


def test_vscode_recommends_goat_implement():
    settings = yaml.safe_load(SETTINGS.read_text(encoding="utf-8"))
    recs = settings["chat.promptFilesRecommendations"]
    assert "goat-implement" in recs
    assert "goat-plan" in recs

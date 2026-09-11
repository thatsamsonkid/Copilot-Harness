from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".github" / "skills" / "bulk-reader" / "SKILL.md"
PROMPT = ROOT / ".github" / "prompts" / "bulk-reader.prompt.md"
AGENT = ROOT / ".github" / "agents" / "bulk-reader.agent.md"


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def test_skill_name_matches_directory():
    meta, _ = _frontmatter_and_body(SKILL)
    assert meta["name"] == SKILL.parent.name


def test_skill_and_prompt_point_at_the_agent():
    skill_meta, skill_body = _frontmatter_and_body(SKILL)
    prompt_meta, prompt_body = _frontmatter_and_body(PROMPT)
    agent_meta, agent_body = _frontmatter_and_body(AGENT)
    assert skill_meta["name"] == "bulk-reader"
    assert prompt_meta["name"] == "bulk-reader"
    assert agent_meta["name"] == "Bulk Reader"
    assert agent_meta.get("model") == "Claude Haiku 4.5"
    for body in (skill_body, prompt_body):
        lowered = body.lower()
        assert "bulk reader" in lowered
        assert "#tool:agent" in lowered
        assert "debugging" in lowered
        assert "architectural" in lowered
        assert "safety-critical" in lowered
        assert "claude haiku 4.5" in lowered
        assert "do not override the model" in lowered
    assert "survey" in skill_body.lower()
    assert "do not reason about bugs" in agent_body.lower()
    assert "limit" in agent_body.lower()
    assert "350" in skill_body

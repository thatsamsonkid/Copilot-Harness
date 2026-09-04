from __future__ import annotations

from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parents[1] / ".github" / "skills" / "glossary" / "SKILL.md"
PROMPT = Path(__file__).resolve().parents[1] / ".github" / "prompts" / "glossary.prompt.md"


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "must start with YAML frontmatter"
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def test_skill_name_matches_directory():
    meta, _ = _frontmatter_and_body(SKILL)
    assert meta["name"] == SKILL.parent.name


def test_skill_keeps_glossary_out_of_product_wiki():
    meta, body = _frontmatter_and_body(SKILL)
    description = meta["description"].lower()
    for token in ("acronym", "language", "architecture"):
        assert token in description
    lowered = body.lower()
    for token in (
        "uv run goat glossary list",
        "glossary get",
        "glossary search",
        "glossary add",
        "catalog/glossary.yml",
        "docs/glossary.yml",
        "do not invent",
        "docs/features",
        "cannot spawn",
        "--meaning",
    ):
        assert token in lowered


def test_prompt_points_at_skill_and_get():
    meta, body = _frontmatter_and_body(PROMPT)
    assert meta["name"] == "glossary"
    lowered = body.lower()
    assert "skills/glossary/skill.md" in lowered
    assert "goat glossary get" in lowered
    assert "do not invent" in lowered

"""Former Copilot prompt slashes are user-triggered skills.

Knowledge skills stay agent-loadable. Prompt files are gone.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from goat.skills import parse_skill_frontmatter

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".github" / "skills"

# name -> argument-hint from the old prompt, or None when the prompt had none.
SLASH_SKILLS = {
    "bootstrap-project": "template-name new-folder",
    "bruno": "collection, request, or workflow",
    "bulk-reader": "survey question and file paths",
    "figma-frame": "https://www.figma.com/design/…",
    "get-started": None,
    "glossary": "TERM",
    "goat-implement": "PROJ-123",
    "goat-plan": "PROJ-123",
    "handoff": "PROJ-123",
    "jira-ticket": "PROJ-123",
    "new-workspace": "optional-id",
    "orient": "what area or ticket is this about?",
    "prepare-jira": "paste notes, Figma links, or a one-line ask",
    "review": "PROJ-123",
    "skills-install": "list | lift | pull <git-url>",
    "start-workspace": "optional workspace id or repo names",
}

AGENT_LOADABLE = (
    "jira-cli",
    "figma-cli",
    "bruno-cli",
    "workspace-context",
    "implementing",
    "planning",
    "workspace-create",
    "workspace-start",
)

INSTRUCTION_DOCS = (
    ROOT / "AGENTS.md",
    ROOT / ".github" / "copilot-instructions.md",
    ROOT / "README.md",
)


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    _, raw_meta, _body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta


def test_every_former_prompt_is_a_user_triggered_skill():
    for name, hint in SLASH_SKILLS.items():
        path = SKILLS / name / "SKILL.md"
        meta = _frontmatter(path)
        assert meta["name"] == name
        assert meta.get("disable-model-invocation") is True
        assert "tools" not in meta
        assert "agent" not in meta
        assert "model" not in meta
        description = meta.get("description") or ""
        assert 1 <= len(description) <= 1024
        if hint is None:
            assert not meta.get("argument-hint")
        else:
            assert meta.get("argument-hint") == hint
        parsed = parse_skill_frontmatter(path)
        assert parsed["name"] == name
        assert parsed["description"] == description
        assert parsed["argument_hint"] == (hint or "")
        assert "disable-model-invocation" not in parsed


def test_cli_knowledge_skills_stay_agent_loadable():
    for name in AGENT_LOADABLE:
        path = SKILLS / name / "SKILL.md"
        meta = _frontmatter(path)
        assert meta["name"] == name
        assert "disable-model-invocation" not in meta


def test_prompt_files_are_removed():
    prompts = ROOT / ".github" / "prompts"
    assert list(prompts.glob("*.prompt.md")) == []
    assert list(prompts.glob("*.md")) == []


def test_instruction_docs_do_not_cite_prompt_files():
    for path in INSTRUCTION_DOCS:
        text = path.read_text(encoding="utf-8")
        assert ".github/prompts/" not in text, path
        assert ".prompt.md" not in text, path
        assert "/goat-implement" in text

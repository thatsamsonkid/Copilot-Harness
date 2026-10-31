"""Six pstack slash skills stay user-triggered, attributed, and free of Cursor-only terms."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".github" / "skills"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"

PSTACK_SKILLS = (
    "benchmark-checklist",
    "blast-radius",
    "bro",
    "tdd",
    "technical-writing",
    "unslop",
)

ATTRIBUTION = "Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md"

CURSOR_ONLY = (
    "subagent_type",
    "run_in_background",
    "task tool",
    ".cursor/",
    "cloud agent",
    "poteto-mode",
    "setup-pstack",
)

_REPO_ROOTS = (
    ".github/",
    "templates/",
    "docs/",
    "plans/",
    "catalog/",
    "src/",
    "tests/",
)

_BARE_PATH = re.compile(
    r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.md|\.github/hooks|plans/)(?![\w./-])"
)


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def _repo_paths(text: str) -> list[str]:
    found: list[str] = []
    for token in re.findall(r"`([^`]+)`", text):
        if token.startswith("/") or any(char in token for char in " <>*|"):
            continue
        if token.endswith(".md") or token.startswith(_REPO_ROOTS):
            found.append(token)
    for token in _BARE_PATH.findall(text):
        if token.startswith(".") and not token.startswith(".github/"):
            continue
        if token not in found:
            found.append(token)
    return found


def test_each_pstack_skill_is_user_triggered_and_attributed():
    for name in PSTACK_SKILLS:
        path = SKILLS / name / "SKILL.md"
        meta, body = _frontmatter_and_body(path)
        assert meta["name"] == name
        assert meta.get("disable-model-invocation") is True
        assert "tools" not in meta
        assert "agent" not in meta
        assert ATTRIBUTION in body


def test_pstack_skills_have_no_cursor_only_terms():
    for name in PSTACK_SKILLS:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8").lower()
        for term in CURSOR_ONLY:
            assert term not in text, f"{name} contains {term}"


def test_repo_paths_named_by_pstack_skills_exist():
    for name in PSTACK_SKILLS:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        discovered = _repo_paths(text)
        assert "THIRD_PARTY_NOTICES.md" in discovered, name
        for token in discovered:
            path = ROOT / token.rstrip("/")
            assert path.exists(), f"{name} references missing {token}"


def test_third_party_notices_list_the_six_skills():
    text = NOTICES.read_text(encoding="utf-8")
    for name in PSTACK_SKILLS:
        assert f"/{name}" in text
        assert f".github/skills/{name}/SKILL.md" in text

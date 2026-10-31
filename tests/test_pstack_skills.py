"""pstack slash skills stay user-triggered, attributed, and free of Cursor-only terms."""

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
    "how",
    "tdd",
    "teach",
    "technical-writing",
    "unslop",
    "why",
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
    "pstack-models",
    "generalpurpose",
    "readonly: true",
    "mcps/",
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
        description = str(meta.get("description") or "").lower()
        for phrase in ("use only when", "use when", "use for ", "or when"):
            assert phrase not in description, f"{name} description routes the model: {phrase}"


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


_GOAT_FLAGS = re.compile(
    r"\bgoat\s+([a-z][a-z0-9-]*)((?:\s+--[a-z0-9-]+(?:\s+<[^>\s]+>)?)*)"
)


def _mentioned_goat_flags(text: str) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for match in _GOAT_FLAGS.finditer(text):
        command = match.group(1)
        for flag in re.findall(r"--[a-z0-9-]+", match.group(2)):
            found.add((command, flag))
    return found


def _command_flag_section(docs: str, command: str) -> str:
    marker = f"### `goat {command}`"
    start = docs.find(marker)
    assert start != -1, f"docs/cli.md has no flags section for goat {command}"
    rest = docs[start:]
    nxt = re.search(r"\n### |\n## ", rest[len(marker) :])
    end = len(marker) + nxt.start() if nxt else len(rest)
    return rest[:end]


def test_pstack_skill_goat_flags_are_in_cli_docs():
    """Scoped to the pstack skills. Repo-wide flag mentions are a larger catalog."""
    docs = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    seen: set[tuple[str, str]] = set()
    for name in PSTACK_SKILLS:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        seen |= _mentioned_goat_flags(text)
    assert seen, "expected the pstack skills to name goat flags"
    for command, flag in sorted(seen):
        section = _command_flag_section(docs, command)
        assert flag in section, f"goat {command} {flag} is not in docs/cli.md"


def test_third_party_notices_list_every_pstack_skill():
    text = NOTICES.read_text(encoding="utf-8")
    for name in PSTACK_SKILLS:
        assert f"/{name}" in text
        assert f".github/skills/{name}/SKILL.md" in text


_SUBAGENT_RULE = (
    "If you were started as a subagent other than Orchestrator, "
    "do every read yourself and do not invoke Bulk Reader."
)


def test_how_surveys_with_bulk_reader_then_rereads():
    text = (SKILLS / "how" / "SKILL.md").read_text(encoding="utf-8")
    assert "Bulk Reader" in text
    assert "path:line" in text
    assert "re-read" in text
    assert _SUBAGENT_RULE in text
    context_at = text.index("goat context")
    knowledge_at = text.index("knowledge.files")
    search_at = text.index("search/codebase")
    assert context_at < search_at
    assert knowledge_at < search_at


_WHY_SKIPPED = (
    "chat",
    "docs platform",
    "observability",
    "error tracking",
    "analytics",
)


def _skipped_near(text: str, category: str) -> bool:
    lowered = text.lower()
    start = 0
    while True:
        at = lowered.find(category, start)
        if at < 0:
            return False
        if "skipped" in lowered[at : at + 200]:
            return True
        start = at + len(category)


def test_why_marks_missing_harness_sources_skipped():
    text = (SKILLS / "why" / "SKILL.md").read_text(encoding="utf-8")
    assert "Sources Consulted" in text
    assert _SUBAGENT_RULE in text
    for category in _WHY_SKIPPED:
        assert _skipped_near(text, category), category
    invoked = re.findall(r"`git [^`]+`", text) + re.findall(r"(?m)^git .+$", text)
    assert invoked, "expected git commands"
    for command in invoked:
        assert command.startswith(("`git -C ", "git -C ")), command


def test_teach_follows_how_then_why_in_this_chat():
    text = (SKILLS / "teach" / "SKILL.md").read_text(encoding="utf-8")
    how_at = text.index(".github/skills/how/SKILL.md")
    why_at = text.index(".github/skills/why/SKILL.md")
    assert how_at < why_at
    assert "in this chat" in text
    assert "sequential" in text.lower()
    assert _SUBAGENT_RULE in text
    assert "Do not hand either skill to a subagent." in text
    assert "Bulk Reader survey calls remain allowed" in text
    assert "/unslop" in text

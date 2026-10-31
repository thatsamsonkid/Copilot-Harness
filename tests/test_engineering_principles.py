"""Engineering principles stay short, attributed, and free of Cursor-only terms."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INSTRUCTIONS = ROOT / ".github" / "instructions" / "engineering-principles.instructions.md"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"

HEADINGS = (
    "## Laziness protocol",
    "## Subtract before you add",
    "## Fix root causes",
    "## Prove it works",
    "## Never block on the human",
    "## Guard the context window",
    "## Sequence verifiable units",
    "## Test behavior, not implementation",
    "## Migrate callers, then delete legacy APIs",
    "## Boundary discipline",
)

CURSOR_ONLY = (
    "subagent_type",
    "run_in_background",
    "Task tool",
    ".cursor/",
    "cloud agent",
)

ATTRIBUTION = "Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md"

# Verbatim pstack LICENSE (MIT). Copyright (c) 2026 Lauren Tan.
PSTACK_MIT = """\
MIT License

Copyright (c) 2026 Lauren Tan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

_REPO_ROOTS = (".github/", "templates/", "docs/", "plans/", "catalog/", "src/", "tests/")


def _split() -> tuple[dict, str]:
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    if body.startswith("\n"):
        body = body[1:]
    return meta, body


_BARE_PATH = re.compile(
    r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.md|\.github/hooks|plans/)(?![\w./-])"
)


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


def _agent_files() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in (ROOT / ".github" / "agents").glob("*.agent.md"):
        raw = path.read_text(encoding="utf-8")
        assert raw.startswith("---\n"), path
        _, raw_meta, _body = raw.split("---", 2)
        meta = yaml.safe_load(raw_meta)
        assert isinstance(meta, dict)
        name = meta.get("name")
        assert isinstance(name, str) and name.strip()
        found[name] = path
    return found


def test_instructions_file_applies_to_every_file():
    assert INSTRUCTIONS.is_file()
    meta, _body = _split()
    assert meta["applyTo"] == "**"
    description = meta.get("description")
    assert isinstance(description, str)
    assert description.strip()
    lowered = description.lower()
    assert "planning" in lowered
    assert "drafting" in lowered


def test_body_is_at_most_60_lines():
    _meta, body = _split()
    assert len(body.splitlines()) <= 60


def test_each_principle_has_a_heading():
    _meta, body = _split()
    lines = [line.strip() for line in body.splitlines()]
    for heading in HEADINGS:
        assert heading in lines


def test_body_has_no_cursor_only_terms():
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    for term in CURSOR_ONLY:
        assert term not in text


def test_attribution_line_is_present():
    _meta, body = _split()
    assert ATTRIBUTION in body


def test_third_party_notices_include_the_mit_license_verbatim():
    text = NOTICES.read_text(encoding="utf-8")
    assert PSTACK_MIT in text
    assert "https://github.com/cursor/plugins/tree/main/pstack" in text
    assert "pstack" in text


def test_named_repo_paths_and_agents_exist():
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    discovered = _repo_paths(text)
    for required in (
        "templates/plan.md",
        ".github/hooks",
        ".github/skills/bulk-reader/SKILL.md",
        "docs/cli.md",
        "AGENTS.md",
    ):
        assert required in discovered
    for token in discovered:
        path = ROOT / token.rstrip("/")
        assert path.exists(), token

    _meta, body = _split()
    agents = _agent_files()
    prose = re.sub(r"`[^`]*`", " ", body)
    mentioned = [
        name
        for name in agents
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", prose)
    ]
    assert "Verifier" in mentioned
    assert "Bulk Reader" in mentioned
    for name in mentioned:
        assert agents[name].is_file()
        assert agents[name] == ROOT / ".github" / "agents" / f"{name.lower().replace(' ', '-')}.agent.md"
    for name in re.findall(r"\*\*([^*\n]+)\*\*", prose):
        assert name in agents
        assert agents[name].is_file()

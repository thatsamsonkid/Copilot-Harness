from __future__ import annotations

from pathlib import Path

import pytest

from goat.done import (
    ACCEPTANCE_HEADING_RE,
    CHECKBOX_RE,
    NEXT_HEADING_RE,
    extract_acceptance,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "jira-ticket.md"
JIRA_TEMPLATE_DIR = ROOT / "templates" / "jira"
TYPED_TEMPLATES = sorted(JIRA_TEMPLATE_DIR.glob("*.md"))

SHARED_HEADINGS = (
    "## Context",
    "## Goal",
    "## Surfaces",
    "## Out of scope",
    "## Verification",
    "## Pointers",
)


def test_jira_ticket_template_has_required_sections():
    text = TEMPLATE.read_text(encoding="utf-8")
    for heading in (
        "## Context",
        "## Goal",
        "## Surfaces",
        "## Acceptance Criteria",
        "## Out of scope",
        "## Constraints",
        "## Verification",
        "## Pointers",
        "### Figma frames",
    ):
        assert heading in text
    assert "goat prepare" in text
    assert "{id, url}" in text
    assert "do not list clone folder names" in text.lower() or "Not repo folder names" in text
    assert "**Role:**" in text
    assert "**Frame:**" in text
    assert "**Context:**" in text
    for role in ("default", "loading", "success", "error / declined", "empty"):
        assert f"**Role:** {role}" in text
    assert text.count("**Frame:** https://www.figma.com/design/") >= 5
    assert "Checkout-errors" in text


def test_acceptance_heading_is_parsed_into_done_when():
    items = extract_acceptance({"description": TEMPLATE.read_text(encoding="utf-8")})
    assert "Guest can complete payment without an account" in items
    assert "Receipt email is sent within 1 minute of success" in items
    assert "Failed card shows the inline error, not a blank page" in items


def test_only_acceptance_checkboxes_are_lifted():
    items = extract_acceptance({"description": TEMPLATE.read_text(encoding="utf-8")})
    assert len(items) == 3
    assert all("as discussed" not in item.lower() for item in items)


def _acceptance_spans(text: str) -> list[tuple[int, int]]:
    lines = text.splitlines()
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        if not ACCEPTANCE_HEADING_RE.match(lines[index].strip()):
            index += 1
            continue
        start = index
        end = len(lines)
        for follow in range(index + 1, len(lines)):
            if NEXT_HEADING_RE.match(lines[follow].strip()):
                end = follow
                break
        spans.append((start, end))
        index = end
    return spans


def _checkbox_items(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        match = CHECKBOX_RE.match(line)
        if match:
            items.append(match.group(1).strip())
    return items


def _section(text: str, heading: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    assert start is not None, heading
    end = len(lines)
    for follow in range(start, len(lines)):
        if NEXT_HEADING_RE.match(lines[follow].strip()):
            end = follow
            break
    return "\n".join(lines[start:end])


@pytest.mark.parametrize("path", TYPED_TEMPLATES, ids=lambda path: path.name)
def test_typed_template_has_shared_headings(path: Path):
    text = path.read_text(encoding="utf-8")
    for heading in SHARED_HEADINGS:
        assert heading in text, path.name
    assert _acceptance_spans(text), path.name
    assert "local" not in path.parts


@pytest.mark.parametrize("path", TYPED_TEMPLATES, ids=lambda path: path.name)
def test_typed_template_acceptance_extracts(path: Path):
    text = path.read_text(encoding="utf-8")
    items = extract_acceptance({"description": text})
    assert len(items) >= 1
    assert items == _checkbox_items(text)


@pytest.mark.parametrize("path", TYPED_TEMPLATES, ids=lambda path: path.name)
def test_typed_template_checkboxes_only_under_acceptance(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    spans = _acceptance_spans(text)
    assert spans, path.name
    for index, line in enumerate(lines):
        if "- [ ]" in line or CHECKBOX_RE.match(line):
            inside = any(start < index < end for start, end in spans)
            assert inside, f"{path.name}:{index + 1} checkbox outside acceptance heading"


def test_story_and_bug_keep_figma_frames_by_role():
    for name in ("story.md", "bug.md"):
        text = (JIRA_TEMPLATE_DIR / name).read_text(encoding="utf-8")
        assert "### Figma frames" in text
        assert "{id, url}" in text
        for label in ("**Role:**", "**Frame:**", "**Context:**"):
            assert label in text


def test_bug_steps_are_numbered_not_checkboxes():
    text = (JIRA_TEMPLATE_DIR / "bug.md").read_text(encoding="utf-8")
    assert "## Expected vs actual" in text
    assert "## Environment" in text
    steps = _section(text, "## Steps to reproduce")
    for number in ("1.", "2.", "3."):
        assert number in steps
    assert "- [ ]" not in steps
    assert all(CHECKBOX_RE.match(line) is None for line in steps.splitlines())


def test_spike_uses_done_when_without_figma_frames():
    text = (JIRA_TEMPLATE_DIR / "spike.md").read_text(encoding="utf-8")
    assert "## Question" in text
    assert "## Timebox" in text
    assert "## Done when" in text
    assert "### Figma frames" not in text
    items = extract_acceptance({"description": text})
    assert len(items) >= 1
    assert all(item for item in items)

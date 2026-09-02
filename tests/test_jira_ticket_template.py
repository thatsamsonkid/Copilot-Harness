from __future__ import annotations

from pathlib import Path

from goat.done import extract_acceptance

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "jira-ticket.md"


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


def test_acceptance_heading_is_parsed_into_done_when():
    items = extract_acceptance({"description": TEMPLATE.read_text(encoding="utf-8")})
    assert "Guest can complete payment without an account" in items
    assert "Receipt email is sent within 1 minute of success" in items
    assert "Failed card shows the inline error, not a blank page" in items


def test_only_acceptance_checkboxes_are_lifted():
    items = extract_acceptance({"description": TEMPLATE.read_text(encoding="utf-8")})
    assert len(items) == 3
    assert all("as discussed" not in item.lower() for item in items)

from __future__ import annotations

from coboose.done import build_done_when, extract_acceptance


def test_extract_acceptance_from_heading_and_checkboxes():
    description = """
# Summary
Ship checkout.

## Acceptance Criteria
- [ ] Guest can pay
- [x] Receipt email is sent

## Notes
Ignore this.
"""
    assert extract_acceptance({"description": description}) == [
        "Guest can pay",
        "Receipt email is sent",
    ]


def test_extract_acceptance_from_aliased_field():
    issue = {
        "description": "No AC heading",
        "acceptance_criteria": "Users see a toast\nAnd the cart updates",
    }
    found = extract_acceptance(issue)
    assert "Users see a toast" in found or found == ["Users see a toast\nAnd the cart updates"]


def test_build_done_when_includes_ticket_verify_and_invariants():
    issue = {
        "description": "## Acceptance Criteria\n- [ ] Button is aligned",
    }
    repos = [
        {
            "id": "frontend",
            "tooling": {"suggested_verify": ["pnpm lint", "pnpm test"]},
        }
    ]
    items = build_done_when(issue, repos)
    texts = [item["text"] for item in items]
    assert "Button is aligned" in texts
    assert "In frontend: pnpm lint" in texts
    assert any("one pull request per sibling" in text.lower() for text in texts)
    assert {item["source"] for item in items} >= {"ticket", "verify", "coboose"}

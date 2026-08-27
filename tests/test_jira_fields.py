from harness.jira_fields import JiraSettings, project_issue


def test_project_issue_keeps_allowlist_only():
    settings = JiraSettings(fields=["key", "summary", "status"])
    projected = project_issue(
        {
            "key": "WEB-1",
            "summary": "Fix",
            "status": "To Do",
            "description": "secret-ish extra",
            "reporter": "Al",
            "id": "10001",
            "custom": {},
        },
        settings,
    )
    assert projected == {"key": "WEB-1", "summary": "Fix", "status": "To Do"}


def test_custom_alias_requires_field_and_extra():
    settings = JiraSettings(
        fields=["key", "story_points"],
        extra_fields=["customfield_10016"],
        field_aliases={"customfield_10016": "story_points"},
        include_comments=False,
    )
    projected = project_issue(
        {
            "key": "WEB-1",
            "summary": "Fix",
            "custom": {"story_points": 3, "customfield_10016": 3},
        },
        settings,
    )
    assert projected["story_points"] == 3
    assert "custom" not in projected
    assert "summary" not in projected


def test_comments_omitted_when_disabled():
    settings = JiraSettings(fields=["key", "comments"], include_comments=False)
    projected = project_issue(
        {"key": "WEB-1", "comments": [{"body": "hi"}]},
        settings,
    )
    assert "comments" not in projected

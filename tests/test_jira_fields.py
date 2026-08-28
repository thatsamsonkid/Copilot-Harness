from coboose.jira_fields import JiraSettings, project_issue


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


def test_shapes_clip_nested_objects_and_drop_empty():
    settings = JiraSettings(
        fields=["key", "project", "parent", "comments", "labels"],
        shapes={
            "project": ["key"],
            "parent": ["key", "summary"],
            "comments": ["author", "body"],
        },
        include_comments=True,
        drop_empty=True,
    )
    projected = project_issue(
        {
            "key": "WEB-1",
            "project": {"key": "WEB", "name": "Web", "id": "10000"},
            "parent": None,
            "labels": [],
            "comments": [
                {
                    "id": "1",
                    "author": "Ada",
                    "created": "2026-01-01",
                    "updated": "2026-01-02",
                    "body": "Ship it",
                }
            ],
            "custom": {},
        },
        settings,
    )
    assert projected == {
        "key": "WEB-1",
        "project": {"key": "WEB"},
        "comments": [{"author": "Ada", "body": "Ship it"}],
    }


def test_schema_exposes_projection_config():
    schema = JiraSettings(fields=["key", "summary"], include_comments=False).schema()
    assert schema["fields"] == ["key", "summary"]
    assert "project" in schema["shapes"]
    assert "key" in schema["search_fields"]
    assert schema["drop_empty"] is True

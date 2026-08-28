import pytest

from coboose import CobooseError
from coboose.projection import ProjectionSpec, project


def test_project_keeps_allowlist_order_and_drops_unknown_keys():
    spec = ProjectionSpec(fields=("key", "summary", "status"))
    assert project(
        {
            "id": "10001",
            "key": "WEB-1",
            "summary": "Fix",
            "status": "To Do",
            "reporter": "Al",
            "watchers": [{"accountId": "secret"}],
        },
        spec,
    ) == {"key": "WEB-1", "summary": "Fix", "status": "To Do"}


def test_project_clips_nested_dicts_and_lists_via_shapes():
    spec = ProjectionSpec(
        fields=("key", "project", "comments"),
        shapes={
            "project": ("key",),
            "comments": ("author", "body"),
        },
        drop_empty=False,
    )
    projected = project(
        {
            "key": "WEB-1",
            "project": {"key": "WEB", "name": "Web", "id": "10000"},
            "comments": [
                {
                    "id": "9",
                    "author": "Ada",
                    "updated": "2026-01-01",
                    "body": "Ship it",
                }
            ],
        },
        spec,
    )
    assert projected == {
        "key": "WEB-1",
        "project": {"key": "WEB"},
        "comments": [{"author": "Ada", "body": "Ship it"}],
    }


def test_project_drops_empty_values_when_configured():
    spec = ProjectionSpec(
        fields=("key", "labels", "parent", "issuelinks", "description"),
        drop_empty=True,
    )
    assert project(
        {
            "key": "WEB-1",
            "labels": [],
            "parent": None,
            "issuelinks": [],
            "description": "",
        },
        spec,
    ) == {"key": "WEB-1"}


def test_from_mapping_overlays_shapes_and_defaults():
    spec = ProjectionSpec.from_mapping(
        {
            "fields": ["key", "comments"],
            "shapes": {"comments": ["author", "body"]},
            "drop_empty": False,
        },
        name="demo",
        default_fields=["unused"],
        default_shapes={"project": ("key", "name"), "comments": ("id",)},
    )
    assert spec.fields == ("key", "comments")
    assert spec.shapes["project"] == ("key", "name")
    assert spec.shapes["comments"] == ("author", "body")
    assert spec.drop_empty is False
    assert spec.nested("comments", ("id",)).fields == ("author", "body")


def test_from_mapping_rejects_non_mapping_shapes():
    with pytest.raises(CobooseError, match="shapes must be a mapping"):
        ProjectionSpec.from_mapping({"fields": ["key"], "shapes": ["project"]}, name="jira")

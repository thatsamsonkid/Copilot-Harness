from __future__ import annotations

import yaml

from harness import HarnessError
from harness.catalog import Workspace, WorkspaceMatch
from harness.stack_edit import format_workspace_yaml, upsert_workspace_text
import pytest


def _workspace(**kwargs) -> Workspace:
    defaults = {
        "id": "checkout",
        "name": "Checkout",
        "description": "Cart and checkout",
        "folders": ["frontend", "backend"],
        "tags": [],
        "include_harness": True,
        "fallback": False,
        "match": WorkspaceMatch(keywords=["cart"]),
    }
    defaults.update(kwargs)
    return Workspace(**defaults)


def test_format_workspace_yaml_matches_catalog_style():
    text = format_workspace_yaml(_workspace())
    assert text.startswith("  - id: checkout\n")
    assert "folders: [frontend, backend]" in text
    assert "keywords: [cart]" in text
    parsed = yaml.safe_load("workspaces:\n" + text)
    assert parsed["workspaces"][0]["id"] == "checkout"


def test_append_to_handwritten_stack():
    original = (
        "# keep me\n"
        "workspaces:\n"
        "  - id: frontend\n"
        "    name: Frontend\n"
        "    folders: [frontend]\n"
    )
    updated = upsert_workspace_text(original, _workspace())
    assert updated.startswith("# keep me\n")
    assert "    folders: [frontend]\n\n  - id: checkout\n" in updated
    data = yaml.safe_load(updated)
    assert [item["id"] for item in data["workspaces"]] == ["frontend", "checkout"]


def test_append_to_pyyaml_dumped_stack():
    original = yaml.safe_dump(
        {
            "workspaces": [
                {"id": "frontend", "name": "Frontend", "folders": ["frontend"]}
            ]
        },
        sort_keys=False,
    )
    updated = upsert_workspace_text(original, _workspace())
    data = yaml.safe_load(updated)
    assert [item["id"] for item in data["workspaces"]] == ["frontend", "checkout"]


def test_replace_existing_workspace():
    original = (
        "workspaces:\n"
        "  - id: checkout\n"
        "    name: Old\n"
        "    folders: [frontend]\n"
        "  - id: backend\n"
        "    name: Backend\n"
        "    folders: [backend]\n"
    )
    with pytest.raises(HarnessError, match="already exists"):
        upsert_workspace_text(original, _workspace())
    updated = upsert_workspace_text(original, _workspace(), replace=True)
    data = yaml.safe_load(updated)
    assert data["workspaces"][0]["name"] == "Checkout"
    assert data["workspaces"][0]["folders"] == ["frontend", "backend"]
    assert data["workspaces"][1]["id"] == "backend"


def test_empty_workspaces_list():
    updated = upsert_workspace_text("workspaces: []\n", _workspace())
    data = yaml.safe_load(updated)
    assert data["workspaces"][0]["id"] == "checkout"


def test_adds_workspaces_key_when_missing():
    updated = upsert_workspace_text("jira:\n  include_comments: true\n", _workspace())
    data = yaml.safe_load(updated)
    assert "jira" in data
    assert data["workspaces"][0]["id"] == "checkout"

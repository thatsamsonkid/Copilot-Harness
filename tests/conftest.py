from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import load_test_catalog, write_harness_config


@pytest.fixture
def sample_catalog_data() -> dict:
    return {
        "parent_dir": "..",
        "jira": {"extra_fields": ["customfield_10016"]},
        "repos": [
            {
                "name": "frontend",
                "url": "https://github.com/acme/frontend.git",
                "path": "frontend",
                "default_branch": "main",
                "description": "UI",
                "tags": ["ui"],
            },
            {
                "name": "backend",
                "url": "https://github.com/acme/backend.git",
                "path": "backend",
                "default_branch": "main",
                "description": "API",
                "tags": ["api"],
            },
        ],
        "templates": [
            {
                "name": "web-starter",
                "url": "https://github.com/acme/web-starter.git",
                "tags": ["frontend", "web"],
                "description": "Web starter",
                "language": "typescript",
                "kind": "frontend",
            },
            {
                "name": "api-starter",
                "url": "https://github.com/acme/api-starter.git",
                "tags": ["backend", "api"],
                "description": "API starter",
                "language": "python",
                "kind": "backend",
            },
        ],
        "workspaces": [
            {
                "id": "frontend",
                "name": "Frontend",
                "folders": ["frontend", "backend"],
                "match": {
                    "projects": ["WEB"],
                    "components": ["Frontend"],
                    "labels": ["ui"],
                    "keywords": ["button", "css"],
                },
            },
            {
                "id": "backend",
                "name": "Backend",
                "folders": ["backend"],
                "fallback": True,
                "match": {
                    "projects": ["API"],
                    "components": ["Backend"],
                    "labels": ["api"],
                    "keywords": ["endpoint"],
                },
            },
        ],
    }


@pytest.fixture
def harness_root(tmp_path: Path, sample_catalog_data: dict) -> Path:
    root = tmp_path / "parent" / "Copilot-Harness"
    write_harness_config(root, sample_catalog_data)
    return root


@pytest.fixture
def catalog(harness_root: Path):
    return load_test_catalog(harness_root)

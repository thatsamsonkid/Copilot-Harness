from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness.catalog import load_catalog


def write_catalog(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def sample_catalog_data() -> dict:
    return {
        "parent_dir": "..",
        "jira": {"extra_fields": ["customfield_10016"]},
        "repos": [
            {
                "id": "frontend",
                "url": "https://github.com/acme/frontend.git",
                "path": "frontend",
                "default_branch": "main",
                "description": "UI",
                "tags": ["ui"],
            },
            {
                "id": "backend",
                "url": "https://github.com/acme/backend.git",
                "path": "backend",
                "default_branch": "main",
                "description": "API",
                "tags": ["api"],
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
    write_catalog(root / "catalog" / "stack.yaml", sample_catalog_data)
    return root


@pytest.fixture
def catalog(harness_root: Path):
    return load_catalog(harness_root / "catalog" / "stack.yaml")

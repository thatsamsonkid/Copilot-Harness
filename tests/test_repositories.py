from pathlib import Path

import pytest

from goat import GoatError
from goat.catalog import load_catalog, load_repositories
from goat.clone import clone_repos
from tests.helpers import write_goat_config, write_yaml


def test_repositories_yml_is_the_manifest(goat_root: Path):
    catalog = load_catalog(goat_root)
    assert catalog.repos_source == goat_root / "repositories.yml"
    assert [repo.name for repo in catalog.repos] == ["frontend", "backend"]
    assert catalog.repo("frontend").tags == ["ui"]


def test_accepts_clone_url_alias(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0].pop("url")
    sample_catalog_data["repos"][0]["clone_url"] = "https://github.com/acme/web.git"
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.repo("frontend").url == "https://github.com/acme/web.git"


def test_accepts_top_level_list_manifest(tmp_path: Path):
    path = write_yaml(
        tmp_path / "repositories.yml",
        [
            {
                "name": "api",
                "url": "https://github.com/acme/api.git",
                "tags": ["api"],
            }
        ],
    )
    repos, parent_dir = load_repositories(path)
    assert parent_dir == ".."
    assert repos[0].name == "api"
    assert repos[0].path == "api"


def test_requires_name_url_and_tags(tmp_path: Path):
    path = write_yaml(
        tmp_path / "repositories.yml",
        {"repositories": [{"name": "frontend", "url": "https://example.invalid/x.git"}]},
    )
    with pytest.raises(GoatError, match="at least one tag"):
        load_repositories(path)


def test_rejects_repos_key_in_stack(tmp_path: Path, sample_catalog_data: dict):
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    write_yaml(
        root / "catalog" / "stack.yaml",
        {"repos": [{"name": "frontend"}], "workspaces": []},
    )
    with pytest.raises(GoatError, match="must not list repositories"):
        load_catalog(root)


def test_clone_filters_by_tag(catalog, goat_root: Path):
    result = clone_repos(catalog, goat_root, tags=["ui"], dry_run=True)
    assert [item["id"] for item in result] == ["frontend"]


def test_group_defaults_path_under_parent_dir(tmp_path: Path):
    path = write_yaml(
        tmp_path / "repositories.yml",
        {
            "parent_dir": "..",
            "repositories": [
                {
                    "name": "shop-web",
                    "url": "https://github.com/acme/shop-web.git",
                    "tags": ["ui"],
                    "group": "frontend",
                },
                {
                    "name": "tokens",
                    "url": "https://github.com/acme/tokens.git",
                    "tags": ["shared"],
                    "path": "shared/tokens",
                },
            ],
        },
    )
    repos, parent_dir = load_repositories(path)
    assert parent_dir == ".."
    assert repos[0].path == "frontend/shop-web"
    assert repos[0].group == "frontend"
    assert repos[1].path == "shared/tokens"


def test_workspace_folders_from_tags(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["workspaces"].append(
        {
            "id": "all-tagged",
            "name": "All",
            "tags": ["ui", "api"],
            "folders": [],
        }
    )
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.workspace_repo_names("all-tagged") == ["frontend", "backend"]

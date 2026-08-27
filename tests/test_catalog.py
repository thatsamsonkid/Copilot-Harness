from pathlib import Path

import pytest

from harness import HarnessError
from harness.catalog import catalog_to_dict, load_catalog
from harness.paths import find_harness_root
from tests.helpers import write_harness_config


def test_load_and_resolve_sibling_paths(catalog, harness_root: Path):
    assert catalog.repo("frontend").url.endswith("frontend.git")
    assert catalog.repo("frontend").name == "frontend"
    assert catalog.sibling_root(harness_root) == harness_root.parent
    assert catalog.repo_path(harness_root, "backend") == harness_root.parent / "backend"
    assert catalog.workspace_repo_names("frontend") == ["frontend", "backend"]


def test_rejects_unknown_workspace_folder(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["workspaces"][0]["folders"] = ["frontend", "missing"]
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    with pytest.raises(HarnessError, match="unknown repo"):
        load_catalog(root)


def test_rejects_nested_repo_path(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["path"] = "../escape"
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    with pytest.raises(HarnessError, match="sibling folder"):
        load_catalog(root)


def test_find_harness_root_from_nested_cwd(harness_root: Path, monkeypatch: pytest.MonkeyPatch):
    nested = harness_root / "src" / "harness"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("HARNESS_ROOT", raising=False)
    assert find_harness_root() == harness_root.resolve()


def test_parses_graphify_out_and_rejects_parent_escape(
    tmp_path: Path, sample_catalog_data: dict
):
    sample_catalog_data["repos"][0]["graphify"] = {"out": "docs/graphify-out"}
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.repo("frontend").graphify.out == "docs/graphify-out"
    assert catalog.repo("frontend").graphify.enabled is True

    sample_catalog_data["repos"][0]["graphify"] = {"out": "../escape"}
    write_harness_config(root, sample_catalog_data)
    with pytest.raises(HarnessError, match="relative path"):
        load_catalog(root)


def test_parses_knowledge_dirs(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["knowledge"] = {"dirs": ["handbook"]}
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.repo("frontend").knowledge_dirs == ("handbook",)


def test_catalog_to_dict_marks_placeholders(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["url"] = "git@github.com:YOUR_ORG/frontend.git"
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    payload = catalog_to_dict(catalog, root)
    assert payload["repos_source"].endswith("repositories.yml")
    assert payload["repos"][0]["placeholder"] is True
    assert payload["repos"][1]["placeholder"] is False
    assert payload["templates_source"].endswith("templates.yml")
    assert [item["name"] for item in payload["templates"]] == [
        "web-starter",
        "api-starter",
    ]

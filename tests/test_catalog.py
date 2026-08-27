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


def test_rejects_parent_escape_repo_path(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["path"] = "../escape"
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    with pytest.raises(HarnessError, match="parent_dir"):
        load_catalog(root)


def test_accepts_group_and_nested_path(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["name"] = "shop-web"
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0].pop("path", None)
    sample_catalog_data["repos"][1]["name"] = "api"
    sample_catalog_data["repos"][1]["path"] = "backend/api"
    sample_catalog_data["workspaces"][0]["folders"] = ["shop-web", "api"]
    sample_catalog_data["workspaces"][1]["folders"] = ["api"]
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.repo("shop-web").path == "frontend/shop-web"
    assert catalog.repo("shop-web").group == "frontend"
    assert catalog.repo("api").path == "backend/api"
    assert catalog.repo_path(root, "shop-web") == root.parent / "frontend" / "shop-web"
    payload = catalog_to_dict(catalog, root)
    assert payload["repos"][0]["group"] == "frontend"
    assert payload["repos"][0]["path"] == "frontend/shop-web"


def test_rejects_inconsistent_group_and_path(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0]["path"] = "backend/web"
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    with pytest.raises(HarnessError, match="inside group"):
        load_catalog(root)


def test_rejects_path_prefix_collision(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["path"] = "frontend"
    sample_catalog_data["repos"][1]["path"] = "frontend/shop-web"
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    with pytest.raises(HarnessError, match="collide"):
        load_catalog(root)


def test_rejects_slash_in_repo_name(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["name"] = "frontend/shop-web"
    sample_catalog_data["workspaces"][0]["folders"] = ["frontend/shop-web", "backend"]
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    with pytest.raises(HarnessError, match="single id"):
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


def test_parses_verify_commands_and_rejects_blank(
    tmp_path: Path, sample_catalog_data: dict
):
    sample_catalog_data["repos"][0]["verify"] = "./gradlew check"
    sample_catalog_data["repos"][1]["verify"] = ["just test", "just lint"]
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.repo("frontend").verify == ["./gradlew check"]
    assert catalog.repo("backend").verify == ["just test", "just lint"]
    payload = catalog_to_dict(catalog, root)
    assert payload["repos"][0]["verify"] == ["./gradlew check"]

    sample_catalog_data["repos"][0]["verify"] = [" "]
    write_harness_config(root, sample_catalog_data)
    with pytest.raises(HarnessError, match="non-empty single-line"):
        load_catalog(root)


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

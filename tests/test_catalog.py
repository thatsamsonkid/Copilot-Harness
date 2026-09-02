from pathlib import Path

import pytest

from goat import GoatError
from goat.catalog import catalog_to_dict, load_catalog
from goat.paths import find_goat_root
from tests.helpers import write_goat_config


def test_load_and_resolve_sibling_paths(catalog, goat_root: Path):
    assert catalog.repo("frontend").url.endswith("frontend.git")
    assert catalog.repo("frontend").name == "frontend"
    assert catalog.sibling_root(goat_root) == goat_root.parent
    assert catalog.repo_path(goat_root, "backend") == goat_root.parent / "backend"
    assert catalog.workspace_repo_names("frontend") == ["frontend", "backend"]


def test_rejects_unknown_workspace_folder(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["workspaces"][0]["folders"] = ["frontend", "missing"]
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    with pytest.raises(GoatError, match="unknown repo"):
        load_catalog(root)


def test_rejects_parent_escape_repo_path(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["path"] = "../escape"
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    with pytest.raises(GoatError, match="parent_dir"):
        load_catalog(root)


def test_accepts_group_and_nested_path(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["name"] = "shop-web"
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0].pop("path", None)
    sample_catalog_data["repos"][1]["name"] = "api"
    sample_catalog_data["repos"][1]["path"] = "backend/api"
    sample_catalog_data["workspaces"][0]["folders"] = ["shop-web", "api"]
    sample_catalog_data["workspaces"][1]["folders"] = ["api"]
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
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
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    with pytest.raises(GoatError, match="inside group"):
        load_catalog(root)


def test_rejects_path_prefix_collision(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["path"] = "frontend"
    sample_catalog_data["repos"][1]["path"] = "frontend/shop-web"
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    with pytest.raises(GoatError, match="collide"):
        load_catalog(root)


def test_rejects_slash_in_repo_name(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["name"] = "frontend/shop-web"
    sample_catalog_data["workspaces"][0]["folders"] = ["frontend/shop-web", "backend"]
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    with pytest.raises(GoatError, match="single id"):
        load_catalog(root)


def test_find_goat_root_from_nested_cwd(goat_root: Path, monkeypatch: pytest.MonkeyPatch):
    nested = goat_root / "src"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("GOAT_ROOT", raising=False)
    monkeypatch.delenv("COBOOSE_ROOT", raising=False)
    assert find_goat_root() == goat_root.resolve()


def test_find_goat_root_accepts_legacy_env(
    goat_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GOAT_ROOT", raising=False)
    monkeypatch.setenv("COBOOSE_ROOT", str(goat_root))
    assert find_goat_root() == goat_root.resolve()


def test_include_coboose_yaml_still_works(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["workspaces"][0]["include_coboose"] = False
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.workspace("frontend").include_goat is False
    assert catalog.workspace("backend").include_goat is True


def test_parses_graphify_out_and_rejects_parent_escape(
    tmp_path: Path, sample_catalog_data: dict
):
    sample_catalog_data["repos"][0]["graphify"] = {"out": "docs/graphify-out"}
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.repo("frontend").graphify.out == "docs/graphify-out"
    assert catalog.repo("frontend").graphify.enabled is True

    sample_catalog_data["repos"][0]["graphify"] = {"out": "../escape"}
    write_goat_config(root, sample_catalog_data)
    with pytest.raises(GoatError, match="relative path"):
        load_catalog(root)


def test_parses_knowledge_dirs(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["knowledge"] = {"dirs": ["handbook"]}
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.repo("frontend").knowledge_dirs == ("handbook",)



def test_loads_jira_projection_from_stack(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["jira"] = {
        "fields": ["key", "summary", "comments"],
        "search_fields": ["key", "summary"],
        "shapes": {"comments": ["author", "body"]},
        "include_comments": True,
        "drop_empty": False,
        "extra_fields": ["customfield_10016"],
        "field_aliases": {"customfield_10016": "story_points"},
    }
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.jira.output_fields() == ["key", "summary", "comments"]
    assert catalog.jira.search_fields == ["key", "summary"]
    assert catalog.jira.shapes["comments"] == ["author", "body"]
    assert catalog.jira.shapes["project"] == ["key", "name"]
    assert catalog.jira.drop_empty is False
    schema = catalog.jira.schema()
    assert schema["field_aliases"]["customfield_10016"] == "story_points"


def test_loads_figma_projection_from_stack(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["figma"] = {
        "fields": ["file_key", "images"],
        "shapes": {"images": ["id", "url"], "comments": ["author", "message"]},
        "default_format": "jpg",
        "default_scale": 1,
        "max_ids": 3,
        "include_comments": False,
        "max_comments": 5,
        "default_depth": 1,
        "max_depth": 2,
        "drop_empty": False,
    }
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.figma.output_fields() == ["file_key", "images"]
    assert catalog.figma.default_format == "jpg"
    assert catalog.figma.default_scale == 1.0
    assert catalog.figma.max_ids == 3
    assert catalog.figma.shapes["images"] == ["id", "url"]
    assert catalog.figma.shapes["comments"] == ["author", "message"]
    schema = catalog.figma.schema()
    assert schema["drop_empty"] is False
    assert schema["include_comments"] is False
    assert schema["max_comments"] == 5
    assert schema["default_depth"] == 1
    assert schema["max_depth"] == 2
    assert schema["raw_nodes"] is True


def test_loads_bruno_settings_from_stack(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"].append(
        {
            "name": "api-collections",
            "url": "https://github.com/acme/api-collections.git",
            "tags": ["bruno"],
        }
    )
    sample_catalog_data["bruno"] = {
        "repos": ["api-collections"],
        "default_env": "staging",
        "services": [{"id": "cart", "collection": "cart-api", "env": "staging"}],
    }
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.bruno.repos == ["api-collections"]
    assert catalog.bruno.default_env == "staging"
    assert catalog.bruno.tags == ["bruno"]
    assert catalog.bruno.services[0].id == "cart"
    schema = catalog.bruno.schema()
    assert "request_template" in schema
    assert schema["workflows_file"] == "goat.workflows.yml"


def test_parses_optional_repo_language(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["language"] = "typescript"
    sample_catalog_data["repos"][1]["language"] = "java"
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.repo("frontend").language == "typescript"
    assert catalog.repo("backend").language == "java"
    payload = catalog_to_dict(catalog, root)
    assert payload["repos"][0]["language"] == "typescript"


def test_catalog_to_dict_marks_placeholders(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["url"] = "git@github.com:YOUR_ORG/frontend.git"
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
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

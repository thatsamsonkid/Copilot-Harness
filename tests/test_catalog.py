from pathlib import Path

import pytest

from coboose import CobooseError
from coboose.catalog import catalog_to_dict, load_catalog
from coboose.paths import find_coboose_root
from tests.helpers import write_coboose_config


def test_load_and_resolve_sibling_paths(catalog, coboose_root: Path):
    assert catalog.repo("frontend").url.endswith("frontend.git")
    assert catalog.repo("frontend").name == "frontend"
    assert catalog.sibling_root(coboose_root) == coboose_root.parent
    assert catalog.repo_path(coboose_root, "backend") == coboose_root.parent / "backend"
    assert catalog.workspace_repo_names("frontend") == ["frontend", "backend"]


def test_rejects_unknown_workspace_folder(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["workspaces"][0]["folders"] = ["frontend", "missing"]
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
    with pytest.raises(CobooseError, match="unknown repo"):
        load_catalog(root)


def test_rejects_parent_escape_repo_path(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["path"] = "../escape"
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
    with pytest.raises(CobooseError, match="parent_dir"):
        load_catalog(root)


def test_accepts_group_and_nested_path(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["name"] = "shop-web"
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0].pop("path", None)
    sample_catalog_data["repos"][1]["name"] = "api"
    sample_catalog_data["repos"][1]["path"] = "backend/api"
    sample_catalog_data["workspaces"][0]["folders"] = ["shop-web", "api"]
    sample_catalog_data["workspaces"][1]["folders"] = ["api"]
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
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
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
    with pytest.raises(CobooseError, match="inside group"):
        load_catalog(root)


def test_rejects_path_prefix_collision(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["path"] = "frontend"
    sample_catalog_data["repos"][1]["path"] = "frontend/shop-web"
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
    with pytest.raises(CobooseError, match="collide"):
        load_catalog(root)


def test_rejects_slash_in_repo_name(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["name"] = "frontend/shop-web"
    sample_catalog_data["workspaces"][0]["folders"] = ["frontend/shop-web", "backend"]
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
    with pytest.raises(CobooseError, match="single id"):
        load_catalog(root)


def test_find_coboose_root_from_nested_cwd(coboose_root: Path, monkeypatch: pytest.MonkeyPatch):
    nested = coboose_root / "src" / "coboose"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("COBOOSE_ROOT", raising=False)
    assert find_coboose_root() == coboose_root.resolve()


def test_parses_graphify_out_and_rejects_parent_escape(
    tmp_path: Path, sample_catalog_data: dict
):
    sample_catalog_data["repos"][0]["graphify"] = {"out": "docs/graphify-out"}
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.repo("frontend").graphify.out == "docs/graphify-out"
    assert catalog.repo("frontend").graphify.enabled is True

    sample_catalog_data["repos"][0]["graphify"] = {"out": "../escape"}
    write_coboose_config(root, sample_catalog_data)
    with pytest.raises(CobooseError, match="relative path"):
        load_catalog(root)


def test_parses_knowledge_dirs(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["knowledge"] = {"dirs": ["handbook"]}
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.repo("frontend").knowledge_dirs == ("handbook",)


def test_load_catalog_discovers_personal_workspaces(catalog, coboose_root: Path):
    from coboose.prompt import PromptSession
    from coboose.workspace_create import create_workspace

    create_workspace(
        catalog,
        coboose_root,
        workspace_id="scratch",
        name="Scratch",
        folders=["backend"],
        personal=True,
        prompt=PromptSession(interactive=False),
    )
    # Shared id wins if a colliding personal file appears later.
    colliding = coboose_root / "workspaces" / "personal" / "frontend.code-workspace"
    colliding.parent.mkdir(parents=True, exist_ok=True)
    colliding.write_text("{}", encoding="utf-8")
    (coboose_root / "workspaces" / "personal" / "broken.code-workspace").write_text(
        "not-json", encoding="utf-8"
    )

    refreshed = load_catalog(coboose_root)
    payload = catalog_to_dict(refreshed, coboose_root)
    by_id = {item["id"]: item for item in payload["workspaces"]}
    assert by_id["scratch"]["personal"] is True
    assert by_id["scratch"]["folders"] == ["backend"]
    assert by_id["frontend"]["personal"] is False
    assert "broken" not in by_id


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
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
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
        "fields": ["file_key", "err", "images", "status"],
        "default_format": "jpg",
        "default_scale": 1,
        "max_ids": 3,
        "drop_empty": False,
    }
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    assert catalog.figma.output_fields() == ["file_key", "err", "images", "status"]
    assert catalog.figma.default_format == "jpg"
    assert catalog.figma.default_scale == 1.0
    assert catalog.figma.max_ids == 3
    assert "images" not in catalog.figma.shapes
    schema = catalog.figma.schema()
    assert schema["drop_empty"] is False


def test_catalog_to_dict_marks_placeholders(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["url"] = "git@github.com:YOUR_ORG/frontend.git"
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
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

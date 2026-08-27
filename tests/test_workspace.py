from pathlib import Path

from harness.catalog import load_catalog
from harness.workspace import generate_workspaces, list_workspaces, workspace_document
from tests.helpers import write_harness_config


def test_workspace_paths_point_at_siblings(catalog, harness_root: Path):
    document = workspace_document(catalog, harness_root, catalog.workspace("frontend"))
    names = [folder["name"] for folder in document["folders"]]
    assert names == ["harness", "frontend", "backend"]
    assert document["folders"][0]["path"] == ".."
    assert document["folders"][1]["path"] == "../../frontend"
    assert document["folders"][2]["path"] == "../../backend"


def test_workspace_paths_for_grouped_repos(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["name"] = "shop-web"
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0].pop("path", None)
    sample_catalog_data["repos"][1]["path"] = "backend/api"
    sample_catalog_data["workspaces"][0]["folders"] = ["shop-web", "backend"]
    root = tmp_path / "parent" / "Copilot-Harness"
    write_harness_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    document = workspace_document(catalog, root, catalog.workspace("frontend"))
    names = [folder["name"] for folder in document["folders"]]
    assert names == ["harness", "shop-web", "backend"]
    assert document["folders"][1]["path"] == "../../frontend/shop-web"
    assert document["folders"][2]["path"] == "../../backend/api"


def test_generate_and_list(catalog, harness_root: Path):
    written = generate_workspaces(catalog, harness_root)
    assert {item["id"] for item in written} == {"frontend", "backend"}
    path = harness_root / "workspaces" / "frontend.code-workspace"
    assert path.exists()
    listed = list_workspaces(catalog, harness_root)
    frontend = next(item for item in listed if item["id"] == "frontend")
    assert frontend["exists"] is True
    assert frontend["repos"][0]["cloned"] is False

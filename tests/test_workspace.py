import json
from pathlib import Path

from harness.catalog import load_catalog
from harness.prompt import PromptSession
from harness.start import collect_start_plan
from harness.workspace import generate_workspaces, list_workspaces, workspace_document
from harness.workspace_create import create_workspace
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
    assert frontend["personal"] is False
    assert frontend["repos"][0]["cloned"] is False
    assert frontend["start_file"].endswith("workspaces/frontend.start.yml")
    assert frontend["start_plan"] is False

    collect_start_plan(catalog, harness_root, workspace_id="frontend", save=True)
    start_path = harness_root / "workspaces" / "frontend.start.yml"
    original = start_path.read_text(encoding="utf-8")
    generate_workspaces(catalog, harness_root)
    assert start_path.read_text(encoding="utf-8") == original
    listed = list_workspaces(catalog, harness_root)
    frontend = next(item for item in listed if item["id"] == "frontend")
    assert frontend["start_plan"] is True


def test_generate_skips_personal_and_list_includes_them(catalog, harness_root: Path):
    create_workspace(
        catalog,
        harness_root,
        workspace_id="scratch",
        folders=["frontend"],
        personal=True,
        prompt=PromptSession(interactive=False),
    )
    personal_path = harness_root / "workspaces" / "personal" / "scratch.code-workspace"
    original = personal_path.read_text(encoding="utf-8")
    document = json.loads(original)
    document["harness"]["description"] = "do not overwrite"
    personal_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    refreshed = load_catalog(harness_root)
    written = generate_workspaces(refreshed, harness_root)
    assert {item["id"] for item in written} == {"frontend", "backend"}
    assert all(item["personal"] is False for item in written)
    assert not (harness_root / "workspaces" / "scratch.code-workspace").exists()
    assert personal_path.read_text(encoding="utf-8") == json.dumps(document, indent=2) + "\n"

    listed = list_workspaces(refreshed, harness_root)
    scratch = next(item for item in listed if item["id"] == "scratch")
    assert scratch["personal"] is True
    assert scratch["exists"] is True
    assert scratch["file"] == str(personal_path)

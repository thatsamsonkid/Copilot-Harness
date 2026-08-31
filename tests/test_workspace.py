import json
from pathlib import Path

from goat.catalog import load_catalog, parse_personal_workspace
from goat.prompt import PromptSession
from goat.start import collect_start_plan
from goat.workspace import generate_workspaces, list_workspaces, workspace_document
from goat.workspace_create import create_workspace
from tests.helpers import write_goat_config


def test_workspace_paths_point_at_siblings(catalog, goat_root: Path):
    document = workspace_document(catalog, goat_root, catalog.workspace("frontend"))
    names = [folder["name"] for folder in document["folders"]]
    assert names == ["goat", "frontend", "backend"]
    assert document["folders"][0]["path"] == ".."
    assert document["folders"][1]["path"] == "../../frontend"
    assert document["folders"][2]["path"] == "../../backend"
    assert (
        document["settings"]["terminal.integrated.env.linux"]["GOAT_ROOT"]
        == "${workspaceFolder:goat}"
    )
    assert (
        document["settings"]["terminal.integrated.env.osx"]["GOAT_ROOT"]
        == "${workspaceFolder:goat}"
    )
    assert document["settings"]["terminal.integrated.env.linux"]["GOAT_WORKSPACE"] == "frontend"
    assert (
        document["settings"]["terminal.integrated.env.linux"]["GOAT_WORKSPACE_FILE"]
        == "${workspaceFile}"
    )
    assert document["goat"]["id"] == "frontend"
    assert document["goat"]["folders"] == ["frontend", "backend"]
    assert "HARNESS_ROOT" not in document["settings"]["terminal.integrated.env.linux"]
    assert "UV_PROJECT" not in document["settings"]["terminal.integrated.env.linux"]


def test_workspace_paths_for_grouped_repos(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["name"] = "shop-web"
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0].pop("path", None)
    sample_catalog_data["repos"][1]["path"] = "backend/api"
    sample_catalog_data["workspaces"][0]["folders"] = ["shop-web", "backend"]
    root = tmp_path / "parent" / "Goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    document = workspace_document(catalog, root, catalog.workspace("frontend"))
    names = [folder["name"] for folder in document["folders"]]
    assert names == ["goat", "shop-web", "backend"]
    assert document["folders"][1]["path"] == "../../frontend/shop-web"
    assert document["folders"][2]["path"] == "../../backend/api"


def test_generate_and_list(catalog, goat_root: Path):
    written = generate_workspaces(catalog, goat_root)
    assert {item["id"] for item in written} == {"frontend", "backend"}
    path = goat_root / "workspaces" / "frontend.code-workspace"
    assert path.exists()
    listed = list_workspaces(catalog, goat_root)
    frontend = next(item for item in listed if item["id"] == "frontend")
    assert frontend["exists"] is True
    assert frontend["personal"] is False
    assert frontend["repos"][0]["cloned"] is False
    assert frontend["start_file"].endswith("workspaces/frontend.start.yml")
    assert frontend["start_plan"] is False

    collect_start_plan(catalog, goat_root, workspace_id="frontend", save=True)
    start_path = goat_root / "workspaces" / "frontend.start.yml"
    original = start_path.read_text(encoding="utf-8")
    generate_workspaces(catalog, goat_root)
    assert start_path.read_text(encoding="utf-8") == original
    listed = list_workspaces(catalog, goat_root)
    frontend = next(item for item in listed if item["id"] == "frontend")
    assert frontend["start_plan"] is True


def test_generate_skips_personal_and_list_includes_them(catalog, goat_root: Path):
    create_workspace(
        catalog,
        goat_root,
        workspace_id="scratch",
        folders=["frontend"],
        personal=True,
        prompt=PromptSession(interactive=False),
    )
    personal_path = goat_root / "workspaces" / "personal" / "scratch.code-workspace"
    original = personal_path.read_text(encoding="utf-8")
    document = json.loads(original)
    document["goat"]["description"] = "do not overwrite"
    personal_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    refreshed = load_catalog(goat_root)
    written = generate_workspaces(refreshed, goat_root)
    assert {item["id"] for item in written} == {"frontend", "backend"}
    assert all(item["personal"] is False for item in written)
    assert not (goat_root / "workspaces" / "scratch.code-workspace").exists()
    assert personal_path.read_text(encoding="utf-8") == json.dumps(document, indent=2) + "\n"

    listed = list_workspaces(refreshed, goat_root)
    scratch = next(item for item in listed if item["id"] == "scratch")
    assert scratch["personal"] is True
    assert scratch["exists"] is True
    assert scratch["file"] == str(personal_path)


def test_parse_personal_workspace_accepts_legacy_coboose_key(tmp_path: Path):
    path = tmp_path / "legacy.code-workspace"
    path.write_text(
        json.dumps(
            {
                "folders": [
                    {"name": "coboose", "path": "../.."},
                    {"name": "frontend", "path": "../../../frontend"},
                ],
                "coboose": {
                    "id": "legacy",
                    "name": "Legacy",
                    "folders": ["frontend"],
                    "include_coboose": True,
                    "personal": True,
                },
            }
        ),
        encoding="utf-8",
    )
    workspace = parse_personal_workspace(path, {"frontend", "backend"})
    assert workspace is not None
    assert workspace.id == "legacy"
    assert workspace.folders == ["frontend"]
    assert workspace.include_goat is True
    assert workspace.personal is True

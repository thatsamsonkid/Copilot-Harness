import json
from pathlib import Path

from coboose.catalog import load_catalog
from coboose.prompt import PromptSession
from coboose.start import collect_start_plan
from coboose.workspace import (
    check_workspaces,
    generate_workspaces,
    list_workspaces,
    workspace_document,
    workspace_sync_error,
)
from coboose.workspace_create import create_workspace
from tests.helpers import write_coboose_config


def test_workspace_paths_point_at_siblings(catalog, coboose_root: Path):
    document = workspace_document(catalog, coboose_root, catalog.workspace("frontend"))
    names = [folder["name"] for folder in document["folders"]]
    assert names == ["coboose", "frontend", "backend"]
    assert document["folders"][0]["path"] == ".."
    assert document["folders"][1]["path"] == "../../frontend"
    assert document["folders"][2]["path"] == "../../backend"
    assert (
        document["settings"]["terminal.integrated.env.linux"]["COBOOSE_ROOT"]
        == "${workspaceFolder:coboose}"
    )
    assert (
        document["settings"]["terminal.integrated.env.osx"]["COBOOSE_ROOT"]
        == "${workspaceFolder:coboose}"
    )
    assert document["settings"]["terminal.integrated.env.linux"]["COBOOSE_WORKSPACE"] == "frontend"
    assert (
        document["settings"]["terminal.integrated.env.linux"]["COBOOSE_WORKSPACE_FILE"]
        == "${workspaceFile}"
    )
    assert document["coboose"]["id"] == "frontend"
    assert document["coboose"]["folders"] == ["frontend", "backend"]
    assert "HARNESS_ROOT" not in document["settings"]["terminal.integrated.env.linux"]
    assert "UV_PROJECT" not in document["settings"]["terminal.integrated.env.linux"]


def test_workspace_paths_for_grouped_repos(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["name"] = "shop-web"
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0].pop("path", None)
    sample_catalog_data["repos"][1]["path"] = "backend/api"
    sample_catalog_data["workspaces"][0]["folders"] = ["shop-web", "backend"]
    root = tmp_path / "parent" / "Coboose"
    write_coboose_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    document = workspace_document(catalog, root, catalog.workspace("frontend"))
    names = [folder["name"] for folder in document["folders"]]
    assert names == ["coboose", "shop-web", "backend"]
    assert document["folders"][1]["path"] == "../../frontend/shop-web"
    assert document["folders"][2]["path"] == "../../backend/api"


def test_generate_and_list(catalog, coboose_root: Path):
    written = generate_workspaces(catalog, coboose_root)
    assert {item["id"] for item in written} == {"frontend", "backend"}
    path = coboose_root / "workspaces" / "frontend.code-workspace"
    assert path.exists()
    listed = list_workspaces(catalog, coboose_root)
    frontend = next(item for item in listed if item["id"] == "frontend")
    assert frontend["exists"] is True
    assert frontend["personal"] is False
    assert frontend["sync"] == "ok"
    assert frontend["in_sync"] is True
    assert frontend["open_command"].endswith("frontend.code-workspace")
    assert {item["action"] for item in written} == {"created"}
    assert frontend["repos"][0]["cloned"] is False
    assert frontend["start_file"].endswith("workspaces/frontend.start.yml")
    assert frontend["start_plan"] is False

    collect_start_plan(catalog, coboose_root, workspace_id="frontend", save=True)
    start_path = coboose_root / "workspaces" / "frontend.start.yml"
    original = start_path.read_text(encoding="utf-8")
    generate_workspaces(catalog, coboose_root)
    assert start_path.read_text(encoding="utf-8") == original
    listed = list_workspaces(catalog, coboose_root)
    frontend = next(item for item in listed if item["id"] == "frontend")
    assert frontend["start_plan"] is True


def test_generate_skips_personal_and_list_includes_them(catalog, coboose_root: Path):
    create_workspace(
        catalog,
        coboose_root,
        workspace_id="scratch",
        folders=["frontend"],
        personal=True,
        prompt=PromptSession(interactive=False),
    )
    personal_path = coboose_root / "workspaces" / "personal" / "scratch.code-workspace"
    original = personal_path.read_text(encoding="utf-8")
    document = json.loads(original)
    document["coboose"]["description"] = "do not overwrite"
    personal_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    refreshed = load_catalog(coboose_root)
    written = generate_workspaces(refreshed, coboose_root)
    assert {item["id"] for item in written} == {"frontend", "backend"}
    assert all(item["personal"] is False for item in written)
    assert not (coboose_root / "workspaces" / "scratch.code-workspace").exists()
    assert personal_path.read_text(encoding="utf-8") == json.dumps(document, indent=2) + "\n"

    listed = list_workspaces(refreshed, coboose_root)
    scratch = next(item for item in listed if item["id"] == "scratch")
    assert scratch["personal"] is True
    assert scratch["exists"] is True
    assert scratch["file"] == str(personal_path)
    assert scratch["sync"] == "personal"
    assert scratch["in_sync"] is True
    assert check_workspaces(refreshed, coboose_root)["ok"] is True


def test_check_workspaces_reports_missing_stale_and_orphan(catalog, coboose_root: Path):
    missing = check_workspaces(catalog, coboose_root)
    assert missing["ok"] is False
    assert missing["missing"] == ["frontend", "backend"]
    assert missing["stale"] == []
    assert missing["orphans"] == []
    assert "workspace generate" in (missing.get("hint") or "")
    assert "missing frontend, backend" in workspace_sync_error(missing)

    listed = list_workspaces(catalog, coboose_root)
    assert {item["id"]: item["sync"] for item in listed} == {
        "frontend": "missing",
        "backend": "missing",
    }

    generate_workspaces(catalog, coboose_root)
    ok = check_workspaces(catalog, coboose_root)
    assert ok["ok"] is True
    assert ok["missing"] == []
    assert ok["stale"] == []
    assert ok["orphans"] == []

    stale_path = coboose_root / "workspaces" / "frontend.code-workspace"
    document = json.loads(stale_path.read_text(encoding="utf-8"))
    document["coboose"]["description"] = "hand edited"
    stale_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    orphan = coboose_root / "workspaces" / "legacy.code-workspace"
    orphan.write_text("{}\n", encoding="utf-8")

    drifted = check_workspaces(catalog, coboose_root)
    assert drifted["ok"] is False
    assert drifted["missing"] == []
    assert drifted["stale"] == ["frontend"]
    assert drifted["orphans"] == ["legacy"]
    assert drifted["orphan_files"][0]["file"] == str(orphan)
    error = workspace_sync_error(drifted)
    assert "stale frontend" in error
    assert "orphan legacy" in error

    generate_workspaces(catalog, coboose_root)
    after_generate = check_workspaces(catalog, coboose_root)
    assert after_generate["stale"] == []
    assert after_generate["orphans"] == ["legacy"]
    assert after_generate["ok"] is False
    rewritten = json.loads(stale_path.read_text(encoding="utf-8"))
    assert rewritten["coboose"]["description"] != "hand edited"


def test_shared_workspace_files_are_gitignored_not_committed():
    root = Path(__file__).resolve().parents[1]
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "workspaces/*.code-workspace" in gitignore
    committed = list((root / "workspaces").glob("*.code-workspace"))
    assert committed == []

from pathlib import Path

from harness.workspace import generate_workspaces, list_workspaces, workspace_document


def test_workspace_paths_point_at_siblings(catalog, harness_root: Path):
    document = workspace_document(catalog, harness_root, catalog.workspace("frontend"))
    names = [folder["name"] for folder in document["folders"]]
    assert names == ["harness", "frontend", "backend"]
    assert document["folders"][0]["path"] == ".."
    assert document["folders"][1]["path"] == "../../frontend"
    assert document["folders"][2]["path"] == "../../backend"


def test_generate_and_list(catalog, harness_root: Path):
    written = generate_workspaces(catalog, harness_root)
    assert {item["id"] for item in written} == {"frontend", "backend"}
    path = harness_root / "workspaces" / "frontend.code-workspace"
    assert path.exists()
    listed = list_workspaces(catalog, harness_root)
    frontend = next(item for item in listed if item["id"] == "frontend")
    assert frontend["exists"] is True
    assert frontend["repos"][0]["cloned"] is False

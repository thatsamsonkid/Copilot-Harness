from __future__ import annotations

import json
import subprocess
from pathlib import Path

from goat.branch import align_branches, suggested_branch
from goat.cli import main


def _init_git(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Dev"], cwd=path, check=True)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_suggested_branch_parses_browse_url():
    assert suggested_branch("https://acme.atlassian.net/browse/WEB-42") == "WEB-42"


def test_branch_suggests_without_creating(catalog, goat_root: Path):
    _init_git(goat_root.parent / "frontend")
    payload = align_branches(catalog, goat_root, "WEB-42", only=["frontend"])
    assert payload["branch"] == "WEB-42"
    assert payload["repos"][0]["action"] == "suggest"
    assert payload["repos"][0]["current_branch"] == "main"


def test_branch_create_on_clean_tree(catalog, goat_root: Path):
    frontend = goat_root.parent / "frontend"
    _init_git(frontend)
    payload = align_branches(
        catalog, goat_root, "WEB-42", only=["frontend"], create=True
    )
    assert payload["repos"][0]["action"] == "create"
    assert payload["repos"][0]["current_branch"] == "WEB-42"
    current = subprocess.check_output(
        ["git", "-C", str(frontend), "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
    ).strip()
    assert current == "WEB-42"


def test_branch_create_in_grouped_clone(sample_catalog_data: dict, goat_root: Path):
    from goat.catalog import load_catalog
    from tests.helpers import write_goat_config

    sample_catalog_data["repos"][0]["name"] = "shop-web"
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0].pop("path", None)
    sample_catalog_data["workspaces"][0]["folders"] = ["shop-web", "backend"]
    write_goat_config(goat_root, sample_catalog_data)
    catalog = load_catalog(goat_root)
    clone = goat_root.parent / "frontend" / "shop-web"
    _init_git(clone)
    payload = align_branches(
        catalog, goat_root, "WEB-42", only=["shop-web"], create=True
    )
    assert payload["repos"][0]["action"] == "create"
    assert payload["repos"][0]["path"].endswith("frontend/shop-web")
    current = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
    ).strip()
    assert current == "WEB-42"


def test_branch_refuses_dirty_create(catalog, goat_root: Path, capsys, monkeypatch):
    frontend = goat_root.parent / "frontend"
    _init_git(frontend)
    (frontend / "dirty.txt").write_text("nope\n", encoding="utf-8")
    monkeypatch.chdir(goat_root)
    assert (
        main(
            [
                "--root",
                str(goat_root),
                "branch",
                "WEB-42",
                "--repo",
                "frontend",
                "--create",
            ]
        )
        == 1
    )
    error = json.loads(capsys.readouterr().err)
    assert error["repos"][0]["action"] == "blocked"
    assert "dirty" in error["repos"][0]["error"].lower()

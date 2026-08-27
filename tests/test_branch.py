from __future__ import annotations

import json
import subprocess
from pathlib import Path

from harness.branch import align_branches, suggested_branch
from harness.cli import main


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


def test_branch_suggests_without_creating(catalog, harness_root: Path):
    _init_git(harness_root.parent / "frontend")
    payload = align_branches(catalog, harness_root, "WEB-42", only=["frontend"])
    assert payload["branch"] == "WEB-42"
    assert payload["repos"][0]["action"] == "suggest"
    assert payload["repos"][0]["current_branch"] == "main"


def test_branch_create_on_clean_tree(catalog, harness_root: Path):
    frontend = harness_root.parent / "frontend"
    _init_git(frontend)
    payload = align_branches(
        catalog, harness_root, "WEB-42", only=["frontend"], create=True
    )
    assert payload["repos"][0]["action"] == "create"
    assert payload["repos"][0]["current_branch"] == "WEB-42"
    current = subprocess.check_output(
        ["git", "-C", str(frontend), "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
    ).strip()
    assert current == "WEB-42"


def test_branch_refuses_dirty_create(catalog, harness_root: Path, capsys, monkeypatch):
    frontend = harness_root.parent / "frontend"
    _init_git(frontend)
    (frontend / "dirty.txt").write_text("nope\n", encoding="utf-8")
    monkeypatch.chdir(harness_root)
    assert (
        main(
            [
                "--root",
                str(harness_root),
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

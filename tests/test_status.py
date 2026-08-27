from __future__ import annotations

import json
import subprocess
from pathlib import Path

from harness.cli import main
from harness.status import collect_status


def _init_git(path: Path, *, branch: str = "main") -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", branch], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Dev"], cwd=path, check=True)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_status_reports_dirty_sibling(catalog, harness_root: Path):
    frontend = harness_root.parent / "frontend"
    _init_git(frontend)
    (frontend / "dirty.txt").write_text("nope\n", encoding="utf-8")
    payload = collect_status(catalog, harness_root, only=["frontend"], cwd=harness_root)
    repo = payload["repos"][0]
    assert repo["git"]["present"] is True
    assert repo["git"]["dirty"] is True
    assert payload["dirty_repos"] == ["frontend"]
    assert payload["cwd_hint"]["kind"] == "harness"


def test_status_cli_and_cwd_sibling_hint(catalog, harness_root: Path, capsys, monkeypatch):
    frontend = harness_root.parent / "frontend"
    _init_git(frontend)
    monkeypatch.chdir(frontend)
    assert main(["--root", str(harness_root), "status", "--repo", "frontend", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cwd_hint"]["kind"] == "sibling"
    assert payload["cwd_hint"]["repo"] == "frontend"
    assert payload["repos"][0]["git"]["branch"] == "main"

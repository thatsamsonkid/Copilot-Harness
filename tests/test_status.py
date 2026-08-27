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


def test_status_cwd_hint_uses_nested_group_path(
    sample_catalog_data: dict, harness_root: Path
):
    from harness.catalog import load_catalog
    from tests.helpers import write_harness_config

    sample_catalog_data["repos"][0]["name"] = "shop-web"
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0].pop("path", None)
    sample_catalog_data["workspaces"][0]["folders"] = ["shop-web", "backend"]
    write_harness_config(harness_root, sample_catalog_data)
    catalog = load_catalog(harness_root)
    clone = harness_root.parent / "frontend" / "shop-web"
    _init_git(clone)
    (clone / "src").mkdir()

    inside = collect_status(catalog, harness_root, only=["shop-web"], cwd=clone / "src")
    assert inside["cwd_hint"]["kind"] == "sibling"
    assert inside["cwd_hint"]["repo"] == "shop-web"
    assert inside["cwd_hint"]["relpath"] == "frontend/shop-web"
    assert inside["repos"][0]["relpath"] == "frontend/shop-web"
    assert inside["repos"][0]["group"] == "frontend"

    group_dir = collect_status(
        catalog, harness_root, only=["shop-web"], cwd=harness_root.parent / "frontend"
    )
    assert group_dir["cwd_hint"]["kind"] == "parent_dir"
    assert "group folder" in group_dir["cwd_hint"]["detail"]

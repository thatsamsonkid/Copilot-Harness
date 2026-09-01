from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from goat import GoatError
from goat.catalog import load_catalog
from goat.cli import main
from goat.clone import clone_repos
from goat.clone_map import (
    apply_workspace_map,
    map_clones,
    normalize_git_url,
    parse_set_paths,
)
from goat.workspace import workspace_document
from tests.helpers import write_goat_config


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_clone(path: Path, remote: str) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "remote", "add", "origin", remote)
    return path


def test_normalize_git_url_collapses_ssh_and_https():
    assert normalize_git_url("git@github.com:Acme/Frontend.git") == (
        normalize_git_url("https://github.com/acme/frontend")
    )
    assert normalize_git_url("ssh://git@github.com/acme/frontend.git") == (
        "github.com/acme/frontend"
    )
    assert normalize_git_url("https://github.com/acme/frontend.git/") == (
        "github.com/acme/frontend"
    )


def test_parse_set_paths_requires_name_equals_path():
    assert parse_set_paths(["frontend=~/code/shop-web"]) == {
        "frontend": "~/code/shop-web"
    }
    with pytest.raises(GoatError, match="NAME=PATH"):
        parse_set_paths(["frontend"])


def test_overlay_repo_path_and_workspace_folders(
    goat_root: Path, sample_catalog_data: dict, tmp_path: Path
):
    elsewhere = tmp_path / "elsewhere" / "shop-web"
    elsewhere.mkdir(parents=True)
    (goat_root / "repositories.local.yml").write_text(
        yaml.safe_dump({"paths": {"frontend": str(elsewhere)}}),
        encoding="utf-8",
    )
    catalog = load_catalog(goat_root)
    assert catalog.is_mapped("frontend")
    assert catalog.repo_path(goat_root, "frontend") == elsewhere.resolve()
    assert catalog.expected_repo_path(goat_root, "frontend") == goat_root.parent / "frontend"
    document = workspace_document(catalog, goat_root, catalog.workspace("frontend"))
    frontend_folder = next(
        folder for folder in document["folders"] if folder["name"] == "frontend"
    )
    assert Path(frontend_folder["path"]).name == "shop-web"
    payload = catalog_to_mapped(goat_root)
    assert payload["repos"][0]["mapped"] is True


def catalog_to_mapped(goat_root: Path) -> dict:
    from goat.catalog import catalog_to_dict

    return catalog_to_dict(load_catalog(goat_root), goat_root)


def test_overlay_refuses_path_inside_goat(goat_root: Path):
    (goat_root / "repositories.local.yml").write_text(
        yaml.safe_dump({"paths": {"frontend": "src"}}),
        encoding="utf-8",
    )
    with pytest.raises(GoatError, match="inside the Goat repo"):
        load_catalog(goat_root)


def test_overlay_unknown_name(goat_root: Path):
    (goat_root / "repositories.local.yml").write_text(
        yaml.safe_dump({"paths": {"nope": "../elsewhere"}}),
        encoding="utf-8",
    )
    with pytest.raises(GoatError, match="unknown repo"):
        load_catalog(goat_root)


def test_map_discovers_remote_elsewhere_and_writes_overlay(
    goat_root: Path, tmp_path: Path
):
    elsewhere = _init_clone(
        tmp_path / "code" / "shop-web",
        "git@github.com:acme/frontend.git",
    )
    payload = apply_workspace_map(
        load_catalog(goat_root),
        goat_root,
        extra_search=[str(tmp_path / "code")],
        write=True,
        generate=True,
    )
    frontend = next(row for row in payload["repos"] if row["id"] == "frontend")
    assert frontend["status"] == "remap"
    assert Path(frontend["found"]) == elsewhere.resolve()
    assert payload["wrote"] is True
    overlay = yaml.safe_load((goat_root / "repositories.local.yml").read_text())
    assert "frontend" in overlay["paths"]
    catalog = load_catalog(goat_root)
    document = workspace_document(catalog, goat_root, catalog.workspace("frontend"))
    frontend_folder = next(
        folder for folder in document["folders"] if folder["name"] == "frontend"
    )
    assert "shop-web" in frontend_folder["path"]
    assert (goat_root / "workspaces" / "frontend.code-workspace").exists()


def test_map_does_not_write_ambiguous_or_name_only(
    goat_root: Path, tmp_path: Path
):
    _init_clone(tmp_path / "one" / "frontend", "https://github.com/acme/frontend.git")
    _init_clone(tmp_path / "two" / "frontend", "https://github.com/acme/frontend.git")
    _init_clone(tmp_path / "named" / "backend", "https://github.com/other/not-backend.git")
    payload = apply_workspace_map(
        load_catalog(goat_root),
        goat_root,
        extra_search=[str(tmp_path / "one"), str(tmp_path / "two"), str(tmp_path / "named")],
        write=True,
    )
    by_id = {row["id"]: row for row in payload["repos"]}
    assert by_id["frontend"]["status"] == "ambiguous"
    assert by_id["backend"]["status"] == "name_only"
    assert payload["wrote"] is False
    assert not (goat_root / "repositories.local.yml").exists()


def test_map_expected_path_is_not_written(goat_root: Path):
    dest = goat_root.parent / "frontend"
    _init_clone(dest, "https://github.com/acme/frontend.git")
    payload = map_clones(load_catalog(goat_root), goat_root)
    frontend = next(row for row in payload["repos"] if row["id"] == "frontend")
    assert frontend["status"] == "expected"
    written = apply_workspace_map(load_catalog(goat_root), goat_root, write=True)
    assert written["wrote"] is False
    assert not (goat_root / "repositories.local.yml").exists()


def test_clone_skips_overlay_dest(
    goat_root: Path, sample_catalog_data: dict, tmp_path: Path
):
    remotes = tmp_path / "remotes"
    remotes.mkdir()
    work = remotes / "frontend-work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "README.md")
    _git(work, "commit", "-m", "init")
    bare = remotes / "frontend.git"
    subprocess.run(
        ["git", "clone", "--bare", str(work), str(bare)],
        check=True,
        capture_output=True,
        text=True,
    )
    sample_catalog_data["repos"][0]["url"] = str(bare)
    write_goat_config(goat_root, sample_catalog_data)
    existing = tmp_path / "already" / "frontend"
    subprocess.run(
        ["git", "clone", str(bare), str(existing)],
        check=True,
        capture_output=True,
        text=True,
    )
    (goat_root / "repositories.local.yml").write_text(
        yaml.safe_dump({"paths": {"frontend": str(existing)}}),
        encoding="utf-8",
    )
    catalog = load_catalog(goat_root)
    result = clone_repos(catalog, goat_root, only=["frontend"])
    assert result[0]["action"] == "exists"
    assert result[0]["mapped"] is True
    assert not (goat_root.parent / "frontend").exists()


def test_workspace_map_cli_set_and_generate(
    goat_root: Path, tmp_path: Path, capsys, monkeypatch
):
    elsewhere = _init_clone(
        tmp_path / "mine" / "web",
        "https://github.com/acme/frontend.git",
    )
    monkeypatch.chdir(goat_root)
    assert (
        main(
            [
                "--root",
                str(goat_root),
                "workspace",
                "map",
                "--set",
                f"frontend={elsewhere}",
                "--write",
                "--generate",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "workspace_map"
    frontend = next(row for row in payload["repos"] if row["id"] == "frontend")
    assert frontend["status"] == "pinned"
    assert payload["wrote"] is True
    catalog = load_catalog(goat_root)
    assert catalog.repo_path(goat_root, "frontend") == elsewhere.resolve()

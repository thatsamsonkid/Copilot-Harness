from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from coboose import CobooseError
from coboose.catalog import load_catalog
from coboose.clone import clone_repos, rewrite_clone_url
from tests.helpers import write_coboose_config


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _bare_repo(path: Path, branch: str = "main") -> Path:
    work = path.with_name(path.name + "-work")
    work.mkdir(parents=True)
    _git(work, "init", "-b", branch)
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "README.md")
    _git(work, "commit", "-m", "init")
    subprocess.run(
        ["git", "clone", "--bare", str(work), str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return path


def test_rewrite_https():
    assert (
        rewrite_clone_url("git@github.com:acme/web.git", https=True)
        == "https://github.com/acme/web.git"
    )
    assert rewrite_clone_url("https://github.com/acme/web.git", https=True).startswith(
        "https://"
    )


def test_clone_as_sibling_and_skip_existing(
    coboose_root: Path, sample_catalog_data: dict, tmp_path: Path
):
    remotes = tmp_path / "remotes"
    sample_catalog_data["repos"][0]["url"] = str(_bare_repo(remotes / "frontend.git"))
    sample_catalog_data["repos"][1]["url"] = str(_bare_repo(remotes / "backend.git"))
    write_coboose_config(coboose_root, sample_catalog_data)
    catalog = load_catalog(coboose_root)

    first = clone_repos(catalog, coboose_root)
    assert {item["action"] for item in first} == {"clone"}
    sibling = coboose_root.parent / "frontend"
    assert (sibling / ".git").exists()
    assert (coboose_root.parent / "backend" / "README.md").read_text() == "hello\n"
    assert sibling.resolve().parent == coboose_root.parent.resolve()
    assert not (coboose_root / "frontend").exists()

    second = clone_repos(catalog, coboose_root)
    assert {item["action"] for item in second} == {"exists"}


def test_placeholder_urls_are_blocked(
    coboose_root: Path, sample_catalog_data: dict
):
    sample_catalog_data["repos"][0]["url"] = "git@github.com:YOUR_ORG/frontend.git"
    write_coboose_config(coboose_root, sample_catalog_data)
    catalog = load_catalog(coboose_root)
    result = clone_repos(catalog, coboose_root, only=["frontend"])
    assert result[0]["action"] == "blocked"
    assert not (coboose_root.parent / "frontend").exists()


def test_refuses_filesystem_root_parent(
    coboose_root: Path, sample_catalog_data: dict
):
    sample_catalog_data["parent_dir"] = "/"
    write_coboose_config(coboose_root, sample_catalog_data)
    catalog = load_catalog(coboose_root)
    with pytest.raises(CobooseError, match="filesystem root"):
        clone_repos(catalog, coboose_root, only=["frontend"], dry_run=True)


def test_clone_into_grouped_folder(
    coboose_root: Path, sample_catalog_data: dict, tmp_path: Path
):
    remotes = tmp_path / "remotes"
    sample_catalog_data["repos"][0]["name"] = "shop-web"
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0].pop("path", None)
    sample_catalog_data["repos"][0]["url"] = str(_bare_repo(remotes / "shop-web.git"))
    sample_catalog_data["workspaces"][0]["folders"] = ["shop-web", "backend"]
    write_coboose_config(coboose_root, sample_catalog_data)
    catalog = load_catalog(coboose_root)

    result = clone_repos(catalog, coboose_root, only=["shop-web"])
    dest = coboose_root.parent / "frontend" / "shop-web"
    assert result[0]["action"] == "clone"
    assert (dest / ".git").exists()
    assert (dest / "README.md").read_text() == "hello\n"
    assert not (coboose_root / "frontend").exists()
    assert not (coboose_root.parent / "shop-web").exists()


def test_refuses_non_git_destination(catalog, coboose_root: Path):
    dest = coboose_root.parent / "frontend"
    dest.mkdir(parents=True)
    (dest / "notes.txt").write_text("not a repo\n", encoding="utf-8")
    with pytest.raises(CobooseError, match="not a git repo"):
        clone_repos(catalog, coboose_root, only=["frontend"])

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness import HarnessError
from harness.catalog import load_catalog
from harness.clone import clone_repos, rewrite_clone_url
from tests.conftest import write_catalog


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
    harness_root: Path, sample_catalog_data: dict, tmp_path: Path
):
    remotes = tmp_path / "remotes"
    sample_catalog_data["repos"][0]["url"] = str(_bare_repo(remotes / "frontend.git"))
    sample_catalog_data["repos"][1]["url"] = str(_bare_repo(remotes / "backend.git"))
    write_catalog(harness_root / "catalog" / "stack.yaml", sample_catalog_data)
    catalog = load_catalog(harness_root / "catalog" / "stack.yaml")

    first = clone_repos(catalog, harness_root)
    assert {item["action"] for item in first} == {"clone"}
    sibling = harness_root.parent / "frontend"
    assert (sibling / ".git").exists()
    assert (harness_root.parent / "backend" / "README.md").read_text() == "hello\n"
    assert sibling.resolve().parent == harness_root.parent.resolve()
    assert not (harness_root / "frontend").exists()

    second = clone_repos(catalog, harness_root)
    assert {item["action"] for item in second} == {"exists"}


def test_placeholder_urls_are_blocked(
    harness_root: Path, sample_catalog_data: dict
):
    sample_catalog_data["repos"][0]["url"] = "git@github.com:YOUR_ORG/frontend.git"
    write_catalog(harness_root / "catalog" / "stack.yaml", sample_catalog_data)
    catalog = load_catalog(harness_root / "catalog" / "stack.yaml")
    result = clone_repos(catalog, harness_root, only=["frontend"])
    assert result[0]["action"] == "blocked"
    assert not (harness_root.parent / "frontend").exists()


def test_refuses_filesystem_root_parent(
    harness_root: Path, sample_catalog_data: dict
):
    sample_catalog_data["parent_dir"] = "/"
    write_catalog(harness_root / "catalog" / "stack.yaml", sample_catalog_data)
    catalog = load_catalog(harness_root / "catalog" / "stack.yaml")
    with pytest.raises(HarnessError, match="filesystem root"):
        clone_repos(catalog, harness_root, only=["frontend"], dry_run=True)


def test_refuses_non_git_destination(catalog, harness_root: Path):
    dest = harness_root.parent / "frontend"
    dest.mkdir(parents=True)
    (dest / "notes.txt").write_text("not a repo\n", encoding="utf-8")
    with pytest.raises(HarnessError, match="not a git repo"):
        clone_repos(catalog, harness_root, only=["frontend"])

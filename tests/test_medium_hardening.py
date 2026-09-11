from __future__ import annotations

import os
from pathlib import Path

import pytest

from goat import GoatError
from goat.catalog import Workspace, load_catalog
from goat.clone import clone_repos
from goat.skills import _copy_ignore, pull_skills
from tests.helpers import write_goat_config


# --- parent_dir containment --------------------------------------------------


def test_absolute_parent_dir_is_rejected(goat_root: Path, sample_catalog_data: dict):
    sample_catalog_data["parent_dir"] = "/tmp/goat-somewhere-else"
    write_goat_config(goat_root, sample_catalog_data)
    catalog = load_catalog(goat_root)
    with pytest.raises(GoatError, match="relative path"):
        clone_repos(catalog, goat_root, only=["frontend"], dry_run=True)


# --- workspace id / path traversal -------------------------------------------


@pytest.mark.parametrize("bad_id", ["../evil", "a/b", "..", "with\\slash"])
def test_load_stack_rejects_unsafe_workspace_id(
    goat_root: Path, sample_catalog_data: dict, bad_id: str
):
    sample_catalog_data["workspaces"][0]["id"] = bad_id
    write_goat_config(goat_root, sample_catalog_data)
    with pytest.raises(GoatError, match="Invalid workspace id"):
        load_catalog(goat_root)


def test_workspace_file_rejects_escaping_id(catalog, goat_root: Path):
    escaping = Workspace(id="../../evil", name="Evil")
    with pytest.raises(GoatError, match="escapes the workspaces"):
        catalog.workspace_file(goat_root, escaping)


# --- skills pull must not dereference symlinks -------------------------------


def test_copy_ignore_skips_symlinks(tmp_path: Path):
    (tmp_path / "real.md").write_text("ok", encoding="utf-8")
    os.symlink(tmp_path / "real.md", tmp_path / "link.md")
    ignored = _copy_ignore(str(tmp_path), ["real.md", "link.md"])
    assert "link.md" in ignored
    assert "real.md" not in ignored


def test_resolve_workspace_path_honors_named_folders(tmp_path: Path):
    from goat.launch import _resolve_workspace_path

    repo = tmp_path / "frontend"
    shared = tmp_path / "shared"
    resolved = _resolve_workspace_path(
        repo, "${workspaceFolder:shared}/.env", {"shared": shared}
    )
    assert resolved == shared / ".env"
    # Plain ${workspaceFolder} still resolves to the repo itself.
    assert _resolve_workspace_path(repo, "${workspaceFolder}/.env") == repo / ".env"
    # An unknown named folder must not silently resolve to this repo.
    unresolved = _resolve_workspace_path(repo, "${workspaceFolder:nope}/.env", {})
    assert "${workspaceFolder:nope}" in str(unresolved)
    assert unresolved != repo / ".env"


def test_quote_cli_args_round_trips_dangerous_tokens():
    import shlex

    from goat.start import _quote_cli_args

    args = ["--flag", "a b", "; rm -rf /", "$(touch pwned)", "`id`"]
    quoted = _quote_cli_args(args)
    assert shlex.split(quoted) == args


def test_pull_skills_does_not_dereference_symlinks(
    catalog, goat_root: Path, tmp_path: Path
):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET", encoding="utf-8")

    def run(command, cwd):
        dest = Path(command[-1])
        skill = dest / "review"
        skill.mkdir(parents=True)
        skill.joinpath("SKILL.md").write_text(
            "---\nname: review\ndescription: d\n---\n\n# review\n",
            encoding="utf-8",
        )
        os.symlink(secret, skill / "leak.txt")

    pull_skills(
        catalog,
        goat_root,
        "https://github.com/acme/agent-skills.git",
        names=["review"],
        run=run,
    )
    installed = goat_root / ".github" / "skills" / "review"
    assert installed.joinpath("SKILL.md").exists()
    assert not installed.joinpath("leak.txt").exists()

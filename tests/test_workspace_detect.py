from __future__ import annotations

import json
from pathlib import Path

import pytest

from goat import GoatError
from goat.cli import main
from goat.context import collect_context
from goat.start import collect_start_plan
from goat.status import collect_status
from goat.workspace import generate_workspaces, workspace_document
from goat.workspace_detect import (
    WORKSPACE_FILE_ENV,
    WORKSPACE_ID_ENV,
    resolve_workspace_scope,
    scoped_repos,
)


def test_detects_workspace_from_legacy_env(catalog, goat_root: Path):
    scope = resolve_workspace_scope(
        catalog,
        goat_root,
        environ={"COBOOSE_WORKSPACE": "backend"},
    )
    assert scope.detected is True
    assert scope.id == "backend"
    assert scope.source == "env"
    assert "COBOOSE_WORKSPACE" in scope.detail


def test_detects_workspace_from_env(catalog, goat_root: Path):
    scope = resolve_workspace_scope(
        catalog,
        goat_root,
        environ={WORKSPACE_ID_ENV: "frontend"},
    )
    assert scope.detected is True
    assert scope.id == "frontend"
    assert scope.source == "env"
    assert scope.repos == ["frontend", "backend"]
    assert scope.scope == "workspace"


def test_flag_overrides_env(catalog, goat_root: Path):
    scope = resolve_workspace_scope(
        catalog,
        goat_root,
        workspace_id="backend",
        environ={WORKSPACE_ID_ENV: "frontend"},
    )
    assert scope.id == "backend"
    assert scope.source == "flag"
    assert scope.repos == ["backend"]


def test_all_ignores_env(catalog, goat_root: Path):
    scope = resolve_workspace_scope(
        catalog,
        goat_root,
        all_repos=True,
        environ={WORKSPACE_ID_ENV: "frontend"},
    )
    assert scope.detected is False
    assert scope.source == "all"
    assert scope.id is None
    assert scope.repos == ["frontend", "backend"]


def test_all_plus_workspace_is_an_error(catalog, goat_root: Path):
    with pytest.raises(GoatError, match="Do not combine"):
        resolve_workspace_scope(
            catalog,
            goat_root,
            workspace_id="frontend",
            all_repos=True,
        )


def test_unknown_env_workspace_is_an_error(catalog, goat_root: Path):
    with pytest.raises(GoatError, match="Unknown workspace"):
        resolve_workspace_scope(
            catalog,
            goat_root,
            environ={WORKSPACE_ID_ENV: "nope"},
        )


def test_unresolved_vscode_file_is_ignored(catalog, goat_root: Path):
    scope = resolve_workspace_scope(
        catalog,
        goat_root,
        environ={WORKSPACE_FILE_ENV: "${workspaceFile}"},
    )
    assert scope.detected is False
    assert scope.source == "none"


def test_detects_workspace_from_generated_file(catalog, goat_root: Path):
    generate_workspaces(catalog, goat_root)
    path = goat_root / "workspaces" / "backend.code-workspace"
    scope = resolve_workspace_scope(
        catalog,
        goat_root,
        workspace_file=path,
    )
    assert scope.id == "backend"
    assert scope.source == "file"
    assert scope.repos == ["backend"]

    from_env = resolve_workspace_scope(
        catalog,
        goat_root,
        environ={WORKSPACE_FILE_ENV: str(path)},
    )
    assert from_env.id == "backend"
    assert from_env.source == "file"


def test_generated_document_stamps_workspace_env(catalog, goat_root: Path):
    document = workspace_document(catalog, goat_root, catalog.workspace("backend"))
    env = document["settings"]["terminal.integrated.env.linux"]
    assert env["GOAT_WORKSPACE"] == "backend"
    assert env["GOAT_WORKSPACE_FILE"] == "${workspaceFile}"
    assert document["goat"]["id"] == "backend"


def test_context_stays_inside_open_workspace(catalog, goat_root: Path):
    payload = collect_context(
        catalog,
        goat_root,
        environ={WORKSPACE_ID_ENV: "backend"},
    )
    assert payload["workspace"] == "backend"
    assert [repo["name"] for repo in payload["repos"]] == ["backend"]
    assert payload["workspace_scope"]["detected"] is True
    assert "Stay inside workspace.repos" in payload["guidance"][0]


def test_context_all_includes_every_enabled_repo(catalog, goat_root: Path):
    payload = collect_context(
        catalog,
        goat_root,
        all_repos=True,
        environ={WORKSPACE_ID_ENV: "backend"},
    )
    assert payload["workspace"] is None
    assert [repo["name"] for repo in payload["repos"]] == ["frontend", "backend"]


def test_status_and_start_follow_env_workspace(catalog, goat_root: Path):
    status = collect_status(
        catalog,
        goat_root,
        cwd=goat_root,
        environ={WORKSPACE_ID_ENV: "backend"},
    )
    assert [repo["name"] for repo in status["repos"]] == ["backend"]
    assert status["workspace"] == "backend"

    plan = collect_start_plan(
        catalog,
        goat_root,
        environ={WORKSPACE_ID_ENV: "backend"},
    )
    assert plan["workspace"] == "backend"
    assert plan["order"] == ["backend"]
    assert plan["workspace_scope"]["source"] == "env"


def test_start_save_uses_detected_workspace(catalog, goat_root: Path):
    payload = collect_start_plan(
        catalog,
        goat_root,
        save=True,
        environ={WORKSPACE_ID_ENV: "frontend"},
    )
    assert payload["saved"]["action"] == "created"
    assert (goat_root / "workspaces" / "frontend.start.yml").is_file()


def test_repo_outside_workspace_is_rejected(catalog, goat_root: Path):
    with pytest.raises(GoatError, match="not in workspace backend"):
        scoped_repos(
            catalog,
            resolve_workspace_scope(
                catalog,
                goat_root,
                workspace_id="backend",
            ),
            only=["frontend"],
        )


def test_workspace_current_cli(catalog, goat_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(goat_root)
    monkeypatch.setenv(WORKSPACE_ID_ENV, "frontend")
    assert main(["--root", str(goat_root), "workspace", "current"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["detected"] is True
    assert payload["id"] == "frontend"
    assert payload["repos"] == ["frontend", "backend"]


def test_context_cli_respects_env(catalog, goat_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(goat_root)
    monkeypatch.setenv(WORKSPACE_ID_ENV, "backend")
    assert main(["--root", str(goat_root), "context"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [repo["name"] for repo in payload["repos"]] == ["backend"]
    assert payload["workspace_scope"]["source"] == "env"


def test_context_cli_all_overrides_env(catalog, goat_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(goat_root)
    monkeypatch.setenv(WORKSPACE_ID_ENV, "backend")
    assert main(["--root", str(goat_root), "context", "--all"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [repo["name"] for repo in payload["repos"]] == ["frontend", "backend"]
    assert payload["workspace_scope"]["source"] == "all"

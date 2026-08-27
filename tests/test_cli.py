from __future__ import annotations

import json
from pathlib import Path

from harness.cli import main


def test_jira_schema_needs_no_credentials(harness_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(harness_root)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    assert main(["--root", str(harness_root), "jira", "schema"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "summary" in payload["jira"]["fields"]
    assert payload["jira"]["include_comments"] is True


def test_repos_command(harness_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(harness_root)
    assert main(["--root", str(harness_root), "repos"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["manifest"].endswith("repositories.yml")
    assert [repo["name"] for repo in payload["repositories"]] == ["frontend", "backend"]
    assert payload["repositories"][0]["tags"] == ["ui"]


def test_catalog_and_workspace_generate(harness_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(harness_root)
    assert main(["--root", str(harness_root), "catalog"]) == 0
    catalog = json.loads(capsys.readouterr().out)
    assert catalog["repos"][0]["name"] == "frontend"

    assert main(["--root", str(harness_root), "workspace", "generate"]) == 0
    generated = json.loads(capsys.readouterr().out)
    assert len(generated["workspaces"]) == 2
    assert (harness_root / "workspaces" / "backend.code-workspace").exists()


def test_clone_dry_run_and_doctor(harness_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(harness_root)
    assert (
        main(["--root", str(harness_root), "clone", "--dry-run", "--only", "frontend"])
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["repos"][0]["action"] == "clone"
    assert payload["repos"][0]["cloned"] is False

    assert main(["--root", str(harness_root), "doctor"]) == 0
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["sibling_root"] == str(harness_root.parent.resolve())
    assert any(check["name"] == "jira_env" for check in doctor["checks"])
    assert any(check["name"] == "uv" for check in doctor["checks"])
    assert "onboarding" in doctor
    assert "uv" in doctor
    assert any(check["name"] == "env_age" for check in doctor["checks"])
    assert any(check["name"] == "graphify_cli" for check in doctor["checks"])
    assert "env_age" in doctor


def test_jira_mine_uses_current_user_jql(harness_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(harness_root)
    monkeypatch.setenv("JIRA_BASE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "a@b.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "tok")

    class FakeClient:
        def search(self, jql, max_results=25):
            assert "currentUser()" in jql
            return [{"key": "WEB-1", "summary": "Mine"}]

    monkeypatch.setattr("harness.cli._client", lambda: FakeClient())
    assert main(["--root", str(harness_root), "jira", "mine"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["issues"][0]["key"] == "WEB-1"


def test_error_is_json_on_stderr(harness_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(harness_root)
    assert main(["--root", str(harness_root), "workspace", "path", "nope"]) == 1
    captured = capsys.readouterr()
    error = json.loads(captured.err)
    assert "Unknown workspace" in error["error"]


def test_clone_placeholder_exits_nonzero(
    harness_root: Path, sample_catalog_data: dict, capsys, monkeypatch
):
    from tests.helpers import write_harness_config

    sample_catalog_data["repos"][0]["url"] = "git@github.com:YOUR_ORG/frontend.git"
    write_harness_config(harness_root, sample_catalog_data)
    monkeypatch.chdir(harness_root)
    assert main(["--root", str(harness_root), "clone", "--only", "frontend"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert error["repos"][0]["action"] == "blocked"


def test_missing_jira_env(harness_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(harness_root)
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_USERNAME", raising=False)
    monkeypatch.delenv("JIRA_TOKEN", raising=False)
    assert main(["--root", str(harness_root), "jira", "get", "WEB-1"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert "JIRA_BASE_URL" in error["error"]

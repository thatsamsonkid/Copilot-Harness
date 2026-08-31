from __future__ import annotations

import json
from pathlib import Path

from coboose.cli import main


def test_figma_schema_needs_no_credentials(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    monkeypatch.delenv("FIGMA_ACCESS_TOKEN", raising=False)
    assert main(["--root", str(coboose_root), "figma", "schema"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["figma"]["fields"][0] == "file_key"
    assert payload["figma"]["shapes"]["images"] == ["id", "url"]
    assert payload["figma"]["shapes"]["comments"] == [
        "author",
        "created",
        "message",
        "node_id",
        "resolved",
    ]
    assert payload["figma"]["default_format"] == "png"
    assert payload["figma"]["default_scale"] == 2
    assert payload["figma"]["include_comments"] is True
    assert payload["figma"]["max_comments"] == 30
    assert payload["figma"]["default_depth"] == 2
    assert payload["figma"]["max_depth"] == 3
    assert payload["figma"]["raw_nodes"] is True
    assert "targeted frame" in payload["figma"]["nodes_note"]
    assert payload["figma"]["drop_empty"] is True


def test_figma_images_uses_client(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "figd_test")

    class FakeClient:
        def get_images(self, file, ids=None, image_format=None, scale=None, settings=None):
            assert "figma.com" in file
            assert settings is not None
            return {
                "file_key": "AbCdEfGhIjKlMnOpQr",
                "url": file,
                "format": "png",
                "scale": 2,
                "images": [{"id": "12:34", "url": "https://example/one.png"}],
            }

    monkeypatch.setattr("coboose.cli._figma_client", lambda _catalog: FakeClient())
    assert main(
        [
            "--root",
            str(coboose_root),
            "figma",
            "images",
            "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr/Name?node-id=12-34",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["images"][0]["url"] == "https://example/one.png"


def test_figma_comments_and_nodes_use_client(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "figd_test")

    class FakeClient:
        def get_comments(self, file, ids=None, whole_file=False, settings=None):
            assert settings is not None
            assert whole_file is True
            return {
                "file_key": "AbCdEfGhIjKlMnOpQr",
                "url": file,
                "comments": [{"author": "Ada", "message": "Use navy"}],
            }

        def get_nodes(self, file, ids=None, depth=None, settings=None):
            assert depth == 1
            return {
                "file_key": "AbCdEfGhIjKlMnOpQr",
                "url": file,
                "depth": depth,
                "nodes": [{"id": "12:34", "name": "Button", "type": "FRAME"}],
            }

    monkeypatch.setattr("coboose.cli._figma_client", lambda _catalog: FakeClient())
    assert main(
        [
            "--root",
            str(coboose_root),
            "figma",
            "comments",
            "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr/Name?node-id=12-34",
            "--file-comments",
        ]
    ) == 0
    comments = json.loads(capsys.readouterr().out)
    assert comments["comments"][0]["message"] == "Use navy"

    assert main(
        [
            "--root",
            str(coboose_root),
            "figma",
            "nodes",
            "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr/Name?node-id=12-34",
            "--depth",
            "1",
        ]
    ) == 0
    nodes = json.loads(capsys.readouterr().out)
    assert nodes["nodes"][0]["name"] == "Button"


def test_missing_figma_env(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    monkeypatch.delenv("FIGMA_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("FIGMA_TOKEN", raising=False)
    monkeypatch.delenv("FIGMA_API_TOKEN", raising=False)
    assert main(["--root", str(coboose_root), "figma", "whoami"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert "FIGMA_ACCESS_TOKEN" in error["error"]
    assert "figma login" in error["error"]


def test_jira_schema_needs_no_credentials(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    assert main(["--root", str(coboose_root), "jira", "schema"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "summary" in payload["jira"]["fields"]
    assert payload["jira"]["include_comments"] is True
    assert payload["jira"]["shapes"]["comments"] == ["author", "created", "body"]
    assert "summary" in payload["jira"]["search_fields"]
    assert payload["jira"]["drop_empty"] is True


def test_repos_command(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    assert main(["--root", str(coboose_root), "repos"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["manifest"].endswith("repositories.yml")
    assert [repo["name"] for repo in payload["repositories"]] == ["frontend", "backend"]
    assert payload["repositories"][0]["tags"] == ["ui"]


def test_workspace_generate_check_does_not_write(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    path = coboose_root / "workspaces" / "frontend.code-workspace"
    assert not path.exists()
    assert main(["--root", str(coboose_root), "workspace", "generate", "--check"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert "out of sync" in error["error"]
    assert error["missing"] == ["frontend", "backend"]
    assert error["ok"] is False
    assert not path.exists()


def test_catalog_and_workspace_generate(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    assert main(["--root", str(coboose_root), "catalog"]) == 0
    catalog = json.loads(capsys.readouterr().out)
    assert catalog["repos"][0]["name"] == "frontend"

    assert main(["--root", str(coboose_root), "workspace", "generate"]) == 0
    generated = json.loads(capsys.readouterr().out)
    assert len(generated["workspaces"]) == 2
    assert (coboose_root / "workspaces" / "backend.code-workspace").exists()
    assert "skills" in generated
    assert generated["skills"]["dest"].endswith(".github/skills")
    assert {item["action"] for item in generated["workspaces"]} == {"created"}

    assert main(["--root", str(coboose_root), "workspace", "generate", "--check"]) == 0
    checked = json.loads(capsys.readouterr().out)
    assert checked["check"] is True
    assert checked["ok"] is True
    assert checked["in_sync"] is True
    assert checked["missing"] == []
    assert checked["stale"] == []
    assert checked["orphans"] == []

    stale = coboose_root / "workspaces" / "frontend.code-workspace"
    original = stale.read_text(encoding="utf-8")
    stale.write_text(original.replace("Frontend", "Hand Edited"), encoding="utf-8")
    assert main(["--root", str(coboose_root), "workspace", "generate", "--check"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert "out of sync" in error["error"]
    assert error["stale"] == ["frontend"]
    assert stale.read_text(encoding="utf-8") != original
    assert "Hand Edited" in stale.read_text(encoding="utf-8")


def test_clone_dry_run_and_doctor(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    assert (
        main(["--root", str(coboose_root), "clone", "--dry-run", "--only", "frontend"])
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["repos"][0]["action"] == "clone"
    assert payload["repos"][0]["cloned"] is False

    assert main(["--root", str(coboose_root), "doctor"]) == 0
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["sibling_root"] == str(coboose_root.parent.resolve())
    assert any(check["name"] == "jira_env" for check in doctor["checks"])
    assert any(check["name"] == "jira_token_store" for check in doctor["checks"])
    assert any(check["name"] == "figma_token_store" for check in doctor["checks"])
    assert "keychain" in doctor
    assert "env" in doctor
    assert {row["name"] for row in doctor["env"]["variables"]} >= {
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
    }
    assert any(check["name"] == "uv" for check in doctor["checks"])
    assert any(check["name"] == "cli_path" for check in doctor["checks"])
    assert "onboarding" in doctor
    assert "uv" in doctor
    assert any(check["name"] == "env_age" for check in doctor["checks"])
    assert any(check["name"] == "graphify_cli" for check in doctor["checks"])
    assert any(check["name"] == "bru_cli" for check in doctor["checks"])
    assert "bruno" in doctor
    assert "env_age" in doctor
    assert doctor["invoke"]["cwd"] == str(coboose_root.resolve())
    assert "--project" in doctor["invoke"]["command"]
    assert "workspace_sync" in doctor
    workspace_check = next(
        check for check in doctor["checks"] if check["name"] == "workspaces"
    )
    assert workspace_check["ok"] is False
    assert workspace_check["advisory"] is True
    assert "missing" in workspace_check["detail"]
    assert doctor["workspace_sync"]["missing"] == ["frontend", "backend"]
    assert (coboose_root / "workspaces" / "frontend.code-workspace").exists()


def test_jira_mine_uses_current_user_jql(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    monkeypatch.setenv("JIRA_BASE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "a@b.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "tok")

    class FakeClient:
        def search(self, jql, max_results=25, settings=None):
            assert "currentUser()" in jql
            assert settings is not None
            return [{"key": "WEB-1", "summary": "Mine"}]

    monkeypatch.setattr("coboose.cli._client", lambda: FakeClient())
    assert main(["--root", str(coboose_root), "jira", "mine"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["issues"][0]["key"] == "WEB-1"


def test_root_flag_works_before_or_after_subcommand(
    coboose_root: Path, capsys, monkeypatch
):
    monkeypatch.chdir("/")
    assert main(["--root", str(coboose_root), "repos"]) == 0
    before = json.loads(capsys.readouterr().out)
    assert main(["repos", "--root", str(coboose_root)]) == 0
    after = json.loads(capsys.readouterr().out)
    assert before["sibling_root"] == after["sibling_root"]
    assert before["sibling_root"] == str(coboose_root.parent.resolve())


def test_error_is_json_on_stderr(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    assert main(["--root", str(coboose_root), "workspace", "path", "nope"]) == 1
    captured = capsys.readouterr()
    error = json.loads(captured.err)
    assert "Unknown workspace" in error["error"]


def test_clone_placeholder_exits_nonzero(
    coboose_root: Path, sample_catalog_data: dict, capsys, monkeypatch
):
    from tests.helpers import write_coboose_config

    sample_catalog_data["repos"][0]["url"] = "git@github.com:YOUR_ORG/frontend.git"
    write_coboose_config(coboose_root, sample_catalog_data)
    monkeypatch.chdir(coboose_root)
    assert main(["--root", str(coboose_root), "clone", "--only", "frontend"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert error["repos"][0]["action"] == "blocked"


def test_missing_jira_env(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_USERNAME", raising=False)
    monkeypatch.delenv("JIRA_TOKEN", raising=False)
    assert main(["--root", str(coboose_root), "jira", "get", "WEB-1"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert "JIRA_BASE_URL" in error["error"]

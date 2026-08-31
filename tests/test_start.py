from __future__ import annotations

import json
from pathlib import Path

import pytest

from goat import GoatError
from goat.catalog import load_catalog
from goat.cli import main
from goat.output import render
from goat.prompt import PromptSession
from goat.envapply import GOAT_ENV_REPO
from goat.start import (
    collect_start_plan,
    execute_start_env,
    execute_start_run,
    load_saved_start_plan,
    redacted_exec_command,
    start_run_preview,
)
from goat.workspace_create import create_workspace
from tests.helpers import write_goat_config


def _write_angular(root: Path, name: str = "frontend") -> Path:
    repo = root.parent / name
    (repo / "src").mkdir(parents=True)
    (repo / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "start": "ng serve --port 4300",
                    "lint": "eslint .",
                }
            }
        ),
        encoding="utf-8",
    )
    (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
    (repo / "angular.json").write_text(
        json.dumps(
            {
                "projects": {
                    "shop": {
                        "architect": {
                            "serve": {
                                "options": {
                                    "port": 4300,
                                    "proxyConfig": "proxy.conf.json",
                                }
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (repo / "proxy.conf.json").write_text(
        json.dumps(
            {
                "/api": {
                    "target": "https://api.example.com",
                    "secure": True,
                    "changeOrigin": True,
                }
            }
        ),
        encoding="utf-8",
    )
    return repo


def _write_spring(root: Path, name: str = "backend") -> Path:
    repo = root.parent / name
    resources = repo / "src" / "main" / "resources"
    resources.mkdir(parents=True)
    (repo / "pom.xml").write_text(
        """<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
  </dependencies>
</project>
""",
        encoding="utf-8",
    )
    (repo / "mvnw").write_text("#!/bin/sh\n", encoding="utf-8")
    (resources / "application.yml").write_text(
        "server:\n  port: ${PORT:8090}\n",
        encoding="utf-8",
    )
    return repo


def test_start_discovers_angular_and_spring(goat_root: Path, catalog):
    _write_angular(goat_root)
    _write_spring(goat_root)
    payload = collect_start_plan(catalog, goat_root, workspace_id="frontend")
    assert payload["order"] == ["backend", "frontend"]
    assert payload["goat_root"] == str(goat_root.resolve())
    assert payload["invoke"]["cwd"] == str(goat_root.resolve())
    assert "--project" in payload["invoke"]["command"]
    assert any("cannot spawn" in item.lower() for item in payload["guidance"])
    by_name = {item["name"]: item for item in payload["services"]}

    backend = by_name["backend"]
    assert backend["kind"] == "spring-boot"
    assert backend["role"] == "backend"
    assert backend["command"] == "./mvnw spring-boot:run"
    assert backend["port_hint"] == 8090
    assert backend["port_source"].endswith("application.yml")
    assert backend["wait"] == "listen:8090"
    assert backend["source"] == "discovered"
    assert backend["run_via"] == "terminal"
    assert backend["launch"] is None

    frontend = by_name["frontend"]
    assert frontend["kind"] == "angular"
    assert frontend["role"] == "frontend"
    assert frontend["command"] == "pnpm start"
    assert frontend["port_hint"] == 4300
    assert frontend["depends_on"] == ["backend"]
    assert frontend["proxies"][0]["relative"] == "proxy.conf.json"
    assert frontend["proxies"][0]["targets"] == [
        {"context": "/api", "target": "https://api.example.com"}
    ]
    assert any("proxy" in note.lower() for note in frontend["notes"])
    assert payload["plan_source"] == "discovered"
    assert payload["plan_exists"] is False
    assert payload["plan_file"].endswith("workspaces/frontend.start.yml")
    assert any("--save" in item for item in payload["guidance"])


def test_repositories_yml_rejects_start_block(
    sample_catalog_data: dict, goat_root: Path
):
    sample_catalog_data["repos"][1]["start"] = {
        "command": "java -jar app.jar",
        "port": 9000,
        "role": "backend",
    }
    write_goat_config(goat_root, sample_catalog_data)
    with pytest.raises(GoatError, match="no longer owns start commands"):
        load_catalog(goat_root)


def test_start_marks_uncloned_and_unknown(goat_root: Path, catalog):
    payload = collect_start_plan(catalog, goat_root, only=["frontend"])
    service = payload["services"][0]
    assert service["cloned"] is False
    assert service["blocked"] == "repo is not cloned"
    assert payload["blocked"][0]["name"] == "frontend"


def test_start_cli_and_markdown(goat_root: Path, capsys, monkeypatch):
    _write_angular(goat_root)
    _write_spring(goat_root)
    monkeypatch.chdir(goat_root)
    assert (
        main(
            [
                "--root",
                str(goat_root),
                "start",
                "--workspace",
                "frontend",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert [item["name"] for item in payload["services"]] == ["backend", "frontend"]
    assert "does not start processes" in payload["guidance"][0].lower()
    assert any("own vs code terminal" in item.lower() for item in payload["guidance"])

    markdown = render(payload, "markdown")
    assert "# Start plan (`frontend`)" in markdown
    assert "--project" in markdown
    assert "pnpm start" in markdown
    assert "proxy.conf.json" in markdown
    assert "--save" in markdown
    text = render(payload, "text")
    assert "backend" in text and "frontend" in text
    assert "No saved sequence" in text


def test_catalog_to_dict_lists_workspace_start_file(goat_root: Path, catalog):
    from goat.catalog import catalog_to_dict

    payload = catalog_to_dict(catalog, goat_root)
    assert "start" not in payload["repos"][0]
    frontend_ws = next(item for item in payload["workspaces"] if item["id"] == "frontend")
    assert frontend_ws["start_file"].endswith("workspaces/frontend.start.yml")
    assert frontend_ws["start_plan"] is False


def test_start_save_and_reuse_workspace_plan(goat_root: Path, catalog):
    _write_angular(goat_root)
    _write_spring(goat_root)
    first = collect_start_plan(
        catalog, goat_root, workspace_id="frontend", save=True
    )
    plan_path = Path(first["saved"]["path"])
    assert first["saved"]["action"] == "created"
    assert first["plan_source"] == "discovered"
    assert any("saved the sequence" in item.lower() for item in first["guidance"])
    assert plan_path.is_file()
    assert plan_path.name == "frontend.start.yml"
    saved = load_saved_start_plan(plan_path)
    assert saved["order"] == ["backend", "frontend"]
    assert saved["services"][0]["command"] == "./mvnw spring-boot:run"
    assert saved["services"][0]["port"] == 8090

    plan_path.write_text(
        """workspace: frontend
order:
  - frontend
  - backend
services:
  - name: frontend
    command: pnpm start --host 0.0.0.0
    port: 4500
    role: frontend
    depends_on: [backend]
  - name: backend
    command: java -jar custom.jar
    port: 9001
    role: backend
    wait: http://localhost:9001/health
""",
        encoding="utf-8",
    )
    reused = collect_start_plan(catalog, goat_root, workspace_id="frontend")
    assert reused["plan_source"] == "saved"
    assert reused["plan_exists"] is True
    assert reused["order"] == ["frontend", "backend"]
    by_name = {item["name"]: item for item in reused["services"]}
    assert by_name["frontend"]["source"] == "saved"
    assert by_name["frontend"]["command"] == "pnpm start --host 0.0.0.0"
    assert by_name["frontend"]["port_hint"] == 4500
    assert by_name["backend"]["command"] == "java -jar custom.jar"
    assert by_name["backend"]["wait"] == "http://localhost:9001/health"
    assert any("saved sequence" in item.lower() for item in reused["guidance"])
    markdown = render(reused, "markdown")
    assert "Saved sequence" in markdown


def test_start_refresh_ignores_saved_plan(goat_root: Path, catalog):
    _write_angular(goat_root)
    _write_spring(goat_root)
    collect_start_plan(catalog, goat_root, workspace_id="frontend", save=True)
    plan_path = catalog.workspace_start_file(goat_root, "frontend")
    plan_path.write_text(
        "workspace: frontend\norder: [backend]\nservices:\n"
        "  - name: backend\n    command: echo nope\n    port: 1\n    role: backend\n",
        encoding="utf-8",
    )
    refreshed = collect_start_plan(
        catalog, goat_root, workspace_id="frontend", refresh=True
    )
    assert refreshed["plan_source"] == "discovered"
    assert refreshed["order"] == ["backend", "frontend"]
    backend = refreshed["services"][0]
    assert backend["command"] == "./mvnw spring-boot:run"
    assert backend["port_hint"] == 8090
    assert any("this run rediscovered" in item.lower() for item in refreshed["guidance"])


def test_saved_plan_reports_unplanned_and_stale(goat_root: Path, catalog):
    _write_angular(goat_root)
    _write_spring(goat_root)
    plan_path = catalog.workspace_start_file(goat_root, "frontend")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        """workspace: frontend
order:
  - backend
  - gone-service
services:
  - name: backend
    command: ./mvnw spring-boot:run
    port: 8090
    role: backend
""",
        encoding="utf-8",
    )
    payload = collect_start_plan(catalog, goat_root, workspace_id="frontend")
    assert payload["plan_source"] == "saved"
    assert payload["order"] == ["backend", "frontend"]
    assert payload["unplanned"] == ["frontend"]
    assert payload["stale"] == ["gone-service"]
    frontend = next(item for item in payload["services"] if item["name"] == "frontend")
    assert any("not in the saved" in note.lower() for note in frontend["notes"])


def test_save_requires_workspace_and_rejects_repo_filter(goat_root: Path, catalog):
    with pytest.raises(GoatError, match="--save needs a workspace"):
        collect_start_plan(catalog, goat_root, save=True)
    with pytest.raises(GoatError, match="Do not combine it with --repo"):
        collect_start_plan(
            catalog,
            goat_root,
            workspace_id="frontend",
            only=["backend"],
            save=True,
        )


def test_personal_workspace_saves_start_plan_beside_file(catalog, goat_root: Path):
    _write_angular(goat_root)
    _write_spring(goat_root)
    create_workspace(
        catalog,
        goat_root,
        workspace_id="scratch",
        folders=["frontend", "backend"],
        personal=True,
        prompt=PromptSession(interactive=False),
    )
    refreshed = load_catalog(goat_root)
    payload = collect_start_plan(
        refreshed, goat_root, workspace_id="scratch", save=True
    )
    path = Path(payload["saved"]["path"])
    assert path.as_posix().endswith("workspaces/personal/scratch.start.yml")
    assert path.is_file()
    assert refreshed.workspace_start_file(goat_root, "scratch") == path


def test_start_save_cli(goat_root: Path, capsys, monkeypatch):
    _write_angular(goat_root)
    _write_spring(goat_root)
    monkeypatch.chdir(goat_root)
    assert (
        main(
            [
                "--root",
                str(goat_root),
                "start",
                "--workspace",
                "frontend",
                "--save",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["saved"]["action"] == "created"
    assert Path(payload["saved"]["path"]).is_file()

    assert (
        main(
            [
                "--root",
                str(goat_root),
                "start",
                "--workspace",
                "frontend",
                "--save",
                "--repo",
                "backend",
            ]
        )
        == 1
    )
    error = json.loads(capsys.readouterr().err)
    assert "--repo" in error["error"] or "combine" in error["error"]


def _write_java_launch(
    repo: Path,
    *,
    secret: str = "s3cret-do-not-print",
    args: str = "--spring.profiles.active=local --token=dont-print-me",
    env_file: str | None = "${workspaceFolder}/.env",
    extra_config: dict | None = None,
) -> None:
    vscode = repo / ".vscode"
    vscode.mkdir(parents=True, exist_ok=True)
    configurations = [
        {
            "type": "java",
            "name": "Launch Backend",
            "request": "launch",
            "mainClass": "com.example.ApiApplication",
            "args": args,
            "vmArgs": "-Xmx512m",
            "env": {
                "DB_PASSWORD": secret,
                "API_TOKEN": "tok_live_xxx",
            },
        },
        {
            "type": "java",
            "name": "Attach",
            "request": "attach",
            "hostName": "localhost",
            "port": 5005,
        },
    ]
    if env_file:
        configurations[0]["envFile"] = env_file
    if extra_config:
        configurations.append(extra_config)
    (vscode / "launch.json").write_text(
        """// VS Code launch
{
  "version": "0.2.0",
  "configurations": """
        + json.dumps(configurations, indent=2)
        + """,
}
""",
        encoding="utf-8",
    )


def test_start_redacts_launch_json_secrets(goat_root: Path, catalog):
    repo = _write_spring(goat_root)
    _write_java_launch(repo)
    (repo / ".env").write_text("MORE_SECRET=another-hidden-value\n", encoding="utf-8")
    payload = collect_start_plan(catalog, goat_root, only=["backend"])
    dumped = json.dumps(payload)
    assert "s3cret-do-not-print" not in dumped
    assert "tok_live_xxx" not in dumped
    assert "dont-print-me" not in dumped
    assert "another-hidden-value" not in dumped

    service = payload["services"][0]
    assert service["run_via"] == "goat"
    assert "goat start run --repo backend" in service["copilot_command"]
    assert "--project" in service["copilot_command"]
    launch = service["launch"]
    assert launch["configuration"] == "Launch Backend"
    assert launch["secret_risk"] is True
    assert launch["has_env"] is True
    assert launch["has_args"] is True
    assert "DB_PASSWORD" in launch["env_keys"]
    assert launch["env_file"] == ".env"
    assert "MORE_SECRET" in launch["env_file_keys"]
    assert any("goat start run" in note for note in service["notes"])
    assert any("never read launch.json" in item.lower() for item in payload["guidance"])
    markdown = render(payload, "markdown")
    assert "Launch Backend" in markdown
    assert "s3cret-do-not-print" not in markdown


def test_start_run_applies_env_without_leaking(goat_root: Path, catalog):
    repo = _write_spring(goat_root)
    _write_java_launch(repo)
    (repo / ".env").write_text("MORE_SECRET=another-hidden-value\n", encoding="utf-8")
    recorded: dict = {}

    def fake_run(command: str, cwd: Path, env: dict[str, str]) -> int:
        recorded["command"] = command
        recorded["cwd"] = cwd
        recorded["env"] = env
        recorded["password"] = env.get("DB_PASSWORD")
        recorded["file_secret"] = env.get("MORE_SECRET")
        return 0

    payload = execute_start_run(
        catalog, goat_root, "backend", dry_run=False, run=fake_run
    )
    assert recorded["password"] == "s3cret-do-not-print"
    assert recorded["file_secret"] == "another-hidden-value"
    assert recorded["env"][GOAT_ENV_REPO] == "backend"
    assert "spring-boot.run.arguments" in recorded["command"]
    dumped = json.dumps(payload)
    assert "s3cret-do-not-print" not in dumped
    assert "another-hidden-value" not in dumped
    assert "dont-print-me" not in dumped
    assert payload["command"] == "./mvnw spring-boot:run"
    assert payload["exec_command"] == (
        "./mvnw spring-boot:run "
        "-Dspring-boot.run.arguments=<redacted> "
        "-Dspring-boot.run.jvmArguments=<redacted>"
    )
    assert payload["arg_count"] == 2
    assert payload["vm_arg_count"] == 1
    assert payload["java_tool_options"] is False
    assert payload["env_keys"] == ["API_TOKEN", "DB_PASSWORD", "MORE_SECRET"]
    assert payload["marker_keys"] == ["GOAT_ENV_CONFIGURATION", "GOAT_ENV_REPO"]
    assert payload["applied_args"] is True
    assert payload["exit_code"] == 0


def test_start_run_dry_run_cli(goat_root: Path, capsys, monkeypatch):
    repo = _write_spring(goat_root)
    _write_java_launch(repo)
    monkeypatch.chdir(goat_root)
    assert (
        main(
            [
                "--root",
                str(goat_root),
                "start",
                "run",
                "--repo",
                "backend",
                "--dry-run",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["dry_run"] is True
    assert payload["name"] == "backend"
    assert "DB_PASSWORD" in payload["env_keys"]
    assert "s3cret-do-not-print" not in out
    assert "dont-print-me" not in out
    assert payload.get("env") is None
    assert payload["exec_command"] == (
        "./mvnw spring-boot:run "
        "-Dspring-boot.run.arguments=<redacted> "
        "-Dspring-boot.run.jvmArguments=<redacted>"
    )
    assert payload["arg_count"] == 2
    assert payload["vm_arg_count"] == 1
    assert "overwritten_keys" in payload
    assert "marker_keys" in payload
    text = render(payload, "text")
    assert "exec_command:" in text
    assert "<redacted>" in text
    assert "s3cret-do-not-print" not in text


def test_start_run_preview_marks_java_tool_options():
    preview = start_run_preview(
        {
            "name": "worker",
            "cwd": "/tmp",
            "command": "java -jar app.jar",
            "args": None,
            "vm_args": "-Xmx512m",
            "applied_args": False,
            "applied_vm_args": True,
            "env_keys": [],
        }
    )
    assert preview["exec_command"] == "java -jar app.jar"
    assert preview["java_tool_options"] is True
    assert preview["vm_arg_count"] == 1
    assert preview["arg_count"] == 0


def test_redacted_exec_command_shapes():
    spring = "./mvnw spring-boot:run"
    assert redacted_exec_command(spring, None, None) == spring
    assert redacted_exec_command(
        spring,
        "--spring.profiles.active=local --token=secret",
        "-Xmx512m",
    ) == (
        "./mvnw spring-boot:run "
        "-Dspring-boot.run.arguments=<redacted> "
        "-Dspring-boot.run.jvmArguments=<redacted>"
    )
    assert (
        redacted_exec_command("./gradlew bootRun", ["--args-one"], None)
        == "./gradlew bootRun --args=<redacted>"
    )
    assert redacted_exec_command("pnpm start", ["--port", "4200"], None) == (
        "pnpm start <redacted>"
    )
    assert redacted_exec_command("pnpm start", None, "-Xmx512m") == "pnpm start"


def test_start_run_banner_uses_redacted_exec(goat_root: Path, catalog, capsys):
    repo = _write_spring(goat_root)
    _write_java_launch(repo)

    def fake_run(command: str, cwd: Path, env: dict[str, str]) -> int:
        assert "dont-print-me" in command
        return 0

    execute_start_run(catalog, goat_root, "backend", run=fake_run)
    err = capsys.readouterr().err
    assert "exec_command ./mvnw spring-boot:run" in err
    assert "-Dspring-boot.run.arguments=<redacted>" in err
    assert "dont-print-me" not in err
    assert "s3cret-do-not-print" not in err


def test_start_run_keep_existing_and_prefix(goat_root: Path, catalog, monkeypatch):
    repo = _write_spring(goat_root)
    _write_java_launch(repo)
    (repo / ".env").write_text("MORE_SECRET=another-hidden-value\n", encoding="utf-8")
    monkeypatch.setenv("DB_PASSWORD", "already-in-terminal")
    recorded: dict = {}

    def fake_run(command: str, cwd: Path, env: dict[str, str]) -> int:
        recorded["env"] = env
        return 0

    kept = execute_start_run(
        catalog,
        goat_root,
        "backend",
        keep_existing=True,
        run=fake_run,
    )
    assert recorded["env"]["DB_PASSWORD"] == "already-in-terminal"
    assert "DB_PASSWORD" in kept["skipped_keys"]
    assert "DB_PASSWORD" not in kept["env_keys"]
    dumped = json.dumps(kept)
    assert "already-in-terminal" not in dumped
    assert "s3cret-do-not-print" not in dumped

    prefixed = execute_start_run(
        catalog,
        goat_root,
        "backend",
        prefix="BACKEND",
        dry_run=True,
    )
    assert "BACKEND_DB_PASSWORD" in prefixed["env_keys"]
    assert "DB_PASSWORD" not in prefixed["env_keys"]
    assert prefixed["prefix"] == "BACKEND_"
    assert "s3cret-do-not-print" not in json.dumps(prefixed)


def test_start_env_lists_collisions_without_values(
    goat_root: Path, catalog, monkeypatch
):
    repo = _write_spring(goat_root)
    _write_java_launch(repo)
    (repo / ".env").write_text("MORE_SECRET=another-hidden-value\n", encoding="utf-8")
    monkeypatch.setenv("API_TOKEN", "parent-token")
    payload = execute_start_env(catalog, goat_root, "backend")
    assert payload["name"] == "backend"
    assert payload["shell"] is False
    assert "API_TOKEN" in payload["env_keys"]
    assert "API_TOKEN" in payload["overwritten_keys"]
    assert payload["marker_keys"] == ["GOAT_ENV_CONFIGURATION", "GOAT_ENV_REPO"]
    dumped = json.dumps(payload)
    assert "s3cret-do-not-print" not in dumped
    assert "parent-token" not in dumped
    assert "another-hidden-value" not in dumped
    assert payload.get("env") is None


def test_start_env_shell_execs_with_env(goat_root: Path, catalog):
    repo = _write_spring(goat_root)
    _write_java_launch(repo)
    (repo / ".env").write_text("MORE_SECRET=another-hidden-value\n", encoding="utf-8")
    recorded: dict = {}

    def fake_exec(env: dict[str, str], cwd: Path) -> None:
        recorded["env"] = env
        recorded["cwd"] = cwd

    payload = execute_start_env(
        catalog, goat_root, "backend", shell=True, exec_fn=fake_exec
    )
    assert payload["shell"] is True
    assert recorded["env"]["DB_PASSWORD"] == "s3cret-do-not-print"
    assert recorded["env"][GOAT_ENV_REPO] == "backend"
    assert recorded["cwd"] == repo
    assert "s3cret-do-not-print" not in json.dumps(payload)


def test_start_env_cli_and_launch_only_repo(goat_root: Path, capsys, monkeypatch):
    repo = goat_root.parent / "backend"
    repo.mkdir(parents=True)
    _write_java_launch(repo)
    monkeypatch.chdir(goat_root)
    assert (
        main(
            [
                "--root",
                str(goat_root),
                "start",
                "env",
                "--repo",
                "backend",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "backend"
    assert "DB_PASSWORD" in payload["env_keys"]
    assert payload["shell"] is False
    assert payload.get("env") is None
    assert "s3cret-do-not-print" not in json.dumps(payload)

    assert (
        main(
            [
                "--root",
                str(goat_root),
                "start",
                "run",
                "--repo",
                "backend",
                "--shell",
            ]
        )
        == 1
    )
    error = json.loads(capsys.readouterr().err)
    assert "start env" in error["error"]


def test_start_vscode_inputs_force_vscode_run(goat_root: Path, catalog):
    repo = _write_spring(goat_root)
    _write_java_launch(
        repo,
        extra_config={
            "type": "java",
            "name": "Prompted",
            "request": "launch",
            "mainClass": "com.example.ApiApplication",
            "env": {"DB_PASSWORD": "${input:dbPassword}"},
        },
    )
    plan_path = catalog.workspace_start_file(goat_root, "frontend")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        """workspace: frontend
order:
  - backend
services:
  - name: backend
    command: ./mvnw spring-boot:run
    role: backend
    launch: Prompted
""",
        encoding="utf-8",
    )
    payload = collect_start_plan(catalog, goat_root, workspace_id="frontend")
    service = next(item for item in payload["services"] if item["name"] == "backend")
    assert service["launch"]["configuration"] == "Prompted"
    assert service["launch"]["uses_vscode_inputs"] is True
    assert service["run_via"] == "vscode"
    assert service["copilot_command"] is None
    dumped = json.dumps(payload)
    assert "${input:dbPassword}" not in dumped
    with pytest.raises(GoatError, match="input variables"):
        execute_start_run(
            catalog, goat_root, "backend", configuration="Prompted"
        )


def test_start_launch_only_uses_vscode_without_blocking(goat_root: Path, catalog):
    repo = goat_root.parent / "backend"
    repo.mkdir(parents=True)
    _write_java_launch(repo)
    payload = collect_start_plan(catalog, goat_root, only=["backend"])
    service = payload["services"][0]
    assert service["command"] is None
    assert service["run_via"] == "vscode"
    assert service["blocked"] is None
    assert any("Run Without Debugging" in note for note in service["notes"])


def test_saved_plan_rejects_bad_method(goat_root: Path, catalog):
    plan_path = catalog.workspace_start_file(goat_root, "frontend")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        "workspace: frontend\nservices:\n  - name: backend\n    method: debug\n",
        encoding="utf-8",
    )
    with pytest.raises(GoatError, match="method must be terminal"):
        collect_start_plan(catalog, goat_root, workspace_id="frontend")

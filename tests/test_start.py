from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import HarnessError
from harness.catalog import load_catalog
from harness.cli import main
from harness.output import render
from harness.start import collect_start_plan, execute_start_run
from tests.helpers import write_harness_config


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


def test_start_discovers_angular_and_spring(harness_root: Path, catalog):
    _write_angular(harness_root)
    _write_spring(harness_root)
    payload = collect_start_plan(catalog, harness_root, workspace_id="frontend")
    assert payload["order"] == ["backend", "frontend"]
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


def test_start_override_wins(sample_catalog_data: dict, harness_root: Path):
    sample_catalog_data["repos"][1]["start"] = {
        "command": "java -jar app.jar",
        "port": 9000,
        "role": "backend",
        "wait": "http://localhost:9000/health",
    }
    write_harness_config(harness_root, sample_catalog_data)
    catalog = load_catalog(harness_root)
    _write_spring(harness_root)
    payload = collect_start_plan(catalog, harness_root, only=["backend"])
    service = payload["services"][0]
    assert service["source"] == "override"
    assert service["confidence"] == "high"
    assert service["command"] == "java -jar app.jar"
    assert service["port_hint"] == 9000
    assert service["wait"] == "http://localhost:9000/health"
    assert catalog.repo("backend").start.to_dict()["port"] == 9000


def test_start_marks_uncloned_and_unknown(harness_root: Path, catalog):
    payload = collect_start_plan(catalog, harness_root, only=["frontend"])
    service = payload["services"][0]
    assert service["cloned"] is False
    assert service["blocked"] == "repo is not cloned"
    assert payload["blocked"][0]["name"] == "frontend"


def test_start_cli_and_markdown(harness_root: Path, capsys, monkeypatch):
    _write_angular(harness_root)
    _write_spring(harness_root)
    monkeypatch.chdir(harness_root)
    assert (
        main(
            [
                "--root",
                str(harness_root),
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
    assert "pnpm start" in markdown
    assert "proxy.conf.json" in markdown
    text = render(payload, "text")
    assert "backend" in text and "frontend" in text


def test_start_rejects_bad_port(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["start"] = {"port": "abc"}
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    with pytest.raises(HarnessError, match="start.port"):
        load_catalog(root)


def test_catalog_to_dict_includes_start_override(
    sample_catalog_data: dict, harness_root: Path
):
    sample_catalog_data["repos"][0]["start"] = {
        "command": "pnpm start",
        "port": 4200,
        "role": "frontend",
    }
    write_harness_config(harness_root, sample_catalog_data)
    catalog = load_catalog(harness_root)
    from harness.catalog import catalog_to_dict

    payload = catalog_to_dict(catalog, harness_root)
    assert payload["repos"][0]["start"]["port"] == 4200
    assert payload["repos"][1]["start"] is None


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


def test_start_redacts_launch_json_secrets(harness_root: Path, catalog):
    repo = _write_spring(harness_root)
    _write_java_launch(repo)
    (repo / ".env").write_text("MORE_SECRET=another-hidden-value\n", encoding="utf-8")
    payload = collect_start_plan(catalog, harness_root, only=["backend"])
    dumped = json.dumps(payload)
    assert "s3cret-do-not-print" not in dumped
    assert "tok_live_xxx" not in dumped
    assert "dont-print-me" not in dumped
    assert "another-hidden-value" not in dumped

    service = payload["services"][0]
    assert service["run_via"] == "harness"
    assert service["copilot_command"].startswith("uv run harness start run --repo backend")
    launch = service["launch"]
    assert launch["configuration"] == "Launch Backend"
    assert launch["secret_risk"] is True
    assert launch["has_env"] is True
    assert launch["has_args"] is True
    assert "DB_PASSWORD" in launch["env_keys"]
    assert launch["env_file"] == ".env"
    assert "MORE_SECRET" in launch["env_file_keys"]
    assert any("harness start run" in note for note in service["notes"])
    assert any("launch.json env/args" in item.lower() for item in payload["guidance"])
    markdown = render(payload, "markdown")
    assert "Launch Backend" in markdown
    assert "s3cret-do-not-print" not in markdown


def test_start_run_applies_env_without_leaking(harness_root: Path, catalog):
    repo = _write_spring(harness_root)
    _write_java_launch(repo)
    (repo / ".env").write_text("MORE_SECRET=another-hidden-value\n", encoding="utf-8")
    recorded: dict = {}

    def fake_run(command: str, cwd: Path, env: dict[str, str]) -> int:
        recorded["command"] = command
        recorded["cwd"] = cwd
        recorded["password"] = env.get("DB_PASSWORD")
        recorded["file_secret"] = env.get("MORE_SECRET")
        return 0

    payload = execute_start_run(
        catalog, harness_root, "backend", dry_run=False, run=fake_run
    )
    assert recorded["password"] == "s3cret-do-not-print"
    assert recorded["file_secret"] == "another-hidden-value"
    assert "spring-boot.run.arguments" in recorded["command"]
    dumped = json.dumps(payload)
    assert "s3cret-do-not-print" not in dumped
    assert "another-hidden-value" not in dumped
    assert "dont-print-me" not in dumped
    assert payload["command"] == "./mvnw spring-boot:run"
    assert payload["env_keys"] == ["API_TOKEN", "DB_PASSWORD", "MORE_SECRET"]
    assert payload["applied_args"] is True
    assert payload["exit_code"] == 0


def test_start_run_dry_run_cli(harness_root: Path, capsys, monkeypatch):
    repo = _write_spring(harness_root)
    _write_java_launch(repo)
    monkeypatch.chdir(harness_root)
    assert (
        main(
            [
                "--root",
                str(harness_root),
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
    assert payload.get("env") is None
    assert payload.get("exec_command") is None


def test_start_vscode_inputs_force_vscode_run(harness_root: Path, catalog):
    repo = _write_spring(harness_root)
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
    # Prefer the prompted config via override
    sample = {
        "parent_dir": "..",
        "repos": [
            {
                "name": "backend",
                "url": "git@github.com:example/backend.git",
                "tags": ["api", "backend"],
                "start": {"launch": "Prompted"},
            }
        ],
        "workspaces": [{"id": "api", "name": "API", "folders": ["backend"]}],
    }
    write_harness_config(harness_root, sample)
    catalog = load_catalog(harness_root)
    payload = collect_start_plan(catalog, harness_root, only=["backend"])
    service = payload["services"][0]
    assert service["launch"]["configuration"] == "Prompted"
    assert service["launch"]["uses_vscode_inputs"] is True
    assert service["run_via"] == "vscode"
    assert service["copilot_command"] is None
    dumped = json.dumps(payload)
    assert "${input:dbPassword}" not in dumped
    with pytest.raises(HarnessError, match="input variables"):
        execute_start_run(catalog, harness_root, "backend")


def test_start_launch_only_uses_vscode_without_blocking(harness_root: Path, catalog):
    repo = harness_root.parent / "backend"
    repo.mkdir(parents=True)
    _write_java_launch(repo)
    payload = collect_start_plan(catalog, harness_root, only=["backend"])
    service = payload["services"][0]
    assert service["command"] is None
    assert service["run_via"] == "vscode"
    assert service["blocked"] is None
    assert any("Run Without Debugging" in note for note in service["notes"])


def test_start_rejects_bad_method(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["start"] = {"method": "debug"}
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    with pytest.raises(HarnessError, match="start.method"):
        load_catalog(root)

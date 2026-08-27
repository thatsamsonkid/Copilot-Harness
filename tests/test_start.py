from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import HarnessError
from harness.catalog import load_catalog
from harness.cli import main
from harness.output import render
from harness.prompt import PromptSession
from harness.start import collect_start_plan, load_saved_start_plan
from harness.workspace_create import create_workspace
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
    sample_catalog_data: dict, harness_root: Path
):
    sample_catalog_data["repos"][1]["start"] = {
        "command": "java -jar app.jar",
        "port": 9000,
        "role": "backend",
    }
    write_harness_config(harness_root, sample_catalog_data)
    with pytest.raises(HarnessError, match="no longer owns start commands"):
        load_catalog(harness_root)


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
    assert "--save" in markdown
    text = render(payload, "text")
    assert "backend" in text and "frontend" in text
    assert "No saved sequence" in text


def test_catalog_to_dict_lists_workspace_start_file(harness_root: Path, catalog):
    from harness.catalog import catalog_to_dict

    payload = catalog_to_dict(catalog, harness_root)
    assert "start" not in payload["repos"][0]
    frontend_ws = next(item for item in payload["workspaces"] if item["id"] == "frontend")
    assert frontend_ws["start_file"].endswith("workspaces/frontend.start.yml")
    assert frontend_ws["start_plan"] is False


def test_start_save_and_reuse_workspace_plan(harness_root: Path, catalog):
    _write_angular(harness_root)
    _write_spring(harness_root)
    first = collect_start_plan(
        catalog, harness_root, workspace_id="frontend", save=True
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
    reused = collect_start_plan(catalog, harness_root, workspace_id="frontend")
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


def test_start_refresh_ignores_saved_plan(harness_root: Path, catalog):
    _write_angular(harness_root)
    _write_spring(harness_root)
    collect_start_plan(catalog, harness_root, workspace_id="frontend", save=True)
    plan_path = catalog.workspace_start_file(harness_root, "frontend")
    plan_path.write_text(
        "workspace: frontend\norder: [backend]\nservices:\n"
        "  - name: backend\n    command: echo nope\n    port: 1\n    role: backend\n",
        encoding="utf-8",
    )
    refreshed = collect_start_plan(
        catalog, harness_root, workspace_id="frontend", refresh=True
    )
    assert refreshed["plan_source"] == "discovered"
    assert refreshed["order"] == ["backend", "frontend"]
    backend = refreshed["services"][0]
    assert backend["command"] == "./mvnw spring-boot:run"
    assert backend["port_hint"] == 8090
    assert any("this run rediscovered" in item.lower() for item in refreshed["guidance"])


def test_saved_plan_reports_unplanned_and_stale(harness_root: Path, catalog):
    _write_angular(harness_root)
    _write_spring(harness_root)
    plan_path = catalog.workspace_start_file(harness_root, "frontend")
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
    payload = collect_start_plan(catalog, harness_root, workspace_id="frontend")
    assert payload["plan_source"] == "saved"
    assert payload["order"] == ["backend", "frontend"]
    assert payload["unplanned"] == ["frontend"]
    assert payload["stale"] == ["gone-service"]
    frontend = next(item for item in payload["services"] if item["name"] == "frontend")
    assert any("not in the saved" in note.lower() for note in frontend["notes"])


def test_save_requires_workspace_and_rejects_repo_filter(harness_root: Path, catalog):
    with pytest.raises(HarnessError, match="--save requires --workspace"):
        collect_start_plan(catalog, harness_root, save=True)
    with pytest.raises(HarnessError, match="Do not combine it with --repo"):
        collect_start_plan(
            catalog,
            harness_root,
            workspace_id="frontend",
            only=["backend"],
            save=True,
        )


def test_personal_workspace_saves_start_plan_beside_file(catalog, harness_root: Path):
    _write_angular(harness_root)
    _write_spring(harness_root)
    create_workspace(
        catalog,
        harness_root,
        workspace_id="scratch",
        folders=["frontend", "backend"],
        personal=True,
        prompt=PromptSession(interactive=False),
    )
    refreshed = load_catalog(harness_root)
    payload = collect_start_plan(
        refreshed, harness_root, workspace_id="scratch", save=True
    )
    path = Path(payload["saved"]["path"])
    assert path.as_posix().endswith("workspaces/personal/scratch.start.yml")
    assert path.is_file()
    assert refreshed.workspace_start_file(harness_root, "scratch") == path


def test_start_save_cli(harness_root: Path, capsys, monkeypatch):
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
                str(harness_root),
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

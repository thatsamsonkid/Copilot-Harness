from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import HarnessError
from harness.catalog import load_catalog
from harness.cli import main
from harness.output import render
from harness.start import collect_start_plan
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

from __future__ import annotations

import json
from pathlib import Path

import yaml

from goat.catalog import load_catalog
from goat.cli import main
from goat.graph.build import build_graph, scan_workspace
from goat.graph.query import explain, neighbors, path_between
from goat.graph.schema import node_id
from goat.graph.validate import validate_graph
from tests.helpers import write_goat_config


def _write_stack(root: Path, data: dict) -> None:
    write_goat_config(root, data)
    (root / "catalog" / "graph.yaml").write_text(
        yaml.safe_dump({"declare": [], "reject": []}),
        encoding="utf-8",
    )


def _product_workspace(tmp_path: Path, sample_catalog_data: dict) -> Path:
    root = tmp_path / "parent" / "Goat"
    _write_stack(root, sample_catalog_data)
    frontend = root.parent / "frontend"
    backend = root.parent / "backend"
    frontend.mkdir(parents=True)
    backend.mkdir(parents=True)

    (frontend / "package.json").write_text(
        json.dumps(
            {
                "name": "frontend",
                "dependencies": {"backend": "file:../backend"},
            }
        ),
        encoding="utf-8",
    )
    (frontend / ".env.example").write_text(
        "BOOKING_API_URL=\nNODE_ENV=development\n",
        encoding="utf-8",
    )
    (frontend / "proxy.conf.json").write_text(
        json.dumps({"/booking": {"target": "http://localhost:8080", "secure": False}}),
        encoding="utf-8",
    )
    (frontend / "angular.json").write_text(
        json.dumps(
            {
                "projects": {
                    "web": {
                        "architect": {
                            "serve": {"options": {"proxyConfig": "proxy.conf.json"}}
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    (backend / "openapi.yaml").write_text(
        "openapi: 3.0.0\ninfo:\n  title: Booking API\n  version: '2'\n"
        "  x-workspace-id: booking-v2\npaths:\n  /booking/slots:\n    get:\n"
        "      summary: slots\n",
        encoding="utf-8",
    )
    adr = backend / "docs" / "adr"
    adr.mkdir(parents=True)
    (adr / "ADR-014-booking.md").write_text(
        "---\nid: ADR-014\ntitle: Booking service owns booking lifecycle\n"
        "governs:\n  - service:backend\n  - api:booking-v2\n---\n"
        "# Booking service owns booking lifecycle\n",
        encoding="utf-8",
    )
    ws = backend / ".workspace"
    ws.mkdir()
    (ws / "component.yaml").write_text(
        "id: backend\ntype: service\nprovides:\n  - api:booking-v2\n"
        "resources:\n  - database:booking-db\npublishes:\n  - event:booking.updated\n",
        encoding="utf-8",
    )
    return root


def test_build_from_catalog_only(catalog, goat_root: Path):
    (goat_root / "catalog" / "graph.yaml").write_text(
        "declare: []\nreject: []\n", encoding="utf-8"
    )
    payload = build_graph(catalog, goat_root, write=False)
    graph = payload["graph"]
    ids = {node["id"] for node in graph["nodes"]}
    assert "repository:frontend" in ids
    assert "repository:backend" in ids
    assert any(
        edge["relationship"] == "CONTAINS" and edge["target"] == "repository:frontend"
        for edge in graph["edges"]
    )
    validate_graph(graph)


def test_extract_and_correlate_contracts(
    tmp_path: Path, sample_catalog_data: dict
):
    root = _product_workspace(tmp_path, sample_catalog_data)
    catalog = load_catalog(root)
    payload = build_graph(catalog, root, write=True)
    graph = payload["graph"]
    dest = root / ".workspace" / "generated" / "workspace-graph.json"
    assert dest.is_file()
    ids = {node["id"] for node in graph["nodes"]}
    assert "api:booking-v2" in ids
    assert "database:booking-db" in ids
    assert "event:booking.updated" in ids
    assert "adr:adr-014" in ids

    consumes = [
        edge
        for edge in graph["edges"]
        if edge["relationship"] == "CONSUMES" and edge["target"] == "api:booking-v2"
    ]
    assert consumes
    assert consumes[0]["classification"] in {"INFERRED", "EXTRACTED", "DECLARED"}
    assert consumes[0]["evidence"]
    assert consumes[0]["confidence"] >= 0.55

    provides = [
        edge
        for edge in graph["edges"]
        if edge["source"] == "service:backend"
        and edge["relationship"] == "PROVIDES"
        and edge["target"] == "api:booking-v2"
    ]
    assert provides
    governed = [
        edge
        for edge in graph["edges"]
        if edge["relationship"] == "GOVERNED_BY" and edge["target"] == "adr:adr-014"
    ]
    assert governed
    uses = [
        edge
        for edge in graph["edges"]
        if edge["relationship"] == "USES" and edge["target"] == "database:booking-db"
    ]
    assert uses

    explained = explain(graph, "application:frontend", "api:booking-v2")
    assert explained["edges"]
    nearby = neighbors(graph, "api:booking-v2")
    assert nearby["inbound"] or nearby["outbound"]
    trail = path_between(graph, "service:backend", "database:booking-db")
    assert trail["edges"]


def test_reject_survives_rebuild(tmp_path: Path, sample_catalog_data: dict):
    root = _product_workspace(tmp_path, sample_catalog_data)
    (root / "catalog" / "graph.yaml").write_text(
        yaml.safe_dump(
            {
                "declare": [],
                "reject": [
                    {
                        "source": "repository:frontend",
                        "target": "repository:backend",
                        "relationship": "DEPENDS_ON",
                        "note": "prefer the API contract",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    graph = build_graph(load_catalog(root), root, write=False)["graph"]
    rejected = [
        edge
        for edge in graph["edges"]
        if edge["classification"] == "REJECTED"
        and edge["source"] == "repository:frontend"
        and edge["target"] == "repository:backend"
    ]
    assert rejected
    assert rejected[0]["confidence"] == 0


def test_graph_cli_scan_build_explain(
    tmp_path: Path, sample_catalog_data: dict, capsys, monkeypatch
):
    root = _product_workspace(tmp_path, sample_catalog_data)
    monkeypatch.chdir(root)
    assert main(["--root", str(root), "graph", "scan"]) == 0
    scan = json.loads(capsys.readouterr().out)
    assert scan["kind"] == "workspace_graph_scan"
    assert {row["name"] for row in scan["extractors"]} >= {"catalog", "openapi", "adr"}

    assert main(["--root", str(root), "graph", "build"]) == 0
    built = json.loads(capsys.readouterr().out)
    assert built["wrote"] is True
    assert (root / ".workspace" / "generated" / "workspace-graph.json").is_file()

    assert (
        main(
            [
                "--root",
                str(root),
                "graph",
                "explain",
                "frontend",
                "booking-v2",
            ]
        )
        == 0
    )
    explained = json.loads(capsys.readouterr().out)
    assert explained["kind"] == "workspace_graph_explain"
    assert explained["edges"]


def test_scan_does_not_write(catalog, goat_root: Path):
    (goat_root / "catalog" / "graph.yaml").write_text(
        "declare: []\nreject: []\n", encoding="utf-8"
    )
    scan_workspace(catalog, goat_root)
    assert not (goat_root / ".workspace" / "generated" / "workspace-graph.json").exists()


def test_node_id_stable():
    assert node_id("api", "Booking API") == "api:booking-api"
    assert node_id("repo", "frontend") == "repository:frontend"

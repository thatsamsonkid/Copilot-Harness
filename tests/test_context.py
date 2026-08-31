from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from goat.cli import main
from goat.context import collect_context
from tests.helpers import write_goat_config


def _write_sibling(goat_root: Path, name: str) -> Path:
    repo = goat_root.parent / name
    (repo / ".github" / "instructions").mkdir(parents=True)
    (repo / "graphify-out").mkdir(parents=True)
    (repo / ".github" / "copilot-instructions.md").write_text(
        "Use the design system buttons.\n", encoding="utf-8"
    )
    (repo / "AGENTS.md").write_text("Run pnpm test after edits.\n", encoding="utf-8")
    (repo / ".github" / "instructions" / "ui.instructions.md").write_text(
        "---\napplyTo: \"**/*.ts\"\n---\nNo any types.\n",
        encoding="utf-8",
    )
    (repo / "graphify-out" / "GRAPH_REPORT.md").write_text(
        "# God nodes\nCheckoutForm\n", encoding="utf-8"
    )
    (repo / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")
    (repo / "package.json").write_text(
        json.dumps({"scripts": {"lint": "eslint .", "test": "vitest"}}),
        encoding="utf-8",
    )
    (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
    (repo / "docs" / "features").mkdir(parents=True)
    (repo / "docs" / "features" / "checkout.md").write_text(
        "# Checkout\nUses CheckoutForm.\n", encoding="utf-8"
    )
    return repo


def test_context_discovers_graphify_and_standards(goat_root: Path, catalog):
    _write_sibling(goat_root, "frontend")
    payload = collect_context(catalog, goat_root, only=["frontend"])
    repo = payload["repos"][0]
    assert repo["cloned"] is True
    assert repo["graphify"]["present"] is True
    assert repo["graphify"]["report"].endswith("GRAPH_REPORT.md")
    assert "graphify query" in repo["graphify"]["query_command"]
    kinds = {item["kind"] for item in repo["instructions"]}
    assert {"copilot", "agents", "path-instructions"} <= kinds
    assert repo["tooling"]["suggested_verify"] == ["pnpm lint", "pnpm test"]
    assert repo["knowledge"]["dirs"][0]["kind"] == "feature"
    assert repo["knowledge"]["files"][0]["name"] == "checkout.md"
    assert repo["knowledge"]["template"] == "templates/feature-note.md"
    assert repo["tooling"]["generated"]["markers"] == []
    assert repo["graphify"]["stale"] in (None, False)
    assert payload["skills"]["dest"].endswith(".github/skills")
    assert "available" in payload["skills"]


def test_context_cli_skips_missing_clone(goat_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(goat_root)
    assert main(["--root", str(goat_root), "context", "--repo", "backend"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repos"][0]["cloned"] is False
    assert payload["repos"][0]["graphify"]["detail"] == "repo is not cloned"


def test_graphify_can_be_disabled(sample_catalog_data: dict, goat_root: Path):
    sample_catalog_data["repos"][0]["graphify"] = False
    write_goat_config(goat_root, sample_catalog_data)
    from goat.catalog import load_catalog

    catalog = load_catalog(goat_root)
    _write_sibling(goat_root, "frontend")
    payload = collect_context(catalog, goat_root, only=["frontend"])
    assert payload["repos"][0]["graphify"]["enabled"] is False
    assert payload["repos"][0]["graphify"]["present"] is False


def test_context_discovers_generated_and_custom_knowledge(
    sample_catalog_data: dict, goat_root: Path
):
    sample_catalog_data["repos"][0]["knowledge"] = {"dirs": ["handbook"]}
    write_goat_config(goat_root, sample_catalog_data)
    from goat.catalog import load_catalog

    catalog = load_catalog(goat_root)
    repo = _write_sibling(goat_root, "frontend")
    (repo / "nx.json").write_text("{}\n", encoding="utf-8")
    (repo / "src" / "generated").mkdir(parents=True)
    (repo / "handbook").mkdir()
    (repo / "handbook" / "payments.md").write_text("# Payments\n", encoding="utf-8")
    payload = collect_context(catalog, goat_root, only=["frontend"])
    generated = payload["repos"][0]["tooling"]["generated"]
    assert "nx" in generated["markers"]
    assert "src/generated" in generated["paths"]
    assert generated["hint"]
    kinds = {item["kind"] for item in payload["repos"][0]["knowledge"]["dirs"]}
    assert "custom" in kinds
    names = {item["name"] for item in payload["repos"][0]["knowledge"]["files"]}
    assert "payments.md" in names


def test_graphify_marks_stale_when_commit_is_newer(goat_root: Path, catalog):
    repo = _write_sibling(goat_root, "frontend")
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Dev"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "graph"], cwd=repo, check=True, capture_output=True)
    graph = repo / "graphify-out" / "graph.json"
    older = time.time() - 3600
    os.utime(graph, (older, older))
    (repo / "later.txt").write_text("new\n", encoding="utf-8")
    subprocess.run(["git", "add", "later.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "later"], cwd=repo, check=True, capture_output=True)
    payload = collect_context(catalog, goat_root, only=["frontend"])
    assert payload["repos"][0]["graphify"]["stale"] is True

from __future__ import annotations

import json
from pathlib import Path

from harness.cli import main
from harness.context import collect_context
from tests.helpers import write_harness_config


def _write_sibling(harness_root: Path, name: str) -> Path:
    repo = harness_root.parent / name
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


def test_context_discovers_graphify_and_standards(harness_root: Path, catalog):
    _write_sibling(harness_root, "frontend")
    payload = collect_context(catalog, harness_root, only=["frontend"])
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


def test_context_cli_skips_missing_clone(harness_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(harness_root)
    assert main(["--root", str(harness_root), "context", "--repo", "backend"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repos"][0]["cloned"] is False
    assert payload["repos"][0]["graphify"]["detail"] == "repo is not cloned"


def test_graphify_can_be_disabled(sample_catalog_data: dict, harness_root: Path):
    sample_catalog_data["repos"][0]["graphify"] = False
    write_harness_config(harness_root, sample_catalog_data)
    from harness.catalog import load_catalog

    catalog = load_catalog(harness_root)
    _write_sibling(harness_root, "frontend")
    payload = collect_context(catalog, harness_root, only=["frontend"])
    assert payload["repos"][0]["graphify"]["enabled"] is False
    assert payload["repos"][0]["graphify"]["present"] is False

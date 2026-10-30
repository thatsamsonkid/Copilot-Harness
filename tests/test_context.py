from __future__ import annotations

import json
from pathlib import Path

from goat.cli import main
from goat.context import collect_context
from tests.helpers import write_goat_config


def _write_sibling(goat_root: Path, name: str) -> Path:
    repo = goat_root.parent / name
    (repo / ".github" / "instructions").mkdir(parents=True)
    (repo / ".github" / "copilot-instructions.md").write_text(
        "Use the design system buttons.\n", encoding="utf-8"
    )
    (repo / "AGENTS.md").write_text("Run pnpm test after edits.\n", encoding="utf-8")
    (repo / ".github" / "instructions" / "ui.instructions.md").write_text(
        "---\napplyTo: \"**/*.ts\"\n---\nNo any types.\n",
        encoding="utf-8",
    )
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


def test_context_discovers_instructions_and_standards(goat_root: Path, catalog):
    _write_sibling(goat_root, "frontend")
    payload = collect_context(catalog, goat_root, only=["frontend"])
    repo = payload["repos"][0]
    assert repo["cloned"] is True
    assert "graphify" not in repo
    kinds = {item["kind"] for item in repo["instructions"]}
    assert {"copilot", "agents", "path-instructions"} <= kinds
    assert repo["tooling"]["suggested_verify"] == ["pnpm lint", "pnpm test"]
    assert repo["knowledge"]["dirs"][0]["kind"] == "feature"
    assert repo["knowledge"]["files"][0]["name"] == "checkout.md"
    assert repo["knowledge"]["template"] == "templates/feature-note.md"
    assert repo["tooling"]["generated"]["markers"] == []
    assert payload["skills"]["dest"].endswith(".github/skills")
    assert "available" in payload["skills"]
    guidance = " ".join(payload["guidance"]).lower()
    assert "search/codebase" in guidance
    assert "search/usages" in guidance
    assert "graphify" not in guidance


def test_context_cli_skips_missing_clone(goat_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(goat_root)
    assert main(["--root", str(goat_root), "context", "--repo", "backend"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repos"][0]["cloned"] is False
    assert "graphify" not in payload["repos"][0]


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

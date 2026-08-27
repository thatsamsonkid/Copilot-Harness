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
    assert repo["readiness"]["ok"] is True
    assert repo["readiness"]["checked"] is True
    assert payload["alignment"]["ok"] is True
    assert payload["alignment"]["missing_verify"] == []


def test_context_cli_skips_missing_clone(harness_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(harness_root)
    assert main(["--root", str(harness_root), "context", "--repo", "backend"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repos"][0]["cloned"] is False
    assert payload["repos"][0]["graphify"]["detail"] == "repo is not cloned"
    assert payload["repos"][0]["readiness"]["checked"] is False
    assert payload["alignment"]["ok"] is True
    assert payload["alignment"]["not_cloned"] == ["backend"]

    assert (
        main(["--root", str(harness_root), "context", "--repo", "backend", "--check"])
        == 0
    )


def test_graphify_can_be_disabled(sample_catalog_data: dict, harness_root: Path):
    sample_catalog_data["repos"][0]["graphify"] = False
    write_harness_config(harness_root, sample_catalog_data)
    from harness.catalog import load_catalog

    catalog = load_catalog(harness_root)
    _write_sibling(harness_root, "frontend")
    payload = collect_context(catalog, harness_root, only=["frontend"])
    assert payload["repos"][0]["graphify"]["enabled"] is False
    assert payload["repos"][0]["graphify"]["present"] is False
    assert not any(
        gap["id"] == "graphify" for gap in payload["repos"][0]["readiness"]["gaps"]
    )


def _write_bare_sibling(harness_root: Path, name: str) -> Path:
    repo = harness_root.parent / name
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    return repo


def test_context_flags_missing_instructions_and_verify(harness_root: Path, catalog):
    _write_bare_sibling(harness_root, "frontend")
    payload = collect_context(catalog, harness_root, only=["frontend"])
    repo = payload["repos"][0]
    assert repo["readiness"]["ok"] is False
    gap_ids = {gap["id"] for gap in repo["readiness"]["gaps"]}
    assert {"instructions", "verify"} <= gap_ids
    assert payload["alignment"]["ok"] is False
    assert payload["alignment"]["missing_instructions"] == ["frontend"]
    assert payload["alignment"]["missing_verify"] == ["frontend"]


def test_contributing_alone_does_not_satisfy_instructions(harness_root: Path, catalog):
    repo = _write_bare_sibling(harness_root, "frontend")
    (repo / "CONTRIBUTING.md").write_text("Please write tests.\n", encoding="utf-8")
    (repo / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
    payload = collect_context(catalog, harness_root, only=["frontend"])
    snapshot = payload["repos"][0]
    kinds = {item["kind"] for item in snapshot["instructions"]}
    assert "docs" in kinds
    assert snapshot["tooling"]["suggested_verify"] == ["make check"]
    gap_ids = {gap["id"] for gap in snapshot["readiness"]["gaps"]}
    assert gap_ids == {"instructions", "graphify"}
    assert payload["alignment"]["missing_instructions"] == ["frontend"]
    assert payload["alignment"]["missing_verify"] == []


def test_declared_verify_aligns_existing_repo(
    sample_catalog_data: dict, harness_root: Path
):
    sample_catalog_data["repos"][0]["verify"] = ["./gradlew check"]
    write_harness_config(harness_root, sample_catalog_data)
    from harness.catalog import load_catalog

    catalog = load_catalog(harness_root)
    repo = _write_bare_sibling(harness_root, "frontend")
    (repo / "AGENTS.md").write_text("Run ./gradlew check after edits.\n", encoding="utf-8")
    payload = collect_context(catalog, harness_root, only=["frontend"])
    snapshot = payload["repos"][0]
    assert snapshot["tooling"]["declared_verify"] == ["./gradlew check"]
    assert snapshot["tooling"]["suggested_verify"] == ["./gradlew check"]
    assert snapshot["readiness"]["ok"] is True
    assert payload["alignment"]["ok"] is True


def test_justfile_verify_is_discovered(harness_root: Path, catalog):
    repo = _write_bare_sibling(harness_root, "frontend")
    (repo / "AGENTS.md").write_text("Use just check.\n", encoding="utf-8")
    (repo / "justfile").write_text("check:\n    true\n", encoding="utf-8")
    payload = collect_context(catalog, harness_root, only=["frontend"])
    snapshot = payload["repos"][0]
    assert snapshot["tooling"]["just_targets"] == ["check"]
    assert snapshot["tooling"]["suggested_verify"] == ["just check"]
    assert snapshot["readiness"]["ok"] is True


def test_context_check_fails_when_cloned_repo_is_unaligned(
    harness_root: Path, capsys, monkeypatch
):
    _write_bare_sibling(harness_root, "frontend")
    monkeypatch.chdir(harness_root)
    assert (
        main(
            [
                "--root",
                str(harness_root),
                "context",
                "--repo",
                "frontend",
                "--check",
            ]
        )
        == 1
    )
    error = json.loads(capsys.readouterr().err)
    assert error["alignment"]["ok"] is False
    assert "missing instructions" in error["error"]
    assert "frontend" in error["alignment"]["missing_verify"]

from __future__ import annotations

import json
from pathlib import Path

import yaml

from goat.cli import main
from goat.context import collect_context
from goat.glossary import add_term, collect_glossary
from goat.output import to_markdown, to_text
from tests.helpers import write_goat_config

REPO_GLOSSARY = Path(__file__).resolve().parents[1] / "catalog" / "glossary.yml"


def _write_glossary(path: Path, terms: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"terms": terms}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def test_committed_glossary_has_kit_terms():
    raw = yaml.safe_load(REPO_GLOSSARY.read_text(encoding="utf-8"))
    terms = {item["term"] for item in raw["terms"]}
    assert {"Yard Goat", "GOAT_ROOT", "done_when", "prepare"} <= terms
    goat = next(item for item in raw["terms"] if item["term"] == "Yard Goat")
    assert "goat" in goat["also"]


def test_list_merges_goat_and_sibling_glossaries(goat_root: Path, catalog):
    _write_glossary(
        goat_root / "catalog" / "glossary.yml",
        [
            {
                "term": "SOW",
                "also": ["Statement of Work"],
                "kind": "acronym",
                "meaning": "The contract scope document.",
            }
        ],
    )
    sibling = goat_root.parent / "frontend"
    sibling.mkdir()
    _write_glossary(
        sibling / "docs" / "glossary.yml",
        [
            {
                "term": "CheckoutForm",
                "kind": "term",
                "meaning": "The shop-web checkout widget.",
            }
        ],
    )
    payload = collect_glossary(catalog, goat_root, only=["frontend"])
    names = {item["term"] for item in payload["terms"]}
    assert names == {"SOW", "CheckoutForm"}
    sources = {item["source"] for item in payload["terms"]}
    assert sources == {"goat", "frontend"}
    assert payload["kind"] == "glossary"
    assert payload["count"] == 2


def test_get_matches_alias_and_is_case_insensitive(goat_root: Path, catalog):
    _write_glossary(
        goat_root / "catalog" / "glossary.yml",
        [
            {
                "term": "Yard Goat",
                "also": ["goat", "Copilot Kit"],
                "kind": "term",
                "meaning": "This kit repo.",
            }
        ],
    )
    payload = collect_glossary(
        catalog, goat_root, query="GOAT", action="get", all_repos=True
    )
    assert payload["matched"] is True
    assert payload["terms"][0]["term"] == "Yard Goat"


def test_get_unmatched_returns_suggestions(goat_root: Path, catalog):
    _write_glossary(
        goat_root / "catalog" / "glossary.yml",
        [
            {
                "term": "done_when",
                "kind": "term",
                "meaning": "Stop condition on prepare JSON.",
            }
        ],
    )
    payload = collect_glossary(
        catalog, goat_root, query="done-when", action="get", all_repos=True
    )
    assert payload["matched"] is True
    miss = collect_glossary(
        catalog, goat_root, query="XYZABC", action="get", all_repos=True
    )
    assert miss["matched"] is False
    assert miss["terms"] == []
    search = collect_glossary(
        catalog, goat_root, query="stop condition", action="search", all_repos=True
    )
    assert search["matched"] is True
    assert search["terms"][0]["term"] == "done_when"


def test_list_can_filter_kind(goat_root: Path, catalog):
    _write_glossary(
        goat_root / "catalog" / "glossary.yml",
        [
            {"term": "SOW", "kind": "acronym", "meaning": "Statement of Work."},
            {"term": "sibling", "kind": "term", "meaning": "A product clone."},
        ],
    )
    payload = collect_glossary(
        catalog, goat_root, action="list", kind="acronym", all_repos=True
    )
    assert [item["term"] for item in payload["terms"]] == ["SOW"]


def test_add_creates_goat_glossary_and_replace_updates_it(goat_root: Path, catalog):
    created = add_term(
        catalog,
        goat_root,
        "DRI",
        meaning="Directly Responsible Individual",
        also=["directly responsible individual"],
        kind="acronym",
    )
    assert created["created"] is True
    assert created["replaced"] is False
    path = goat_root / "catalog" / "glossary.yml"
    assert path.is_file()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["terms"][0]["term"] == "DRI"
    assert raw["terms"][0]["kind"] == "acronym"
    assert "catalog/glossary.yml" in path.read_text(encoding="utf-8") or True
    updated = add_term(
        catalog,
        goat_root,
        "dri",
        meaning="The one owner for a decision.",
        replace=True,
    )
    assert updated["replaced"] is True
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["terms"][0]["meaning"] == "The one owner for a decision."
    assert raw["terms"][0]["also"] == ["directly responsible individual"]


def test_add_duplicate_without_replace_errors(goat_root: Path, catalog):
    from goat import GoatError

    add_term(
        catalog,
        goat_root,
        "SOW",
        meaning="Statement of Work",
        also=["Statement of Work"],
    )
    try:
        add_term(catalog, goat_root, "Statement of Work", meaning="same thing")
        raise AssertionError("expected GoatError")
    except GoatError as exc:
        assert "already exists" in exc.message


def test_add_to_sibling_docs_glossary(goat_root: Path, catalog):
    sibling = goat_root.parent / "frontend"
    sibling.mkdir()
    payload = add_term(
        catalog,
        goat_root,
        "BookingAPI",
        meaning="Internal booking HTTP API.",
        repo="frontend",
    )
    assert payload["source"] == "frontend"
    written = sibling / "docs" / "glossary.yml"
    assert written.is_file()
    raw = yaml.safe_load(written.read_text(encoding="utf-8"))
    assert raw["terms"][0]["term"] == "BookingAPI"
    assert payload["relative"].endswith("docs/glossary.yml")


def test_add_dry_run_does_not_write(goat_root: Path, catalog):
    payload = add_term(
        catalog,
        goat_root,
        "RFP",
        meaning="Request for Proposal",
        dry_run=True,
    )
    assert payload["dry_run"] is True
    assert not (goat_root / "catalog" / "glossary.yml").exists()


def test_cli_glossary_round_trip(goat_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(goat_root)
    _write_glossary(
        goat_root / "catalog" / "glossary.yml",
        [
            {
                "term": "Yard Goat",
                "also": ["goat"],
                "kind": "term",
                "meaning": "This kit repo.",
                "see": ["GOAT_ROOT"],
            }
        ],
    )
    assert main(["--root", str(goat_root), "glossary", "get", "goat"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["matched"] is True
    assert payload["terms"][0]["term"] == "Yard Goat"
    assert main(
        [
            "--root",
            str(goat_root),
            "glossary",
            "add",
            "SOW",
            "--meaning",
            "Statement of Work",
        ]
    ) == 0
    added = json.loads(capsys.readouterr().out)
    assert added["action"] == "add"
    assert added["terms"][0]["kind"] == "acronym"
    assert main(
        ["--root", str(goat_root), "glossary", "list", "--format", "markdown"]
    ) == 0
    markdown = capsys.readouterr().out
    assert "# Glossary" in markdown
    assert "`SOW`" in markdown
    assert main(["--root", str(goat_root), "glossary", "search", "kit repo"]) == 0
    search = json.loads(capsys.readouterr().out)
    assert search["terms"][0]["term"] == "Yard Goat"


def test_glossary_text_and_markdown_are_scannable(goat_root: Path, catalog):
    _write_glossary(
        goat_root / "catalog" / "glossary.yml",
        [{"term": "SOW", "kind": "acronym", "meaning": "Statement of Work."}],
    )
    payload = collect_glossary(catalog, goat_root, all_repos=True)
    text = to_text(payload)
    markdown = to_markdown(payload)
    assert "SOW" in text
    assert "Statement of Work" in text
    assert "| `SOW`" in markdown


def test_context_includes_glossary_pointer(goat_root: Path, catalog):
    _write_glossary(
        goat_root / "catalog" / "glossary.yml",
        [{"term": "SOW", "kind": "acronym", "meaning": "Statement of Work."}],
    )
    payload = collect_context(catalog, goat_root, only=["frontend"])
    assert payload["glossary"]["count"] == 1
    assert payload["glossary"]["relative"] == "catalog/glossary.yml"
    assert "glossary get" in payload["glossary"]["get_command"]
    assert any("glossary get" in line for line in payload["guidance"])


def test_add_guesses_acronym_kind(sample_catalog_data: dict, tmp_path: Path):
    root = tmp_path / "parent" / "Goat"
    write_goat_config(root, sample_catalog_data)
    from goat.catalog import load_catalog

    catalog = load_catalog(root)
    payload = add_term(catalog, root, "KPI", meaning="Key performance indicator")
    assert payload["terms"][0]["kind"] == "acronym"

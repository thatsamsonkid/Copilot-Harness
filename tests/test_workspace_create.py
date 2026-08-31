from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
import yaml

from coboose import CobooseError
from coboose.catalog import load_catalog
from coboose.cli import main
from coboose.prompt import PromptSession
from coboose.workspace_create import (
    create_workspace,
    format_project_menu,
    parse_project_selection,
    slugify,
    title_from_id,
    validate_workspace_id,
)
from tests.helpers import write_coboose_config


def test_slugify_and_validate():
    assert slugify("Checkout Flow") == "checkout-flow"
    assert validate_workspace_id("Checkout Flow") == "checkout-flow"
    assert title_from_id("checkout-flow") == "Checkout Flow"
    with pytest.raises(CobooseError, match="slug"):
        validate_workspace_id("***")


def test_parse_project_selection_numbers_names_tags_and_all(catalog):
    repos = catalog.repos
    assert parse_project_selection("1, backend", repos) == ["frontend", "backend"]
    assert parse_project_selection("1-2", repos) == ["frontend", "backend"]
    assert parse_project_selection("tag:ui", repos) == ["frontend"]
    assert parse_project_selection("all", repos) == ["frontend", "backend"]
    with pytest.raises(CobooseError, match="Unknown project"):
        parse_project_selection("missing", repos)
    with pytest.raises(CobooseError, match="out of range"):
        parse_project_selection("9", repos)
    with pytest.raises(CobooseError, match="No repositories.yml entry has tag"):
        parse_project_selection("tag:nope", repos)
    with pytest.raises(CobooseError, match="at least one"):
        parse_project_selection("   ", repos)


def test_format_project_menu_lists_manifest(catalog):
    menu = format_project_menu(catalog.repos)
    assert "1. frontend" in menu
    assert "tags: ui" in menu
    assert "2. backend" in menu


def test_format_project_menu_shows_grouped_path(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["name"] = "shop-web"
    sample_catalog_data["repos"][0]["group"] = "frontend"
    sample_catalog_data["repos"][0].pop("path", None)
    sample_catalog_data["workspaces"][0]["folders"] = ["shop-web", "backend"]
    root = tmp_path / "coboose"
    write_coboose_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    menu = format_project_menu(catalog.repos)
    assert "1. shop-web" in menu
    assert "path: frontend/shop-web" in menu


def test_create_workspace_with_flags(catalog, coboose_root: Path):
    payload = create_workspace(
        catalog,
        coboose_root,
        workspace_id="checkout",
        name="Checkout",
        description="Cart and checkout",
        folders=["frontend", "backend"],
        match_keywords=["cart", "checkout"],
        prompt=PromptSession(interactive=False),
    )
    assert payload["created"] is True
    assert payload["generated"] is True
    assert payload["workspace"]["id"] == "checkout"
    assert payload["workspace"]["folders"] == ["frontend", "backend"]
    assert payload["folders"] == ["coboose", "frontend", "backend"]
    path = coboose_root / "workspaces" / "checkout.code-workspace"
    assert path.exists()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert [folder["name"] for folder in document["folders"]] == [
        "coboose",
        "frontend",
        "backend",
    ]

    refreshed = load_catalog(coboose_root)
    created = refreshed.workspace("checkout")
    assert created.description == "Cart and checkout"
    assert created.folders == ["frontend", "backend"]
    assert created.match.keywords == ["cart", "checkout"]


def test_create_workspace_requires_flags_without_tty(catalog, coboose_root: Path):
    with pytest.raises(CobooseError, match="--id"):
        create_workspace(
            catalog,
            coboose_root,
            prompt=PromptSession(interactive=False),
        )
    with pytest.raises(CobooseError, match="--projects"):
        create_workspace(
            catalog,
            coboose_root,
            workspace_id="checkout",
            prompt=PromptSession(interactive=False),
        )


def test_create_workspace_rejects_unknown_and_duplicate(catalog, coboose_root: Path):
    with pytest.raises(CobooseError, match="Unknown repo"):
        create_workspace(
            catalog,
            coboose_root,
            workspace_id="checkout",
            folders=["missing"],
            prompt=PromptSession(interactive=False),
        )
    with pytest.raises(CobooseError, match="already exists"):
        create_workspace(
            catalog,
            coboose_root,
            workspace_id="frontend",
            folders=["frontend"],
            prompt=PromptSession(interactive=False),
        )


def test_create_workspace_force_replaces(catalog, coboose_root: Path):
    payload = create_workspace(
        catalog,
        coboose_root,
        workspace_id="frontend",
        folders=["frontend"],
        force=True,
        prompt=PromptSession(interactive=False),
    )
    assert payload["replaced"] is True
    assert payload["created"] is False
    refreshed = load_catalog(coboose_root)
    assert refreshed.workspace("frontend").folders == ["frontend"]
    assert {item.id for item in refreshed.workspaces} == {"frontend", "backend"}


def test_create_workspace_dry_run_does_not_write(catalog, coboose_root: Path):
    payload = create_workspace(
        catalog,
        coboose_root,
        workspace_id="checkout",
        folders=["frontend"],
        dry_run=True,
        prompt=PromptSession(interactive=False),
    )
    assert payload["dry_run"] is True
    assert payload["generated"] is False
    assert not (coboose_root / "workspaces" / "checkout.code-workspace").exists()
    with pytest.raises(CobooseError, match="Unknown workspace"):
        load_catalog(coboose_root).workspace("checkout")


def test_create_workspace_prompts_for_projects(catalog, coboose_root: Path):
    stdin = io.StringIO("checkout\nCheckout\nCart flow\n1,2\n\n")
    stderr = io.StringIO()
    payload = create_workspace(
        catalog,
        coboose_root,
        prompt=PromptSession(stdin=stdin, stderr=stderr, interactive=True),
    )
    menu = stderr.getvalue()
    assert "Repositories from repositories.yml" in menu
    assert "1. frontend" in menu
    assert payload["workspace"]["id"] == "checkout"
    assert payload["workspace"]["folders"] == ["frontend", "backend"]
    assert payload["workspace"]["description"] == "Cart flow"
    assert load_catalog(coboose_root).workspace("checkout").folders == [
        "frontend",
        "backend",
    ]


def test_create_workspace_reprompts_invalid_selection(catalog, coboose_root: Path):
    stdin = io.StringIO("payments\n\n\nnope\n2\ny\n")
    stderr = io.StringIO()
    payload = create_workspace(
        catalog,
        coboose_root,
        prompt=PromptSession(stdin=stdin, stderr=stderr, interactive=True),
    )
    assert "Unknown project 'nope'" in stderr.getvalue()
    assert payload["workspace"]["folders"] == ["backend"]
    assert payload["workspace"]["include_coboose"] is True


def test_create_workspace_cli(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    assert (
        main(
            [
                "--root",
                str(coboose_root),
                "workspace",
                "create",
                "checkout",
                "--projects",
                "frontend,backend",
                "--description",
                "Cart",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["created"] is True
    assert payload["workspace"]["id"] == "checkout"
    assert (coboose_root / "workspaces" / "checkout.code-workspace").exists()


def test_create_workspace_cli_no_prompt_requires_projects(
    coboose_root: Path, capsys, monkeypatch
):
    monkeypatch.chdir(coboose_root)
    assert (
        main(
            [
                "--root",
                str(coboose_root),
                "workspace",
                "create",
                "checkout",
                "--no-prompt",
            ]
        )
        == 1
    )
    error = json.loads(capsys.readouterr().err)
    assert "--projects" in error["error"]


def test_create_workspace_preserves_stack_comments(
    tmp_path: Path, sample_catalog_data: dict
):
    root = tmp_path / "parent" / "Coboose"
    write_coboose_config(root, sample_catalog_data)
    stack = root / "catalog" / "stack.yaml"
    stack.write_text(
        "# Feature workspaces\n"
        "jira:\n"
        "  include_comments: true\n"
        "\n"
        "workspaces:\n"
        "  - id: frontend\n"
        "    name: Frontend\n"
        "    folders: [frontend, backend]\n"
        "  - id: backend\n"
        "    name: Backend\n"
        "    folders: [backend]\n"
        "    fallback: true\n",
        encoding="utf-8",
    )
    catalog = load_catalog(root)
    create_workspace(
        catalog,
        root,
        workspace_id="checkout",
        folders=["frontend"],
        prompt=PromptSession(interactive=False),
    )
    text = stack.read_text(encoding="utf-8")
    assert text.startswith("# Feature workspaces")
    assert "jira:" in text
    assert "include_comments: true" in text
    data = yaml.safe_load(text)
    assert [item["id"] for item in data["workspaces"]] == [
        "frontend",
        "backend",
        "checkout",
    ]


def test_gitignore_covers_generated_workspace_files():
    gitignore = Path(__file__).resolve().parents[1] / ".gitignore"
    text = gitignore.read_text(encoding="utf-8")
    assert "workspaces/*.code-workspace" in text
    assert "workspaces/personal" not in text

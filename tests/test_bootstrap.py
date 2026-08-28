from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from coboose import CobooseError
from coboose.bootstrap import append_repository, bootstrap_project
from coboose.catalog import Repo, load_catalog, parse_project_destination
from coboose.cli import main
from tests.helpers import write_coboose_config


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _bare_repo(path: Path, branch: str = "main") -> Path:
    work = path.with_name(path.name + "-work")
    work.mkdir(parents=True)
    _git(work, "init", "-b", branch)
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    (work / "README.md").write_text("starter\n", encoding="utf-8")
    _git(work, "add", "README.md")
    _git(work, "commit", "-m", "init")
    subprocess.run(
        ["git", "clone", "--bare", str(work), str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return path


def test_bootstrap_dry_run(catalog, coboose_root: Path):
    payload = bootstrap_project(
        catalog,
        coboose_root,
        template_name="web-starter",
        dest_name="shop-web",
        dry_run=True,
    )
    assert payload["dry_run"] is True
    assert payload["project"]["name"] == "shop-web"
    assert payload["project"]["action"] == "bootstrap"
    assert not (coboose_root.parent / "shop-web").exists()


def test_bootstrap_clones_and_detaches_origin(
    coboose_root: Path, sample_catalog_data: dict, tmp_path: Path
):
    remotes = tmp_path / "remotes"
    sample_catalog_data["templates"][0]["url"] = str(_bare_repo(remotes / "web-starter.git"))
    write_coboose_config(coboose_root, sample_catalog_data)
    catalog = load_catalog(coboose_root)

    payload = bootstrap_project(
        catalog,
        coboose_root,
        template_name="web-starter",
        dest_name="shop-web",
    )
    dest = coboose_root.parent / "shop-web"
    assert dest.is_dir()
    assert (dest / "README.md").read_text() == "starter\n"
    remotes_now = subprocess.check_output(
        ["git", "-C", str(dest), "remote"], text=True
    ).split()
    assert remotes_now == ["template"]
    assert payload["project"]["remote"] == "detached"
    assert payload["registered"] is False


def test_bootstrap_fresh_git_and_register(
    coboose_root: Path, sample_catalog_data: dict, tmp_path: Path
):
    remotes = tmp_path / "remotes"
    sample_catalog_data["templates"][0]["url"] = str(_bare_repo(remotes / "web-starter.git"))
    write_coboose_config(coboose_root, sample_catalog_data)
    catalog = load_catalog(coboose_root)
    origin = "git@github.com:acme/shop-web.git"

    payload = bootstrap_project(
        catalog,
        coboose_root,
        template_name="web-starter",
        dest_name="shop-web",
        fresh_git=True,
        register=True,
        remote=origin,
        tags=["ui", "web"],
    )
    dest = coboose_root.parent / "shop-web"
    log = subprocess.check_output(
        ["git", "-C", str(dest), "log", "--oneline"], text=True
    )
    assert "Bootstrap from web-starter" in log
    assert log.count("\n") == 1
    remotes_now = subprocess.check_output(
        ["git", "-C", str(dest), "remote", "-v"], text=True
    )
    assert "origin" in remotes_now
    assert "acme/shop-web.git" in remotes_now
    assert payload["registered"] is True

    manifest = yaml.safe_load((coboose_root / "repositories.yml").read_text())
    names = [item["name"] for item in manifest["repositories"]]
    assert "shop-web" in names
    added = next(item for item in manifest["repositories"] if item["name"] == "shop-web")
    assert added["url"] == origin
    assert added["tags"] == ["ui", "web"]


def test_parse_project_destination_group_and_nested_name():
    assert parse_project_destination("shop-web", "frontend") == (
        "shop-web",
        "frontend/shop-web",
        "frontend",
    )
    assert parse_project_destination("frontend/shop-web") == (
        "shop-web",
        "frontend/shop-web",
        "frontend",
    )
    with pytest.raises(CobooseError, match="inside group"):
        parse_project_destination("backend/api", "frontend")


def test_bootstrap_into_group_and_register(
    coboose_root: Path, sample_catalog_data: dict, tmp_path: Path
):
    remotes = tmp_path / "remotes"
    sample_catalog_data["templates"][0]["url"] = str(_bare_repo(remotes / "web-starter.git"))
    write_coboose_config(coboose_root, sample_catalog_data)
    catalog = load_catalog(coboose_root)

    payload = bootstrap_project(
        catalog,
        coboose_root,
        template_name="web-starter",
        dest_name="shop-web",
        group="apps",
        register=True,
        remote="git@github.com:acme/shop-web.git",
        tags=["ui", "web"],
    )
    dest = coboose_root.parent / "apps" / "shop-web"
    assert dest.is_dir()
    assert payload["project"]["name"] == "shop-web"
    assert payload["project"]["group"] == "apps"
    assert payload["project"]["relpath"] == "apps/shop-web"
    assert payload["registered"] is True

    manifest = yaml.safe_load((coboose_root / "repositories.yml").read_text())
    added = next(item for item in manifest["repositories"] if item["name"] == "shop-web")
    assert added["group"] == "apps"
    assert "path" not in added


def test_bootstrap_refuses_existing_destination(
    coboose_root: Path, sample_catalog_data: dict, tmp_path: Path
):
    remotes = tmp_path / "remotes"
    sample_catalog_data["templates"][0]["url"] = str(_bare_repo(remotes / "web-starter.git"))
    write_coboose_config(coboose_root, sample_catalog_data)
    dest = coboose_root.parent / "shop-web"
    dest.mkdir()
    catalog = load_catalog(coboose_root)
    with pytest.raises(CobooseError, match="already exists"):
        bootstrap_project(
            catalog, coboose_root, template_name="web-starter", dest_name="shop-web"
        )


def test_bootstrap_blocks_placeholder_url(
    coboose_root: Path, sample_catalog_data: dict
):
    sample_catalog_data["templates"][0]["url"] = (
        "git@github.com:YOUR_ORG/web-starter.git"
    )
    write_coboose_config(coboose_root, sample_catalog_data)
    catalog = load_catalog(coboose_root)
    with pytest.raises(CobooseError, match="placeholder"):
        bootstrap_project(
            catalog, coboose_root, template_name="web-starter", dest_name="shop-web"
        )


def test_append_repository_matches_shipped_indent(tmp_path: Path):
    path = tmp_path / "repositories.yml"
    path.write_text(
        "# comment\n"
        "parent_dir: ..\n"
        "\n"
        "repositories:\n"
        "  - name: frontend\n"
        "    url: git@github.com:acme/frontend.git\n"
        "    tags: [ui]\n",
        encoding="utf-8",
    )
    append_repository(
        path,
        Repo(
            name="new-service",
            url="git@github.com:acme/new-service.git",
            path="new-service",
            tags=["api"],
            description="Fresh service",
        ),
    )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert [item["name"] for item in data["repositories"]] == ["frontend", "new-service"]
    assert "# comment" in path.read_text(encoding="utf-8")


def test_append_repository_preserves_existing_entries(coboose_root: Path):
    path = coboose_root / "repositories.yml"
    original = path.read_text(encoding="utf-8")
    append_repository(
        path,
        Repo(
            name="new-service",
            url="git@github.com:acme/new-service.git",
            path="new-service",
            tags=["api"],
            description="Fresh service",
        ),
    )
    text = path.read_text(encoding="utf-8")
    assert original.strip() in text
    assert "name: new-service" in text
    with pytest.raises(CobooseError, match="already listed"):
        append_repository(
            path,
            Repo(
                name="new-service",
                url="git@github.com:acme/new-service.git",
                path="new-service",
                tags=["api"],
            ),
        )


def test_cli_templates_and_bootstrap_dry_run(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    assert main(["--root", str(coboose_root), "templates"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [item["name"] for item in listed["templates"]] == [
        "web-starter",
        "api-starter",
    ]

    assert main(["--root", str(coboose_root), "templates", "--tag", "api"]) == 0
    filtered = json.loads(capsys.readouterr().out)
    assert [item["name"] for item in filtered["templates"]] == ["api-starter"]

    assert main(["--root", str(coboose_root), "templates", "web-starter"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["template"]["name"] == "web-starter"

    assert main(["--root", str(coboose_root), "templates", "--format", "text"]) == 0
    text = capsys.readouterr().out
    assert "web-starter" in text
    assert "Bootstrap: coboose bootstrap --template" in text

    assert (
        main(
            [
                "--root",
                str(coboose_root),
                "bootstrap",
                "--template",
                "web-starter",
                "--name",
                "shop-web",
                "--dry-run",
            ]
        )
        == 0
    )
    boot = json.loads(capsys.readouterr().out)
    assert boot["project"]["name"] == "shop-web"
    assert boot["dry_run"] is True

    assert (
        main(
            [
                "--root",
                str(coboose_root),
                "bootstrap",
                "api-starter",
                "--name",
                "shop-api",
                "--dry-run",
            ]
        )
        == 0
    )
    positional = json.loads(capsys.readouterr().out)
    assert positional["template"]["name"] == "api-starter"

    assert (
        main(
            [
                "--root",
                str(coboose_root),
                "bootstrap",
                "--template",
                "web-starter",
                "--name",
                "shop-web",
                "--group",
                "apps",
                "--dry-run",
            ]
        )
        == 0
    )
    grouped = json.loads(capsys.readouterr().out)
    assert grouped["project"]["name"] == "shop-web"
    assert grouped["project"]["group"] == "apps"
    assert grouped["project"]["relpath"] == "apps/shop-web"


def test_cli_bootstrap_requires_template(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    assert main(["--root", str(coboose_root), "bootstrap", "--name", "x"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert "listed template" in error["error"]

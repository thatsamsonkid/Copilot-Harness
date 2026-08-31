from __future__ import annotations

import json
from pathlib import Path

import pytest

from goat import GoatError
from goat.catalog import load_catalog
from goat.cli import main
from goat.envspec import (
    EnvVar,
    find_var,
    list_env,
    load_env_spec,
    resolve_var,
    set_env_value,
    vars_for,
)
from goat.keychain import SOURCE_ENV, SOURCE_KEYCHAIN, SOURCE_MISSING, SERVICE
from tests.helpers import write_goat_config


def test_defaults_when_env_yaml_missing(tmp_path: Path):
    variables, source = load_env_spec(tmp_path / "missing.yaml")
    assert source is None
    assert [item.name for item in variables] == [
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "FIGMA_ACCESS_TOKEN",
    ]
    assert find_var(variables, "FIGMA_TOKEN").secret is True
    assert find_var(variables, "FIGMA_ACCESS_TOKEN").required is False
    assert find_var(variables, "FIGMA_ACCESS_TOKEN").keychain_account == (
        "figma-access-token"
    )
    assert find_var(variables, "JIRA_TOKEN").secret is True
    assert find_var(variables, "JIRA_API_TOKEN").keychain_account == "jira-api-token"


def test_workspace_scoped_and_workspace_env_list(
    tmp_path: Path, sample_catalog_data: dict, isolated_keychain, monkeypatch
):
    sample_catalog_data["variables"] = [
        {
            "name": "JIRA_BASE_URL",
            "secret": False,
            "hint": "https://acme.atlassian.net",
        },
        {"name": "JIRA_EMAIL", "secret": False},
        {
            "name": "JIRA_API_TOKEN",
            "secret": True,
            "account": "jira-api-token",
        },
        {
            "name": "BACKEND_API_TOKEN",
            "secret": True,
            "workspaces": ["backend"],
        },
    ]
    sample_catalog_data["workspaces"][0]["env"] = ["BACKEND_API_TOKEN"]
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    catalog = load_catalog(root)
    names = {item.name for item in catalog.env_vars}
    assert "BACKEND_API_TOKEN" in names
    frontend = vars_for(catalog.env_vars, "frontend", catalog.workspace("frontend").env)
    assert "BACKEND_API_TOKEN" in [item.name for item in frontend]
    backend_only = vars_for(catalog.env_vars, "backend")
    assert "BACKEND_API_TOKEN" in [item.name for item in backend_only]
    shared = vars_for(catalog.env_vars, "mobile")
    assert "BACKEND_API_TOKEN" not in [item.name for item in shared]


def test_rejects_unknown_workspace_scope(
    tmp_path: Path, sample_catalog_data: dict
):
    sample_catalog_data["variables"] = [
        {"name": "JIRA_BASE_URL", "secret": False},
        {"name": "JIRA_EMAIL", "secret": False},
        {"name": "JIRA_API_TOKEN", "secret": True},
        {"name": "NOPE_TOKEN", "secret": True, "workspaces": ["missing-ws"]},
    ]
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    with pytest.raises(GoatError, match="unknown workspace"):
        load_catalog(root)


def test_set_secret_uses_keychain_and_list_omits_value(
    goat_root: Path, isolated_keychain, monkeypatch
):
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_TOKEN", raising=False)
    variable = EnvVar(
        name="JIRA_API_TOKEN",
        secret=True,
        aliases=("JIRA_TOKEN",),
        account="jira-api-token",
    )
    monkeypatch.setenv("JIRA_API_TOKEN", "ATLASSIAN-SECRET")
    payload = set_env_value(variable, goat_root, from_env=True)
    assert payload["stored"] is True
    assert payload["source"] == SOURCE_KEYCHAIN
    assert "ATLASSIAN-SECRET" not in json.dumps(payload)
    assert isolated_keychain.get_password(SERVICE, "jira-api-token") == "ATLASSIAN-SECRET"

    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    value, source = resolve_var(variable)
    assert value == "ATLASSIAN-SECRET"
    assert source == SOURCE_KEYCHAIN

    listing = list_env([variable], goat_root)
    assert listing["variables"][0]["present"] is True
    assert listing["variables"][0]["source"] == SOURCE_KEYCHAIN
    assert listing["missing"] == []
    assert "ATLASSIAN-SECRET" not in json.dumps(listing)
    assert resolve_var(EnvVar(name="MISSING_KEY")) == ("", SOURCE_MISSING)


def test_cli_env_list_and_set(
    goat_root: Path, isolated_keychain, monkeypatch, capsys
):
    for name in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    (goat_root / ".env").write_text(
        "JIRA_BASE_URL=https://acme.atlassian.net\n"
        "JIRA_EMAIL=ada@acme.test\n"
        "JIRA_API_TOKEN=ATLASSIAN-SECRET\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(goat_root)
    assert main(["--root", str(goat_root), "env", "set", "JIRA_API_TOKEN", "--from-env"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stored"] is True
    assert payload["source"] == SOURCE_KEYCHAIN
    assert "ATLASSIAN-SECRET" not in json.dumps(payload)

    assert main(["--root", str(goat_root), "env", "list"]) == 0
    listing = json.loads(capsys.readouterr().out)
    by_name = {row["name"]: row for row in listing["variables"]}
    assert by_name["JIRA_BASE_URL"]["present"] is True
    assert by_name["JIRA_BASE_URL"]["secret"] is False
    assert by_name["JIRA_API_TOKEN"]["source"] == SOURCE_KEYCHAIN
    assert by_name["JIRA_API_TOKEN"]["store"] == "keychain"
    assert "ATLASSIAN-SECRET" not in json.dumps(listing)


def test_set_non_secret_writes_env_file(goat_root: Path, monkeypatch):
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    variable = EnvVar(
        name="JIRA_BASE_URL",
        prompt="Atlassian site URL",
    )
    payload = set_env_value(
        variable,
        goat_root,
        prompt_fn=lambda _msg: "https://acme.atlassian.net",
        stdin_isatty=True,
    )
    assert payload["source"] == SOURCE_ENV
    assert "JIRA_BASE_URL=https://acme.atlassian.net" in (
        goat_root / ".env"
    ).read_text(encoding="utf-8")

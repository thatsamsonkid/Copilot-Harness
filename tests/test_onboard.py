from __future__ import annotations

import json
from pathlib import Path

from coboose.cli import main
from coboose.onboard import onboarding_steps, run_init
from coboose.uv_check import detect_uv


def _clear_jira_env(monkeypatch) -> None:
    for name in (
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_USERNAME",
        "JIRA_API_TOKEN",
        "JIRA_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def test_init_lists_missing_jira_keys_without_reading_secrets(
    coboose_root: Path, catalog, monkeypatch, capsys
):
    _clear_jira_env(monkeypatch)
    example = coboose_root / ".env.example"
    example.write_text(
        "JIRA_BASE_URL=\nJIRA_EMAIL=\nJIRA_API_TOKEN=\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(coboose_root)
    assert main(["--root", str(coboose_root), "init"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["created_env"] is True
    assert payload["ready"] is False
    assert payload["token_docs"] == "docs/jira-api-token.md"
    assert payload["keychain_guide"]["macos"]["store"] == "macOS Keychain"
    assert payload["keychain_guide"]["windows"]["store"] == "Windows Credential Manager"
    assert payload["env"]["variables"][0]["name"] == "JIRA_BASE_URL"
    assert all("value" not in row for row in payload["env"]["variables"])
    assert payload["uv_docs"] == "docs/install-uv.md"
    assert "macos" in payload["uv"]["install"]
    assert "windows" in payload["uv"]["install"]
    ids = {step["id"]: step for step in payload["steps"]}
    assert "uv" in ids
    assert "cli_path" in ids
    assert ids["cli_path"]["optional"] is True
    assert ids["jira_api_token"]["ok"] is False
    assert "docs/jira-api-token.md" in ids["jira_api_token"]["action"]
    assert "jira login" in ids["jira_api_token"]["action"]
    assert ids["figma_access_token"]["optional"] is True
    assert ids["figma_access_token"]["ok"] is False
    assert "figma login" in ids["figma_access_token"]["action"]
    dumped = json.dumps(payload)
    assert "ATLASSIAN-SECRET" not in dumped


def test_interactive_init_stores_token_in_keychain(
    coboose_root: Path, catalog, monkeypatch, isolated_keychain
):
    _clear_jira_env(monkeypatch)
    answers = iter(
        [
            "https://acme.atlassian.net",
            "ada@acme.test",
        ]
    )
    payload = run_init(
        catalog,
        coboose_root,
        interactive=True,
        prompt_fn=lambda _msg: next(answers),
        secret_fn=lambda _msg: "ATLASSIAN-SECRET",
    )
    env_text = (coboose_root / ".env").read_text(encoding="utf-8")
    assert "JIRA_EMAIL=ada@acme.test" in env_text
    assert "ATLASSIAN-SECRET" not in env_text
    assert "ATLASSIAN-SECRET" not in json.dumps(payload)
    assert "JIRA_API_TOKEN" not in payload["wrote_keys"]
    assert set(payload["wrote_keys"]) == {
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
    }
    assert payload["token_store"] == "keychain"
    assert isolated_keychain.get_password("coboose", "jira-api-token") == (
        "ATLASSIAN-SECRET"
    )


def test_interactive_init_falls_back_to_env_without_keychain(
    coboose_root: Path, catalog, monkeypatch
):
    from coboose.keychain import UnavailableStore, set_store

    _clear_jira_env(monkeypatch)
    set_store(UnavailableStore(), backend="unavailable", available=False)
    answers = iter(
        [
            "https://acme.atlassian.net",
            "ada@acme.test",
        ]
    )
    payload = run_init(
        catalog,
        coboose_root,
        interactive=True,
        prompt_fn=lambda _msg: next(answers),
        secret_fn=lambda _msg: "ATLASSIAN-SECRET",
    )
    env_text = (coboose_root / ".env").read_text(encoding="utf-8")
    assert "JIRA_API_TOKEN=ATLASSIAN-SECRET" in env_text
    assert "ATLASSIAN-SECRET" not in json.dumps(payload)
    assert payload["token_store"] == "env"
    assert set(payload["wrote_keys"]) == {
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
    }


def test_init_treats_keychain_token_as_present(
    coboose_root: Path, catalog, monkeypatch, isolated_keychain
):
    _clear_jira_env(monkeypatch)
    (coboose_root / ".env").write_text(
        "JIRA_BASE_URL=https://acme.atlassian.net\nJIRA_EMAIL=ada@acme.test\n",
        encoding="utf-8",
    )
    isolated_keychain.set_password("coboose", "jira-api-token", "hidden")
    payload = run_init(catalog, coboose_root)
    ids = {step["id"]: step for step in payload["steps"]}
    assert ids["jira_api_token"]["ok"] is True
    assert "keychain" in ids["jira_api_token"]["detail"].lower() or "in-memory" in (
        ids["jira_api_token"]["detail"].lower()
    )
    assert payload["token_store"] == "keychain"
    assert "hidden" not in json.dumps(payload)


def test_init_treats_env_file_values_as_present(
    coboose_root: Path, catalog, monkeypatch
):
    _clear_jira_env(monkeypatch)
    (coboose_root / ".env").write_text(
        "JIRA_BASE_URL=https://acme.atlassian.net\n"
        "JIRA_EMAIL=ada@acme.test\n"
        "JIRA_API_TOKEN=hidden\n",
        encoding="utf-8",
    )
    payload = run_init(catalog, coboose_root)
    ids = {step["id"]: step for step in payload["steps"]}
    assert ids["jira_base_url"]["ok"] is True
    assert ids["jira_email"]["ok"] is True
    assert ids["jira_api_token"]["ok"] is True
    assert "hidden" not in json.dumps(payload)


def test_onboarding_uv_step_uses_os_specific_action(coboose_root: Path, catalog):
    missing = detect_uv(which=lambda _name: None, system="Windows")
    steps = onboarding_steps(catalog, coboose_root, uv=missing)
    uv_step = next(step for step in steps if step["id"] == "uv")
    assert uv_step["ok"] is False
    assert "setup.ps1" in uv_step["action"]
    assert "docs/install-uv.md" in uv_step["action"]

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from goat import GoatError
from goat.cli import main
from goat.jira_client import jira_settings_from_env
from goat.keychain import (
    ACCOUNT,
    LEGACY_SERVICE,
    SERVICE,
    SOURCE_ENV,
    SOURCE_KEYCHAIN,
    SOURCE_MISSING,
    UnavailableStore,
    get_stored_secret,
    login_token,
    logout_token,
    resolve_token,
    set_store,
    storage_guide,
    storage_guides,
)


def _clear_jira_env(monkeypatch) -> None:
    for name in (
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_USERNAME",
        "JIRA_API_TOKEN",
        "JIRA_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def test_storage_guide_covers_macos_and_windows():
    mac = storage_guide("Darwin")
    assert mac["os"] == "macOS"
    assert mac["store"] == "macOS Keychain"
    assert mac["service"] == SERVICE
    assert mac["account"] == ACCOUNT
    assert any("Keychain Access" in step for step in mac["manual_steps"])
    assert "security add-generic-password" in mac["security_cli"]

    windows = storage_guide("Windows")
    assert windows["os"] == "Windows"
    assert windows["store"] == "Windows Credential Manager"
    assert any("Credential Manager" in step for step in windows["manual_steps"])
    assert any(SERVICE in step for step in windows["manual_steps"])

    guides = storage_guides()
    assert guides["macos"]["store"] == "macOS Keychain"
    assert guides["windows"]["store"] == "Windows Credential Manager"
    assert guides["preferred_cli"] == "uv run goat jira login"


def test_resolve_token_prefers_env_then_keychain(isolated_keychain, monkeypatch):
    _clear_jira_env(monkeypatch)
    assert resolve_token() == ("", SOURCE_MISSING)

    isolated_keychain.set_password(SERVICE, ACCOUNT, "from-keychain")
    assert resolve_token() == ("from-keychain", SOURCE_KEYCHAIN)

    monkeypatch.setenv("JIRA_API_TOKEN", "from-env")
    assert resolve_token() == ("from-env", SOURCE_ENV)


def test_jira_settings_read_keychain_when_env_empty(
    isolated_keychain, monkeypatch
):
    _clear_jira_env(monkeypatch)
    monkeypatch.setenv("JIRA_BASE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "ada@acme.test")
    isolated_keychain.set_password(SERVICE, ACCOUNT, "keychain-token")
    base_url, email, token = jira_settings_from_env()
    assert base_url == "https://acme.atlassian.net"
    assert email == "ada@acme.test"
    assert token == "keychain-token"


def test_missing_token_mentions_keychain_login(monkeypatch):
    _clear_jira_env(monkeypatch)
    monkeypatch.setenv("JIRA_BASE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "ada@acme.test")
    with pytest.raises(GoatError, match="jira login") as exc:
        jira_settings_from_env()
    assert "Keychain" in exc.value.message
    assert "Credential Manager" in exc.value.message
    assert "do not paste" in exc.value.message.lower()


def test_login_from_env_moves_token_and_blanks_dotenv(
    goat_root: Path, isolated_keychain, monkeypatch
):
    _clear_jira_env(monkeypatch)
    env_path = goat_root / ".env"
    env_path.write_text(
        "JIRA_BASE_URL=https://acme.atlassian.net\n"
        "JIRA_EMAIL=ada@acme.test\n"
        "JIRA_API_TOKEN=ATLASSIAN-SECRET\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("JIRA_API_TOKEN", "ATLASSIAN-SECRET")
    payload = login_token(goat_root, from_env=True)
    assert payload["stored"] is True
    assert payload["source"] == SOURCE_KEYCHAIN
    assert payload["cleared_env"] is True
    assert "ATLASSIAN-SECRET" not in json.dumps(payload)
    assert isolated_keychain.get_password(SERVICE, ACCOUNT) == "ATLASSIAN-SECRET"
    assert "JIRA_API_TOKEN=" in env_path.read_text(encoding="utf-8")
    assert "ATLASSIAN-SECRET" not in env_path.read_text(encoding="utf-8")
    assert "JIRA_API_TOKEN" not in os.environ


def test_login_without_tty_is_refused(goat_root: Path, monkeypatch):
    _clear_jira_env(monkeypatch)
    with pytest.raises(GoatError, match="TTY"):
        login_token(goat_root, from_env=False, stdin_isatty=False)


def test_login_unavailable_keychain_fails(goat_root: Path, monkeypatch):
    _clear_jira_env(monkeypatch)
    monkeypatch.setenv("JIRA_API_TOKEN", "ATLASSIAN-SECRET")
    set_store(UnavailableStore(), backend="unavailable", available=False)
    with pytest.raises(GoatError, match="not available"):
        login_token(goat_root, from_env=True)


def test_reads_and_clears_legacy_keychain_service(isolated_keychain):
    isolated_keychain.set_password(LEGACY_SERVICE, ACCOUNT, "legacy-secret")
    assert get_stored_secret(ACCOUNT) == "legacy-secret"
    from goat.keychain import delete_stored_secret

    assert delete_stored_secret(ACCOUNT) is True
    assert isolated_keychain.get_password(LEGACY_SERVICE, ACCOUNT) is None
    assert get_stored_secret(ACCOUNT) is None


def test_logout_removes_keychain_token(goat_root: Path, isolated_keychain):
    isolated_keychain.set_password(SERVICE, ACCOUNT, "ATLASSIAN-SECRET")
    payload = logout_token(goat_root)
    assert payload["removed"] is True
    assert isolated_keychain.get_password(SERVICE, ACCOUNT) is None
    assert "ATLASSIAN-SECRET" not in json.dumps(payload)


def test_cli_login_from_env_and_doctor_report_keychain(
    goat_root: Path, isolated_keychain, monkeypatch, capsys
):
    _clear_jira_env(monkeypatch)
    (goat_root / ".env").write_text(
        "JIRA_BASE_URL=https://acme.atlassian.net\n"
        "JIRA_EMAIL=ada@acme.test\n"
        "JIRA_API_TOKEN=ATLASSIAN-SECRET\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(goat_root)
    assert main(["--root", str(goat_root), "jira", "login", "--from-env"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stored"] is True
    assert payload["present"] is True
    assert payload["guide"]["store"] in {
        "macOS Keychain",
        "Windows Credential Manager",
        "Secret Service (GNOME Keyring / KWallet)",
    }
    assert "ATLASSIAN-SECRET" not in json.dumps(payload)
    assert isolated_keychain.get_password(SERVICE, ACCOUNT) == "ATLASSIAN-SECRET"

    assert main(["--root", str(goat_root), "doctor"]) == 0
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["jira_token_source"] == "keychain"
    assert doctor["keychain"]["present"] is True
    assert any(check["name"] == "jira_token_store" for check in doctor["checks"])
    assert "ATLASSIAN-SECRET" not in json.dumps(doctor)

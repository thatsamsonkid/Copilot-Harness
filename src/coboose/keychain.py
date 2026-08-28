from __future__ import annotations

import os
import platform
import sys
from collections.abc import Callable
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Any, Protocol

from coboose import CobooseError
from coboose.envfile import upsert_env_file

SERVICE = "coboose"
ACCOUNT = "jira-api-token"
TOKEN_DOC = "docs/jira-api-token.md"

SOURCE_ENV = "env"
SOURCE_KEYCHAIN = "keychain"
SOURCE_MISSING = "missing"


class TokenStore(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...

    def set_password(self, service: str, username: str, password: str) -> None: ...

    def delete_password(self, service: str, username: str) -> None: ...


class MemoryStore:
    """In-memory store used by tests. Never used as a default runtime backend."""

    def __init__(self) -> None:
        self._passwords: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._passwords.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._passwords[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._passwords.pop((service, username), None)


class UnavailableStore:
    def get_password(self, service: str, username: str) -> str | None:
        return None

    def set_password(self, service: str, username: str, password: str) -> None:
        raise CobooseError(_unavailable_message())

    def delete_password(self, service: str, username: str) -> None:
        return None


@dataclass(frozen=True)
class KeychainStatus:
    available: bool
    present: bool
    backend: str
    os_name: str
    store_name: str
    service: str = SERVICE
    account: str = ACCOUNT

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "present": self.present,
            "backend": self.backend,
            "os": self.os_name,
            "store": self.store_name,
            "service": self.service,
            "account": self.account,
        }


_store_override: TokenStore | None = None
_backend_name_override: str | None = None
_available_override: bool | None = None


def set_store(
    store: TokenStore | None,
    *,
    backend: str | None = None,
    available: bool | None = None,
) -> None:
    """Install a token store. Tests use this to stay off the real keychain."""
    global _store_override, _backend_name_override, _available_override
    _store_override = store
    _backend_name_override = backend
    _available_override = available


def reset_store() -> None:
    set_store(None)


def env_token() -> str:
    return (
        os.environ.get("JIRA_API_TOKEN") or os.environ.get("JIRA_TOKEN") or ""
    ).strip()


def get_stored_secret(account: str) -> str | None:
    try:
        value = _store().get_password(SERVICE, account)
    except Exception:  # noqa: BLE001 - missing backends must not crash lookup
        return None
    if not value:
        return None
    return value.strip() or None


def set_stored_secret(account: str, value: str) -> None:
    cleaned = (value or "").strip()
    if not cleaned:
        raise CobooseError("A non-empty secret is required")
    if not account.strip():
        raise CobooseError("A keychain account name is required")
    if not keychain_available():
        raise CobooseError(_unavailable_message())
    try:
        _store().set_password(SERVICE, account, cleaned)
    except CobooseError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface a safe user message
        raise CobooseError(
            f"Could not store the secret in {backend_display_name()}: {exc}. "
            f"See {TOKEN_DOC}."
        ) from exc


def delete_stored_secret(account: str) -> bool:
    if get_stored_secret(account) is None:
        return False
    try:
        _store().delete_password(SERVICE, account)
    except Exception as exc:  # noqa: BLE001 - surface a safe user message
        raise CobooseError(
            f"Could not remove the secret from {backend_display_name()}: {exc}."
        ) from exc
    return True


def get_stored_token() -> str | None:
    return get_stored_secret(ACCOUNT)


def set_stored_token(token: str) -> None:
    set_stored_secret(ACCOUNT, token)


def delete_stored_token() -> bool:
    return delete_stored_secret(ACCOUNT)


def resolve_token() -> tuple[str, str]:
    """Return (token, source). Env / .env wins so CI and existing files keep working."""
    current = env_token()
    if current:
        return current, SOURCE_ENV
    stored = get_stored_token()
    if stored:
        return stored, SOURCE_KEYCHAIN
    return "", SOURCE_MISSING


def token_source() -> str:
    return resolve_token()[1]


def keychain_available() -> bool:
    if _available_override is not None:
        return _available_override
    store = _store_override
    if store is not None:
        return not isinstance(store, UnavailableStore)
    backend = _keyring_backend()
    return backend is not None and _backend_usable(backend)


def backend_display_name(system: str | None = None) -> str:
    if _backend_name_override:
        return _backend_name_override
    system = system or platform.system()
    backend = _keyring_backend()
    if backend is not None:
        mapped = _map_backend_name(backend)
        if mapped:
            return mapped
    return default_store_name(system)


def default_store_name(system: str | None = None) -> str:
    system = system or platform.system()
    if system == "Darwin":
        return "macOS Keychain"
    if system == "Windows":
        return "Windows Credential Manager"
    return "Secret Service (GNOME Keyring / KWallet)"


def keychain_status(account: str | None = None) -> KeychainStatus:
    system = platform.system()
    store_name = default_store_name(system)
    lookup = account or ACCOUNT
    return KeychainStatus(
        available=keychain_available(),
        present=get_stored_secret(lookup) is not None,
        backend=backend_display_name(system),
        os_name=_os_label(system),
        store_name=store_name,
        account=lookup,
    )


def storage_guides() -> dict[str, Any]:
    current = platform.system()
    return {
        "preferred_cli": "uv run coboose jira login",
        "env_command": "uv run coboose env set NAME",
        "migrate_command": "uv run coboose jira login --from-env",
        "service": SERVICE,
        "account": ACCOUNT,
        "current": storage_guide(current),
        "macos": storage_guide("Darwin"),
        "windows": storage_guide("Windows"),
        "linux": storage_guide("Linux"),
    }


def storage_guide(system: str | None = None) -> dict[str, Any]:
    system = system or platform.system()
    if system == "Darwin":
        return {
            "os": "macOS",
            "store": "macOS Keychain",
            "cli_command": "uv run coboose jira login",
            "migrate_command": "uv run coboose jira login --from-env",
            "service": SERVICE,
            "account": ACCOUNT,
            "manual_steps": [
                "Open Keychain Access",
                "File > New Password Item",
                f"Keychain Item Name: {SERVICE}",
                f"Account Name: {ACCOUNT}",
                "Password: the Atlassian API token (not your account password)",
                "Click Add",
            ],
            "security_cli": (
                f"security add-generic-password -a {ACCOUNT} -s {SERVICE} -w"
            ),
        }
    if system == "Windows":
        return {
            "os": "Windows",
            "store": "Windows Credential Manager",
            "cli_command": "uv run coboose jira login",
            "migrate_command": "uv run coboose jira login --from-env",
            "service": SERVICE,
            "account": ACCOUNT,
            "manual_steps": [
                "Open Credential Manager (Control Panel > User Accounts > Credential Manager)",
                "Select Windows Credentials",
                "Click Add a generic credential",
                f"Internet or network address: {SERVICE}",
                f"User name: {ACCOUNT}",
                "Password: the Atlassian API token (not your account password)",
                "Click OK",
            ],
        }
    return {
        "os": "Linux",
        "store": "Secret Service (GNOME Keyring / KWallet)",
        "cli_command": "uv run coboose jira login",
        "migrate_command": "uv run coboose jira login --from-env",
        "service": SERVICE,
        "account": ACCOUNT,
        "manual_steps": [
            "On a desktop session with GNOME Keyring or KWallet, run `uv run coboose jira login`.",
            "Headless or CI machines can keep JIRA_API_TOKEN in .env instead.",
        ],
    }


def login_token(
    coboose_root: Path,
    *,
    from_env: bool = False,
    clear_env: bool = True,
    secret_fn: Callable[[str], str] | None = None,
    stdin_isatty: bool | None = None,
) -> dict[str, Any]:
    if from_env:
        token = env_token()
        if not token:
            raise CobooseError(
                "No JIRA_API_TOKEN in the environment or .env. "
                "Run `uv run coboose jira login` in your own terminal, "
                f"or see {TOKEN_DOC}."
            )
    else:
        if stdin_isatty is None:
            stdin_isatty = sys.stdin.isatty()
        if not stdin_isatty:
            raise CobooseError(
                "Refusing interactive login without a TTY. Run this in your own "
                "terminal, or use `coboose jira login --from-env` if the token is "
                f"already in .env. See {TOKEN_DOC}."
            )
        prompt = (
            f"Atlassian API token (stored in {backend_display_name()}; input hidden): "
        )
        token = (secret_fn or getpass)(prompt).strip()
        if not token:
            raise CobooseError("A non-empty API token is required")

    set_stored_token(token)
    cleared_env = False
    if clear_env:
        cleared_env = _clear_env_token(coboose_root)

    status = keychain_status()
    return {
        "stored": True,
        "source": SOURCE_KEYCHAIN,
        "cleared_env": cleared_env,
        "token_docs": TOKEN_DOC,
        **status.as_dict(),
        "guide": storage_guide(),
    }


def logout_token(coboose_root: Path, *, clear_env: bool = False) -> dict[str, Any]:
    removed = delete_stored_token()
    cleared_env = _clear_env_token(coboose_root) if clear_env else False
    status = keychain_status()
    return {
        "removed": removed,
        "cleared_env": cleared_env,
        "token_docs": TOKEN_DOC,
        **status.as_dict(),
        "guide": storage_guide(),
    }


def missing_token_action() -> str:
    return (
        f"Create a token ({TOKEN_DOC}) and store it with "
        "`uv run coboose jira login` (macOS Keychain or Windows Credential Manager). "
        "Do not paste the token into chat."
    )


def _clear_env_token(coboose_root: Path) -> bool:
    env_path = coboose_root / ".env"
    had_env = bool(env_token())
    for key in ("JIRA_API_TOKEN", "JIRA_TOKEN"):
        os.environ.pop(key, None)
    if env_path.exists():
        upsert_env_file(env_path, {"JIRA_API_TOKEN": ""})
        return True
    return had_env


def _store() -> TokenStore:
    if _store_override is not None:
        return _store_override
    backend = _keyring_backend()
    if backend is None or not _backend_usable(backend):
        return UnavailableStore()
    return backend


def _keyring_backend() -> TokenStore | None:
    try:
        import keyring
    except ImportError:
        return None
    try:
        return keyring.get_keyring()
    except Exception:  # noqa: BLE001 - treat a broken keyring as missing
        return None


def _backend_usable(backend: Any) -> bool:
    priority = getattr(backend, "priority", None)
    if priority is not None:
        try:
            return float(priority) > 0
        except (TypeError, ValueError):
            return True
    module = type(backend).__module__
    return "fail" not in module


def _map_backend_name(backend: Any) -> str | None:
    module = type(backend).__module__.lower()
    name = type(backend).__name__.lower()
    if "macos" in module or "macos" in name:
        return "macOS Keychain"
    if "windows" in module or "winvault" in name or "cred" in name:
        return "Windows Credential Manager"
    if "kwallet" in module or "kwallet" in name:
        return "KWallet"
    if "secretservice" in module or "secret" in name:
        return "Secret Service (GNOME Keyring / KWallet)"
    return None


def _os_label(system: str) -> str:
    if system == "Darwin":
        return "macOS"
    if system == "Windows":
        return "Windows"
    if system == "Linux":
        return "Linux"
    return system or "unknown"


def _unavailable_message() -> str:
    guide = storage_guide()
    return (
        f"{guide['store']} is not available in this session. "
        f"Run `{guide['cli_command']}` on your Mac or Windows machine, "
        f"or set JIRA_API_TOKEN in .env as a fallback. See {TOKEN_DOC}."
    )

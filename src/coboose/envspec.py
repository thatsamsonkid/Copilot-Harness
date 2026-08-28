from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Any

from coboose import CobooseError
from coboose.envfile import env_file_keys, upsert_env_file
from coboose.keychain import (
    SOURCE_ENV,
    SOURCE_KEYCHAIN,
    SOURCE_MISSING,
    backend_display_name,
    delete_stored_secret,
    get_stored_secret,
    keychain_available,
    keychain_status,
    set_stored_secret,
    storage_guides,
)
from coboose.paths import ENV_RELATIVE

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")

TOKEN_DOC = "docs/jira-api-token.md"
TOKEN_URL = "https://id.atlassian.com/manage-profile/security/api-tokens"


@dataclass(frozen=True)
class EnvVar:
    name: str
    secret: bool = False
    required: bool = True
    aliases: tuple[str, ...] = ()
    hint: str = ""
    docs: str = ""
    prompt: str = ""
    account: str = ""
    workspaces: tuple[str, ...] = ()
    description: str = ""

    @property
    def keychain_account(self) -> str:
        return self.account or self.name

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)

    def applies_to(self, workspace_id: str | None) -> bool:
        if workspace_id is None:
            return True
        if not self.workspaces:
            return True
        return workspace_id in self.workspaces


DEFAULT_ENV_VARS: tuple[EnvVar, ...] = (
    EnvVar(
        name="JIRA_BASE_URL",
        hint="https://your-domain.atlassian.net",
        docs=TOKEN_DOC,
        prompt="Atlassian site URL (https://your-domain.atlassian.net)",
    ),
    EnvVar(
        name="JIRA_EMAIL",
        aliases=("JIRA_USERNAME",),
        hint="Atlassian account email that owns the API token",
        docs=TOKEN_DOC,
        prompt="Atlassian email",
    ),
    EnvVar(
        name="JIRA_API_TOKEN",
        secret=True,
        aliases=("JIRA_TOKEN",),
        docs=TOKEN_DOC,
        account="jira-api-token",
        prompt="Atlassian API token",
    ),
)


def default_env_vars() -> list[EnvVar]:
    return list(DEFAULT_ENV_VARS)


def load_env_spec(path: Path | None) -> tuple[list[EnvVar], Path | None]:
    if path is None or not path.exists():
        return default_env_vars(), None
    from coboose.catalog import read_yaml

    raw = read_yaml(path)
    if raw is None:
        return default_env_vars(), path
    if not isinstance(raw, dict):
        raise CobooseError(f"{path} must be a mapping with a variables list")
    items = raw.get("variables")
    if items is None:
        return default_env_vars(), path
    if not isinstance(items, list):
        raise CobooseError(f"{path} variables must be a list")
    variables: list[EnvVar] = []
    seen: set[str] = set()
    for item in items:
        variable = _parse_var(item, path)
        for name in variable.names:
            if name in seen:
                raise CobooseError(f"{path} has a duplicate env name: {name}")
            seen.add(name)
        variables.append(variable)
    if not variables:
        raise CobooseError(f"{path} variables list is empty")
    return variables, path


def validate_env_spec(
    variables: Iterable[EnvVar],
    workspace_ids: set[str],
    workspace_env: dict[str, list[str]],
    *,
    source: Path | None,
) -> None:
    known = {variable.name for variable in variables}
    label = str(source) if source else str(ENV_RELATIVE)
    for variable in variables:
        unknown = [item for item in variable.workspaces if item not in workspace_ids]
        if unknown:
            raise CobooseError(
                f"{label} {variable.name} references unknown workspace id(s): "
                + ", ".join(unknown)
            )
    for workspace_id, names in workspace_env.items():
        missing = [name for name in names if name not in known]
        if missing:
            raise CobooseError(
                f"Workspace {workspace_id} env references unknown variable(s): "
                + ", ".join(missing)
                + f". Add them to {label}."
            )


def find_var(variables: Iterable[EnvVar], name: str) -> EnvVar:
    needle = name.strip()
    for variable in variables:
        if needle in variable.names:
            return variable
    known = ", ".join(variable.name for variable in variables)
    raise CobooseError(
        f"Unknown env variable {name!r}. Known names: {known or '(none)'}."
    )


def vars_for(
    variables: Iterable[EnvVar],
    workspace_id: str | None = None,
    extra_names: Iterable[str] | None = None,
) -> list[EnvVar]:
    selected: list[EnvVar] = []
    extra = set(extra_names or [])
    for variable in variables:
        if variable.applies_to(workspace_id) or variable.name in extra:
            selected.append(variable)
    return selected


def resolve_var(variable: EnvVar) -> tuple[str, str]:
    for key in variable.names:
        value = (os.environ.get(key) or "").strip()
        if value:
            return value, SOURCE_ENV
    if variable.secret:
        stored = get_stored_secret(variable.keychain_account)
        if stored:
            return stored, SOURCE_KEYCHAIN
        if variable.keychain_account != variable.name:
            stored = get_stored_secret(variable.name)
            if stored:
                return stored, SOURCE_KEYCHAIN
    return "", SOURCE_MISSING


def var_is_present(variable: EnvVar, file_keys: dict[str, bool] | None = None) -> bool:
    value, _source = resolve_var(variable)
    if value:
        return True
    keys = file_keys or {}
    return any(keys.get(name) for name in variable.names)


def var_source(variable: EnvVar, file_keys: dict[str, bool] | None = None) -> str:
    _value, source = resolve_var(variable)
    if source != SOURCE_MISSING:
        return source
    keys = file_keys or {}
    if any(keys.get(name) for name in variable.names):
        return SOURCE_ENV
    return SOURCE_MISSING


def var_status(
    variable: EnvVar, file_keys: dict[str, bool] | None = None
) -> dict[str, Any]:
    source = var_source(variable, file_keys)
    present = source != SOURCE_MISSING
    payload: dict[str, Any] = {
        "name": variable.name,
        "secret": variable.secret,
        "required": variable.required,
        "present": present,
        "source": source,
        "workspaces": list(variable.workspaces),
        "aliases": list(variable.aliases),
        "hint": variable.hint or None,
        "docs": variable.docs or None,
        "description": variable.description or None,
        "account": variable.keychain_account if variable.secret else None,
        "store": "keychain" if variable.secret else "env",
    }
    if not present:
        payload["action"] = missing_action(variable)
    elif variable.secret and source == SOURCE_ENV:
        payload["action"] = (
            f"Token is in .env. Prefer `uv run coboose env set {variable.name} "
            "--from-env` to move it into macOS Keychain or Windows Credential Manager."
        )
        if variable.name == "JIRA_API_TOKEN":
            payload["action"] = (
                "Token is in .env. Prefer `uv run coboose jira login --from-env` "
                "to move it into macOS Keychain or Windows Credential Manager."
            )
    return payload


def missing_action(variable: EnvVar) -> str:
    docs = f" ({variable.docs})" if variable.docs else ""
    if variable.secret:
        command = (
            "uv run coboose jira login"
            if variable.name == "JIRA_API_TOKEN"
            else f"uv run coboose env set {variable.name}"
        )
        return (
            f"Create a value{docs} and store it with `{command}` "
            "(macOS Keychain or Windows Credential Manager). "
            "Do not paste the secret into chat."
        )
    hint = f" to {variable.hint}" if variable.hint else ""
    return (
        f"Set {variable.name} in .env{hint}. "
        "Do not paste secrets into Copilot chat."
    )


def list_env(
    variables: Iterable[EnvVar],
    coboose_root: Path,
    *,
    workspace_id: str | None = None,
    extra_names: Iterable[str] | None = None,
    source: Path | None = None,
) -> dict[str, Any]:
    file_keys = env_file_keys(coboose_root / ".env")
    selected = vars_for(variables, workspace_id, extra_names)
    rows = [var_status(variable, file_keys) for variable in selected]
    missing = [
        row["name"]
        for row, variable in zip(rows, selected)
        if variable.required and not row["present"]
    ]
    return {
        "source": str(source) if source else "defaults",
        "workspace": workspace_id,
        "keychain": keychain_status().as_dict(),
        "keychain_guide": storage_guides(),
        "variables": rows,
        "missing": missing,
    }


def set_env_value(
    variable: EnvVar,
    coboose_root: Path,
    *,
    from_env: bool = False,
    clear_env: bool = True,
    prompt_fn: Callable[[str], str] | None = None,
    secret_fn: Callable[[str], str] | None = None,
    stdin_isatty: bool | None = None,
) -> dict[str, Any]:
    env_path = coboose_root / ".env"
    if from_env:
        value, source = resolve_var(variable)
        if source != SOURCE_ENV or not value:
            raise CobooseError(
                f"No {variable.name} in the environment or .env. "
                f"Run `uv run coboose env set {variable.name}` in your own terminal"
                + (f", or see {variable.docs}." if variable.docs else ".")
            )
    else:
        if stdin_isatty is None:
            stdin_isatty = sys.stdin.isatty()
        if not stdin_isatty:
            raise CobooseError(
                "Refusing interactive env set without a TTY. Run this in your own "
                f"terminal, or use `coboose env set {variable.name} --from-env` "
                "if the value is already in .env."
            )
        value = _prompt_value(variable, prompt_fn=prompt_fn, secret_fn=secret_fn)

    stored_source = SOURCE_ENV
    cleared_env = False
    wrote: list[str] = []
    if variable.secret and keychain_available():
        set_stored_secret(variable.keychain_account, value)
        stored_source = SOURCE_KEYCHAIN
        if clear_env:
            cleared_env = _clear_env_names(env_path, variable.names)
    elif variable.secret and not keychain_available():
        wrote = upsert_env_file(env_path, {variable.name: value})
        os.environ[variable.name] = value
        stored_source = SOURCE_ENV
    else:
        wrote = upsert_env_file(env_path, {variable.name: value})
        os.environ[variable.name] = value

    status = var_status(variable, env_file_keys(env_path))
    payload = {
        "stored": True,
        "source": stored_source,
        "cleared_env": cleared_env,
        "wrote_keys": wrote,
        **status,
        "keychain": keychain_status(variable.keychain_account).as_dict()
        if variable.secret
        else keychain_status().as_dict(),
        "keychain_guide": storage_guides(),
        "guide": storage_guides()["current"],
    }
    return payload


def unset_env_value(
    variable: EnvVar,
    coboose_root: Path,
    *,
    clear_env: bool = False,
) -> dict[str, Any]:
    removed = False
    if variable.secret:
        removed = delete_stored_secret(variable.keychain_account)
        if variable.keychain_account != variable.name:
            removed = delete_stored_secret(variable.name) or removed
    cleared_env = False
    if clear_env or not variable.secret:
        cleared_env = _clear_env_names(coboose_root / ".env", variable.names)
    return {
        "removed": removed,
        "cleared_env": cleared_env,
        **var_status(variable, env_file_keys(coboose_root / ".env")),
        "keychain_guide": storage_guides(),
    }


def _prompt_value(
    variable: EnvVar,
    *,
    prompt_fn: Callable[[str], str] | None,
    secret_fn: Callable[[str], str] | None,
) -> str:
    label = variable.prompt or variable.name
    if variable.secret:
        store_name = backend_display_name()
        if keychain_available():
            message = f"{label} (stored in {store_name}; input hidden): "
        else:
            message = (
                f"{label} (OS keychain unavailable; will save to .env; input hidden): "
            )
        value = (secret_fn or getpass)(message).strip()
    else:
        value = (prompt_fn or input)(f"{label}: ").strip()
    if not value:
        raise CobooseError(f"A non-empty value is required for {variable.name}")
    return value


def _clear_env_names(env_path: Path, names: Iterable[str]) -> bool:
    name_list = list(names)
    had_env = any((os.environ.get(name) or "").strip() for name in name_list)
    for name in name_list:
        os.environ.pop(name, None)
    if env_path.exists():
        upsert_env_file(env_path, {name_list[0]: ""})
        return True
    return had_env


def _parse_var(item: Any, source: Path) -> EnvVar:
    if isinstance(item, str):
        name = item.strip()
        _require_name(name, source)
        return EnvVar(name=name)
    if not isinstance(item, dict):
        raise CobooseError(f"{source} each variable must be a mapping or a name")
    name = str(item.get("name") or "").strip()
    _require_name(name, source)
    aliases = tuple(
        _require_name(str(alias).strip(), source)
        for alias in (item.get("aliases") or [])
    )
    workspaces = tuple(str(value).strip() for value in (item.get("workspaces") or []) if str(value).strip())
    account = str(item.get("account") or "").strip()
    return EnvVar(
        name=name,
        secret=bool(item.get("secret", False)),
        required=bool(item.get("required", True)),
        aliases=aliases,
        hint=str(item.get("hint") or ""),
        docs=str(item.get("docs") or ""),
        prompt=str(item.get("prompt") or ""),
        account=account,
        workspaces=workspaces,
        description=str(item.get("description") or ""),
    )


def _require_name(name: str, source: Path) -> str:
    if not name or not _ENV_NAME.match(name):
        raise CobooseError(
            f"{source} env name {name!r} must look like JIRA_API_TOKEN"
        )
    return name

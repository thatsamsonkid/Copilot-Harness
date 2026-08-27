from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from getpass import getpass
from pathlib import Path
from typing import Any

from harness import HarnessError
from harness.catalog import Catalog
from harness.envfile import env_file_keys, upsert_env_file
from harness.jira_client import JiraClient, jira_settings_from_env
from harness.keychain import (
    SOURCE_ENV,
    SOURCE_KEYCHAIN,
    SOURCE_MISSING,
    backend_display_name,
    keychain_available,
    keychain_status,
    missing_token_action,
    set_stored_token,
    storage_guides,
    token_source,
)
from harness.uv_check import UV_DOC, detect_uv, uv_missing_action

TOKEN_DOC = "docs/jira-api-token.md"
TOKEN_URL = "https://id.atlassian.com/manage-profile/security/api-tokens"

JIRA_KEYS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")


def run_init(
    catalog: Catalog,
    harness_root: Path,
    *,
    interactive: bool = False,
    ping_jira: bool = False,
    prompt_fn: Callable[[str], str] | None = None,
    secret_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    env_path = harness_root / ".env"
    created_env = False
    if not env_path.exists() and (harness_root / ".env.example").exists():
        shutil.copyfile(harness_root / ".env.example", env_path)
        created_env = True

    written_keys: list[str] = []
    stored_token = SOURCE_MISSING
    if interactive:
        updates, stored_token = _fill_env_interactive(
            env_path,
            prompt_fn=prompt_fn or input,
            secret_fn=secret_fn or (lambda message: getpass(message)),
        )
        written_keys = list(updates)
        for key, value in updates.items():
            os.environ[key] = value
    elif token_source() != SOURCE_MISSING:
        stored_token = token_source()

    uv = detect_uv()
    steps = onboarding_steps(catalog, harness_root, uv=uv)
    jira = None
    if ping_jira and _jira_env_present():
        try:
            base_url, email, token = jira_settings_from_env()
            jira = JiraClient(base_url, email, token).myself()
            _set_step(steps, "jira_auth", True, "Jira accepted the credentials")
        except Exception as exc:  # noqa: BLE001 - first-run should stay readable
            _set_step(steps, "jira_auth", False, f"Jira auth failed: {exc}")
    elif ping_jira:
        _set_step(steps, "jira_auth", False, "Cannot ping Jira until credentials are complete")

    ready = all(step["ok"] or step.get("optional") for step in steps)
    return {
        "ready": ready,
        "created_env": created_env,
        "env_file": str(env_path),
        "wrote_keys": written_keys,
        "token_store": stored_token if stored_token != SOURCE_MISSING else token_source(),
        "token_docs": TOKEN_DOC,
        "token_url": TOKEN_URL,
        "uv_docs": UV_DOC,
        "uv": uv,
        "interactive": interactive,
        "jira": jira,
        "keychain": keychain_status().as_dict(),
        "keychain_guide": storage_guides(),
        "steps": steps,
        "next_commands": _next_commands(steps, uv=uv),
    }


def onboarding_steps(
    catalog: Catalog,
    harness_root: Path,
    *,
    uv: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    uv = uv or detect_uv()
    env_path = harness_root / ".env"
    file_keys = env_file_keys(env_path)
    steps: list[dict[str, Any]] = [
        _step(
            "uv",
            bool(uv.get("present")),
            f"uv is on PATH ({uv.get('path')})" if uv.get("present") else "uv is not on PATH",
            action=None if uv.get("present") else uv_missing_action(uv),
        ),
        _step(
            "env_file",
            env_path.exists(),
            f"{env_path.name} exists"
            if env_path.exists()
            else "Copy .env.example to .env",
            action="Copy .env.example to .env, then edit it locally. Never paste the token into chat.",
        )
    ]
    for key, hint in (
        ("JIRA_BASE_URL", "https://your-domain.atlassian.net"),
        ("JIRA_EMAIL", "the Atlassian account email that owns the API token"),
        ("JIRA_API_TOKEN", f"an Atlassian API token from {TOKEN_URL}"),
    ):
        present = _env_key_present(key, file_keys)
        action = (
            None
            if present
            else f"Set {key} in .env to {hint}. Do not paste secrets into Copilot chat."
        )
        if key == "JIRA_API_TOKEN" and not present:
            action = missing_token_action()
        elif key == "JIRA_API_TOKEN" and token_source() == SOURCE_ENV:
            action = (
                "Token is in .env. Prefer `uv run harness jira login --from-env` "
                "to move it into macOS Keychain or Windows Credential Manager."
            )
        steps.append(
            _step(
                key.lower(),
                present,
                _token_detail(present) if key == "JIRA_API_TOKEN"
                else (f"{key} is set" if present else f"{key} is missing"),
                action=action,
            )
        )

    placeholders = [repo.name for repo in catalog.repos if repo.is_placeholder]
    steps.append(
        _step(
            "repositories",
            not placeholders,
            "repository URLs look real"
            if not placeholders
            else "placeholder remotes remain: " + ", ".join(placeholders),
            action=None
            if not placeholders
            else "Replace YOUR_ORG in repositories.yml, then run harness clone",
        )
    )

    cloned = [
        repo.name
        for repo in catalog.enabled_repos()
        if catalog.repo_path(harness_root, repo).exists()
    ]
    missing = [
        repo.name
        for repo in catalog.enabled_repos()
        if not repo.is_placeholder and not catalog.repo_path(harness_root, repo).exists()
    ]
    steps.append(
        _step(
            "clones",
            not missing,
            f"cloned: {', '.join(cloned) or 'none'}",
            action=None if not missing else "Run ./scripts/clone-repos.sh (or harness clone)",
            optional=True,
        )
    )
    steps.append(
        _step(
            "token_docs",
            True,
            f"Token walkthrough: {TOKEN_DOC}",
            optional=True,
        )
    )
    return steps


def _fill_env_interactive(
    env_path: Path,
    *,
    prompt_fn: Callable[[str], str],
    secret_fn: Callable[[str], str],
) -> tuple[dict[str, str], str]:
    if prompt_fn is input and not sys.stdin.isatty():
        raise HarnessError(
            "Refusing interactive init without a TTY. Edit .env locally "
            f"or see {TOKEN_DOC}."
        )
    file_keys = env_file_keys(env_path)
    updates: dict[str, str] = {}
    prompts = {
        "JIRA_BASE_URL": "Atlassian site URL (https://your-domain.atlassian.net): ",
        "JIRA_EMAIL": "Atlassian email: ",
    }
    for key, message in prompts.items():
        if _env_key_present(key, file_keys):
            continue
        value = prompt_fn(message).strip()
        if value:
            updates[key] = value
    stored_token = token_source()
    if not _env_key_present("JIRA_API_TOKEN", file_keys):
        store_name = backend_display_name()
        if keychain_available():
            prompt = f"Atlassian API token (stored in {store_name}; input hidden): "
        else:
            prompt = (
                "Atlassian API token (OS keychain unavailable; "
                "will save to .env; input hidden): "
            )
        token = secret_fn(prompt).strip()
        if token:
            if keychain_available():
                set_stored_token(token)
                stored_token = SOURCE_KEYCHAIN
            else:
                updates["JIRA_API_TOKEN"] = token
                stored_token = SOURCE_ENV
    upsert_env_file(env_path, updates)
    return updates, stored_token


def _env_key_present(key: str, file_keys: dict[str, bool]) -> bool:
    if key == "JIRA_EMAIL":
        return bool(
            os.environ.get("JIRA_EMAIL")
            or os.environ.get("JIRA_USERNAME")
            or file_keys.get("JIRA_EMAIL")
            or file_keys.get("JIRA_USERNAME")
        )
    if key == "JIRA_API_TOKEN":
        return token_source() != SOURCE_MISSING or bool(
            file_keys.get("JIRA_API_TOKEN") or file_keys.get("JIRA_TOKEN")
        )
    return bool(os.environ.get(key) or file_keys.get(key))


def _token_detail(present: bool) -> str:
    source = token_source()
    if source == SOURCE_KEYCHAIN:
        return f"JIRA_API_TOKEN is in {backend_display_name()}"
    if source == SOURCE_ENV:
        return "JIRA_API_TOKEN is set in the environment or .env"
    if present:
        return "JIRA_API_TOKEN is set"
    return "JIRA_API_TOKEN is missing"


def _jira_env_present() -> bool:
    return all(
        _env_key_present(key, {})
        for key in JIRA_KEYS
    )


def _step(
    id: str,
    ok: bool,
    detail: str,
    *,
    action: str | None = None,
    optional: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": id,
        "ok": ok,
        "detail": detail,
        "optional": optional,
    }
    if action:
        payload["action"] = action
    return payload


def _set_step(steps: list[dict[str, Any]], id: str, ok: bool, detail: str) -> None:
    for step in steps:
        if step["id"] == id:
            step["ok"] = ok
            step["detail"] = detail
            return
    steps.append(_step(id, ok, detail))


def _next_commands(
    steps: list[dict[str, Any]], *, uv: dict[str, Any] | None = None
) -> list[str]:
    ids = {step["id"] for step in steps if not step["ok"] and not step.get("optional")}
    commands: list[str] = []
    if "uv" in ids:
        info = uv or detect_uv()
        commands.append(uv_missing_action(info))
        commands.append(f"Then open a new terminal and run {info['setup_script']}")
    if ids.intersection({"env_file", "jira_base_url", "jira_email"}):
        commands.append("Edit .env locally. Token docs: docs/jira-api-token.md")
        commands.append("uv run harness init --interactive")
    if "jira_api_token" in ids:
        commands.append("uv run harness jira login")
        if "uv run harness init --interactive" not in commands:
            commands.append("uv run harness init --interactive")
        commands.append("uv run harness doctor --ping-jira")
    elif ids.intersection({"env_file", "jira_base_url", "jira_email"}):
        commands.append("uv run harness doctor --ping-jira")
    if "repositories" in ids:
        commands.append("Edit repositories.yml and replace YOUR_ORG")
    missing_clones = next((step for step in steps if step["id"] == "clones" and not step["ok"]), None)
    if missing_clones:
        commands.append("./scripts/clone-repos.sh")
    commands.append("uv run harness workspace generate")
    return commands

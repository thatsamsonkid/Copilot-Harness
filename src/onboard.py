from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from getpass import getpass
from pathlib import Path
from typing import Any

from goat import GoatError
from goat.catalog import Catalog
from goat.envfile import env_file_keys
from goat.install import cli_path_status
from goat.envspec import (
    list_env,
    set_env_value,
    var_is_present,
    var_source,
    var_status,
)
from goat.jira_client import JiraClient, jira_settings_from_env
from goat.keychain import (
    SOURCE_ENV,
    SOURCE_KEYCHAIN,
    SOURCE_MISSING,
    backend_display_name,
    keychain_status,
    storage_guides,
    token_source,
)
from goat.skills import sync_root_skills
from goat.uv_check import UV_DOC, detect_uv, uv_missing_action
from goat.workspace import catalog_starters, generate_workspaces

TOKEN_DOC = "docs/jira-api-token.md"
TOKEN_URL = "https://id.atlassian.com/manage-profile/security/api-tokens"

JIRA_KEYS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")


def run_init(
    catalog: Catalog,
    goat_root: Path,
    *,
    interactive: bool = False,
    ping_jira: bool = False,
    prompt_fn: Callable[[str], str] | None = None,
    secret_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    env_path = goat_root / ".env"
    created_env = False
    if not env_path.exists() and (goat_root / ".env.example").exists():
        shutil.copyfile(goat_root / ".env.example", env_path)
        created_env = True

    written_keys: list[str] = []
    stored_token = SOURCE_MISSING
    if interactive:
        updates, stored_token = _fill_env_interactive(
            env_path,
            catalog.env_vars,
            prompt_fn=prompt_fn or input,
            secret_fn=secret_fn or (lambda message: getpass(message)),
        )
        written_keys = list(updates)
        for key, value in updates.items():
            os.environ[key] = value
    elif token_source() != SOURCE_MISSING:
        stored_token = token_source()

    uv = detect_uv()
    steps = onboarding_steps(catalog, goat_root, uv=uv)
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

    skills = sync_root_skills(catalog, goat_root, all_repos=True)
    copied = len(skills.get("copied") or [])
    updated = len(skills.get("updated") or [])
    available = len(skills.get("available") or [])
    native = len(skills.get("native") or [])
    if skills.get("error"):
        steps.append(
            _step(
                "skills",
                False,
                f"Could not lift agent skills: {skills['error']}",
                action="uv run goat skills list",
                optional=True,
            )
        )
    else:
        steps.append(
            _step(
                "skills",
                True,
                (
                    f"agent skills ready in .github/skills "
                    f"({native} goat, {copied} lifted, {updated} updated, "
                    f"{available} discovered)"
                ),
                action=None if available else "uv run goat skills list",
                optional=True,
            )
        )

    generate_workspaces(catalog, goat_root)
    starters = catalog_starters(catalog, goat_root)
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
        "env": list_env(
            catalog.env_vars,
            goat_root,
            source=catalog.env_source,
        ),
        "steps": steps,
        "skills": skills,
        "workspaces": starters,
        "workspace_hint": (
            "Open a catalog starter with `goat workspace open <id>`, "
            "or create your own with `goat workspace create` / `/new-workspace`."
        ),
        "next_commands": _next_commands(steps, uv=uv, variables=catalog.env_vars),
    }


def onboarding_steps(
    catalog: Catalog,
    goat_root: Path,
    *,
    uv: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    uv = uv or detect_uv()
    env_path = goat_root / ".env"
    file_keys = env_file_keys(env_path)
    steps: list[dict[str, Any]] = [
        _step(
            "uv",
            bool(uv.get("present")),
            f"uv is on PATH ({uv.get('path')})" if uv.get("present") else "uv is not on PATH",
            action=None if uv.get("present") else uv_missing_action(uv),
        ),
    ]
    path_status = cli_path_status(goat_root)
    steps.append(
        _step(
            "cli_path",
            bool(path_status["on_path"]),
            path_status["detail"],
            action=None if path_status["on_path"] else "uv run goat install",
            optional=True,
        )
    )
    steps.append(
        _step(
            "env_file",
            env_path.exists(),
            f"{env_path.name} exists"
            if env_path.exists()
            else "Copy .env.example to .env",
            action="Copy .env.example to .env, then edit it locally. Never paste the token into chat.",
        )
    )
    for variable in catalog.env_vars:
        present = var_is_present(variable, file_keys)
        status = var_status(variable, file_keys)
        steps.append(
            _step(
                variable.name.lower(),
                present,
                _var_detail(variable, file_keys, present),
                action=status.get("action"),
                optional=not variable.required,
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
            else "Replace YOUR_ORG in repositories.yml, then run goat clone",
        )
    )

    cloned = [
        repo.name
        for repo in catalog.enabled_repos()
        if catalog.repo_path(goat_root, repo).exists()
    ]
    missing = [
        repo.name
        for repo in catalog.enabled_repos()
        if not repo.is_placeholder and not catalog.repo_path(goat_root, repo).exists()
    ]
    steps.append(
        _step(
            "clones",
            not missing,
            f"cloned: {', '.join(cloned) or 'none'}",
            action=None
            if not missing
            else (
                "If clones already exist elsewhere: goat workspace map --write --generate. "
                "Otherwise run goat clone (or ./scripts/clone-repos.sh)"
            ),
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
    variables: list[Any],
    *,
    prompt_fn: Callable[[str], str],
    secret_fn: Callable[[str], str],
) -> tuple[dict[str, str], str]:
    if prompt_fn is input and not sys.stdin.isatty():
        raise GoatError(
            "Refusing interactive init without a TTY. Edit .env locally "
            f"or see {TOKEN_DOC}."
        )
    file_keys = env_file_keys(env_path)
    updates: dict[str, str] = {}
    stored_token = token_source()
    for variable in variables:
        if not variable.required or var_is_present(variable, file_keys):
            if variable.name == "JIRA_API_TOKEN":
                stored_token = var_source(variable, file_keys)
            continue
        payload = set_env_value(
            variable,
            env_path.parent,
            prompt_fn=prompt_fn,
            secret_fn=secret_fn,
            stdin_isatty=True,
        )
        for key in payload.get("wrote_keys") or []:
            value = os.environ.get(key)
            if value:
                updates[key] = value
        file_keys = env_file_keys(env_path)
        if variable.name == "JIRA_API_TOKEN":
            stored_token = str(payload.get("source") or SOURCE_MISSING)
    return updates, stored_token


def _var_detail(variable: Any, file_keys: dict[str, bool], present: bool) -> str:
    source = var_source(variable, file_keys)
    if source == SOURCE_KEYCHAIN:
        return f"{variable.name} is in {backend_display_name()}"
    if source == SOURCE_ENV:
        return f"{variable.name} is set in the environment or .env"
    if present:
        return f"{variable.name} is set"
    return f"{variable.name} is missing"


def _jira_env_present() -> bool:
    from goat.envspec import default_env_vars

    return all(var_is_present(variable, {}) for variable in default_env_vars())


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
    steps: list[dict[str, Any]],
    *,
    uv: dict[str, Any] | None = None,
    variables: list[Any] | None = None,
) -> list[str]:
    ids = {step["id"] for step in steps if not step["ok"] and not step.get("optional")}
    commands: list[str] = []
    if "uv" in ids:
        info = uv or detect_uv()
        commands.append(uv_missing_action(info))
        commands.append(f"Then open a new terminal and run {info['setup_script']}")
    by_id = {variable.name.lower(): variable for variable in (variables or [])}
    missing_vars = [by_id[step_id] for step_id in ids if step_id in by_id]
    missing_plain = [variable for variable in missing_vars if not variable.secret]
    missing_secrets = [variable for variable in missing_vars if variable.secret]
    if "env_file" in ids or missing_plain:
        commands.append("Edit .env locally. See catalog/env.yaml")
        commands.append("uv run goat init --interactive")
    for variable in missing_secrets:
        if variable.name == "JIRA_API_TOKEN":
            commands.append("uv run goat jira login")
        elif variable.name == "FIGMA_ACCESS_TOKEN":
            commands.append("uv run goat figma login")
        else:
            commands.append(f"uv run goat env set {variable.name}")
        if "uv run goat init --interactive" not in commands:
            commands.append("uv run goat init --interactive")
    if missing_secrets or missing_plain or "env_file" in ids:
        commands.append("uv run goat env list")
        commands.append("uv run goat doctor --ping-jira")
    if "repositories" in ids:
        commands.append("Edit repositories.yml and replace YOUR_ORG")
    missing_clones = next((step for step in steps if step["id"] == "clones" and not step["ok"]), None)
    if missing_clones:
        commands.append("./scripts/clone-repos.sh")
    commands.append("uv run goat workspace generate")
    commands.append("uv run goat workspace list")
    commands.append("uv run goat workspace create")
    commands.append("uv run goat skills lift")
    cli_path = next(
        (step for step in steps if step["id"] == "cli_path" and not step["ok"]),
        None,
    )
    if cli_path:
        commands.append("uv run goat install")
    return commands

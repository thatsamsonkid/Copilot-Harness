from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Mapping

from coboose import CobooseError
from coboose.catalog import Catalog
from coboose.context import inspect_repo
from coboose.envfile import env_file_age
from coboose.envspec import list_env
from coboose.invoke import invoke_spec
from coboose.jira_client import JiraClient, jira_settings_from_env
from coboose.keychain import (
    SOURCE_ENV,
    SOURCE_KEYCHAIN,
    backend_display_name,
    keychain_status,
    resolve_token,
    storage_guides,
)
from coboose.onboard import onboarding_steps
from coboose.uv_check import detect_uv, uv_missing_action
from coboose.workspace import generate_workspaces
from coboose.workspace_detect import resolve_workspace_scope, scoped_repos


def run_doctor(
    catalog: Catalog,
    coboose_root: Path,
    *,
    ping_jira: bool = False,
    workspace_id: str | None = None,
    all_repos: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    uv = detect_uv()
    checks.append(
        _check(
            "uv",
            bool(uv["present"]),
            f"uv is on PATH ({uv['path']})" if uv["present"] else uv_missing_action(uv),
        )
    )
    checks.append(
        _check(
            "git",
            bool(shutil.which("git")),
            "git is on PATH" if shutil.which("git") else "git is not on PATH",
        )
    )
    checks.append(
        _check(
            "code",
            bool(shutil.which("code")),
            "code CLI is on PATH"
            if shutil.which("code")
            else "code CLI is not on PATH (open workspaces manually)",
            ok_when_false=True,
        )
    )
    graphify_cli = shutil.which("graphify")
    checks.append(
        _check(
            "graphify_cli",
            bool(graphify_cli),
            f"graphify is on PATH ({graphify_cli})"
            if graphify_cli
            else "graphify is not on PATH; still use committed graphify-out/ artifacts",
            ok_when_false=True,
        )
    )

    placeholders = [repo.id for repo in catalog.repos if repo.is_placeholder]
    checks.append(
        _check(
            "catalog_urls",
            not placeholders,
            "repo URLs look real"
            if not placeholders
            else "placeholder URLs remain: " + ", ".join(placeholders),
        )
    )

    templates_file = catalog.templates_source
    template_placeholders = [
        template.name for template in catalog.templates if template.is_placeholder
    ]
    if templates_file and templates_file.exists():
        checks.append(
            _check(
                "templates",
                bool(catalog.templates),
                f"{len(catalog.templates)} template(s) listed"
                if catalog.templates
                else "templates.yml has no entries",
                ok_when_false=True,
            )
        )
        checks.append(
            _check(
                "template_urls",
                not template_placeholders,
                "template URLs look real"
                if not template_placeholders
                else "placeholder template URLs remain: "
                + ", ".join(template_placeholders),
                ok_when_false=True,
            )
        )
    else:
        checks.append(
            _check(
                "templates",
                False,
                "templates.yml is missing (optional until you bootstrap a project)",
                ok_when_false=True,
            )
        )

    try:
        sibling_root = catalog.require_safe_sibling_root(coboose_root)
        checks.append(
            _check(
                "sibling_root",
                sibling_root != coboose_root.resolve(),
                f"siblings clone to {sibling_root}",
            )
        )
    except CobooseError as exc:
        sibling_root = catalog.sibling_root(coboose_root)
        checks.append(_check("sibling_root", False, str(exc)))

    scope = resolve_workspace_scope(
        catalog,
        coboose_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    env_payload = list_env(
        catalog.env_vars,
        coboose_root,
        workspace_id=scope.id,
        extra_names=(catalog.workspace(scope.id).env if scope.id else None),
        source=catalog.env_source,
    )

    repos = []
    for repo in scoped_repos(catalog, scope):
        path = catalog.repo_path(coboose_root, repo)
        cloned = path.exists()
        repos.append(
            {
                "id": repo.id,
                "path": str(path),
                "relpath": repo.path,
                "group": repo.group,
                "cloned": cloned,
                "placeholder": repo.is_placeholder,
            }
        )
        checks.append(
            _check(
                f"repo:{repo.id}",
                cloned,
                f"{path} is present" if cloned else f"{path} is not cloned",
                ok_when_false=True,
            )
        )
        if cloned:
            snapshot = inspect_repo(catalog, coboose_root, repo)
            graphify = snapshot["graphify"]
            checks.append(
                _check(
                    f"graphify:{repo.id}",
                    bool(graphify.get("present")) or not graphify.get("enabled"),
                    graphify.get("detail") or "graphify status unknown",
                    ok_when_false=True,
                )
            )
            instruction_count = len(snapshot["instructions"])
            checks.append(
                _check(
                    f"instructions:{repo.id}",
                    instruction_count > 0,
                    (
                        f"{instruction_count} instruction file(s)"
                        if instruction_count
                        else "no Copilot/AGENTS instruction files found"
                    ),
                    ok_when_false=True,
                )
            )

    generated = generate_workspaces(catalog, coboose_root)
    checks.append(
        _check(
            "workspaces",
            bool(generated),
            f"generated {len(generated)} workspace file(s)",
        )
    )

    base_url = os.environ.get("JIRA_BASE_URL")
    email = os.environ.get("JIRA_EMAIL") or os.environ.get("JIRA_USERNAME")
    token, source = resolve_token()
    jira_ok = bool(base_url and email and token)
    jira: dict[str, Any] | None = None
    status = keychain_status()
    if source == SOURCE_KEYCHAIN:
        checks.append(
            _check(
                "jira_token_store",
                True,
                f"Jira token is in {backend_display_name()}",
            )
        )
    elif source == SOURCE_ENV:
        checks.append(
            _check(
                "jira_token_store",
                False,
                "Jira token is in .env; prefer `uv run coboose jira login --from-env`",
                ok_when_false=True,
            )
        )
    else:
        checks.append(
            _check(
                "jira_token_store",
                False,
                "Jira token is not in the OS keychain or .env",
                ok_when_false=True,
            )
        )
    if not jira_ok:
        checks.append(
            _check(
                "jira_env",
                False,
                "Jira site URL, email, or token is missing",
                ok_when_false=True,
            )
        )
    elif ping_jira:
        try:
            base_url, email, token = jira_settings_from_env()
            jira = JiraClient(base_url, email, token).myself()
            checks.append(_check("jira_auth", True, f"authenticated as {jira.get('display_name')}"))
        except Exception as exc:  # noqa: BLE001 - doctor should not crash
            checks.append(_check("jira_auth", False, str(exc)))
    else:
        checks.append(_check("jira_env", True, f"Jira credentials are present ({source})"))

    for row in env_payload["variables"]:
        if row["name"] in {"JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"}:
            continue
        checks.append(
            _check(
                f"env:{row['name']}",
                bool(row["present"]),
                (
                    f"{row['name']} is in {row['source']}"
                    if row["present"]
                    else f"{row['name']} is missing"
                ),
                ok_when_false=True,
            )
        )

    env_age = env_file_age(coboose_root / ".env")
    checks.append(
        _check(
            "env_age",
            not env_age["stale"],
            env_age["detail"],
            ok_when_false=True,
        )
    )

    ok = all(item["ok"] or item.get("advisory") for item in checks)
    steps = onboarding_steps(catalog, coboose_root, uv=uv)
    return {
        "ok": ok,
        "coboose_root": str(coboose_root),
        "sibling_root": str(sibling_root),
        "workspace": scope.id,
        "workspace_scope": scope.as_payload(),
        "repos": repos,
        "templates": [
            {
                "name": template.name,
                "url": template.url,
                "tags": template.tags,
                "placeholder": template.is_placeholder,
            }
            for template in catalog.templates
        ],
        "workspaces": generated,
        "jira": jira,
        "jira_token_source": source,
        "keychain": status.as_dict(),
        "keychain_guide": storage_guides(),
        "env": env_payload,
        "uv": uv,
        "graphify_cli": graphify_cli,
        "env_age": env_age,
        "invoke": invoke_spec(coboose_root),
        "checks": checks,
        "onboarding": steps,
    }


def _check(name: str, ok: bool, detail: str, ok_when_false: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "detail": detail,
        "advisory": ok_when_false and not ok,
    }

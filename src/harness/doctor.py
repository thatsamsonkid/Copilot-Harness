from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from harness import HarnessError
from harness.catalog import Catalog
from harness.context import inspect_repo
from harness.jira_client import JiraClient, jira_settings_from_env
from harness.onboard import onboarding_steps
from harness.uv_check import detect_uv, uv_missing_action
from harness.workspace import generate_workspaces


def run_doctor(
    catalog: Catalog,
    harness_root: Path,
    *,
    ping_jira: bool = False,
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
        sibling_root = catalog.require_safe_sibling_root(harness_root)
        checks.append(
            _check(
                "sibling_root",
                sibling_root != harness_root.resolve(),
                f"siblings clone to {sibling_root}",
            )
        )
    except HarnessError as exc:
        sibling_root = catalog.sibling_root(harness_root)
        checks.append(_check("sibling_root", False, str(exc)))

    repos = []
    for repo in catalog.enabled_repos():
        path = catalog.repo_path(harness_root, repo)
        cloned = path.exists()
        record: dict[str, Any] = {
            "id": repo.id,
            "path": str(path),
            "relpath": repo.path,
            "group": repo.group,
            "cloned": cloned,
            "placeholder": repo.is_placeholder,
        }
        repos.append(record)
        checks.append(
            _check(
                f"repo:{repo.id}",
                cloned,
                f"{path} is present" if cloned else f"{path} is not cloned",
                ok_when_false=True,
            )
        )
        if cloned:
            snapshot = inspect_repo(catalog, harness_root, repo)
            graphify = snapshot["graphify"]
            readiness = snapshot["readiness"]
            tooling = snapshot["tooling"]
            record["suggested_verify"] = tooling.get("suggested_verify") or []
            record["readiness"] = readiness
            checks.append(
                _check(
                    f"graphify:{repo.id}",
                    bool(graphify.get("present")) or not graphify.get("enabled"),
                    graphify.get("detail") or "graphify status unknown",
                    ok_when_false=True,
                )
            )
            instruction_gap = _gap(readiness, "instructions")
            primary = [
                item["path"]
                for item in snapshot["instructions"]
                if item.get("kind") in {"copilot", "agents"}
            ]
            checks.append(
                _check(
                    f"instructions:{repo.id}",
                    instruction_gap is None,
                    (
                        f"{len(primary)} Copilot/AGENTS instruction file(s)"
                        if primary
                        else (instruction_gap or {}).get("detail")
                        or "no AGENTS.md or .github/copilot-instructions.md"
                    ),
                    ok_when_false=True,
                )
            )
            verify_gap = _gap(readiness, "verify")
            verify_commands = tooling.get("suggested_verify") or []
            checks.append(
                _check(
                    f"verify:{repo.id}",
                    verify_gap is None,
                    (
                        ", ".join(verify_commands)
                        if verify_commands
                        else (verify_gap or {}).get("detail")
                        or "no discoverable verify command"
                    ),
                    ok_when_false=True,
                )
            )

    generated = generate_workspaces(catalog, harness_root)
    checks.append(
        _check(
            "workspaces",
            bool(generated),
            f"generated {len(generated)} workspace file(s)",
        )
    )

    jira_ok = all(
        os.environ.get(name)
        for name in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
    ) or all(
        os.environ.get(name)
        for name in ("JIRA_BASE_URL", "JIRA_USERNAME", "JIRA_TOKEN")
    )
    jira: dict[str, Any] | None = None
    if not jira_ok:
        checks.append(
            _check(
                "jira_env",
                False,
                "Jira env vars are not fully set",
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
        checks.append(_check("jira_env", True, "Jira env vars are present"))

    ok = all(item["ok"] or item.get("advisory") for item in checks)
    steps = onboarding_steps(catalog, harness_root, uv=uv)
    return {
        "ok": ok,
        "harness_root": str(harness_root),
        "sibling_root": str(sibling_root),
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
        "uv": uv,
        "checks": checks,
        "onboarding": steps,
    }


def _gap(readiness: dict[str, Any], gap_id: str) -> dict[str, Any] | None:
    for gap in readiness.get("gaps") or []:
        if gap.get("id") == gap_id:
            return gap
    return None


def _check(name: str, ok: bool, detail: str, ok_when_false: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "detail": detail,
        "advisory": ok_when_false and not ok,
    }

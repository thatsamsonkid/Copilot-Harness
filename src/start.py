from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from goat import GoatError
from goat.catalog import Catalog, Repo, as_list
from goat.envapply import applied_env_preview, apply_project_env
from goat.invoke import invoke_spec
from goat.launch import load_launch_runtime, summarize_launch
from goat.workspace_detect import resolve_workspace_scope, scoped_repos

RunFn = Callable[[str, Path, dict[str, str]], int]

PACKAGE_START_SCRIPTS = ("start", "serve", "dev")
MAKE_START_TARGETS = ("start", "run", "serve", "dev", "up", "bootrun")

FRONTEND_TAGS = {"ui", "frontend", "web", "angular", "react", "vue"}
BACKEND_TAGS = {"api", "backend", "service", "java", "spring"}
INFRA_TAGS = {"infra", "devops", "ops"}
MOBILE_TAGS = {"mobile", "ios", "android"}

ROLE_ORDER = {"infra": 0, "backend": 1, "worker": 2, "frontend": 3, "mobile": 4}

PROXY_FILENAMES = (
    "proxy.conf.json",
    "proxy.conf.js",
    "proxy.conf.mjs",
    "proxy.conf.cjs",
    "proxy.conf.cts",
    "src/proxy.conf.json",
    "src/proxy.conf.js",
)

COMPOSE_FILENAMES = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
)

_PORT_IN_SCRIPT = re.compile(
    r"(?i)(?:--port|-p)\s*[= ]\s*(\d{2,5})"
)
_SERVER_PORT_FLAT = re.compile(
    r"(?im)^\s*server\.port\s*[:=]\s*(?:\$\{[^:\n]+:)?(\d{2,5})"
)
_SERVER_PORT_PROP = re.compile(
    r"(?im)^\s*server\.port\s*=\s*(?:\$\{[^:\n]+:)?(\d{2,5})"
)


def collect_start_plan(
    catalog: Catalog,
    goat_root: Path,
    *,
    workspace_id: str | None = None,
    only: list[str] | None = None,
    save: bool = False,
    refresh: bool = False,
    all_repos: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    scope = resolve_workspace_scope(
        catalog,
        goat_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    if save and not scope.id:
        raise GoatError(
            "--save needs a workspace id (pass --workspace, or open a "
            "feature .code-workspace so GOAT_WORKSPACE is set)."
        )
    if save and only:
        raise GoatError(
            "--save writes the full workspace sequence. Do not combine it with --repo."
        )

    workspace_id = scope.id
    repos = scoped_repos(catalog, scope, only=only)
    services = [inspect_start(catalog, goat_root, repo) for repo in repos]
    backends = [item["name"] for item in services if item.get("role") == "backend"]
    for item in services:
        if item.get("role") in {"frontend", "mobile"} and backends:
            item["depends_on"] = list(backends)
        else:
            item.setdefault("depends_on", [])
    services.sort(key=_service_sort_key)
    plan_file = (
        catalog.workspace_start_file(goat_root, workspace_id)
        if workspace_id
        else None
    )
    payload = {
        "workspace": workspace_id,
        "workspace_scope": scope.as_payload(),
        "sibling_root": str(catalog.sibling_root(goat_root)),
        "order": [item["name"] for item in services],
        "services": services,
        "blocked": _blocked_entries(services),
        "goat_root": str(Path(goat_root).resolve()),
        "invoke": invoke_spec(goat_root),
        "plan_file": str(plan_file) if plan_file else None,
        "plan_exists": bool(plan_file and plan_file.is_file()),
        "plan_source": "discovered",
        "unplanned": [],
        "stale": [],
    }
    if workspace_id and payload["plan_exists"] and not refresh:
        saved = load_saved_start_plan(plan_file)
        payload = apply_saved_start_plan(
            payload,
            saved,
            catalog,
            goat_root,
            only=only,
        )
    if save:
        payload["saved"] = write_saved_start_plan(plan_file, payload)
        payload["plan_exists"] = True
    payload["guidance"] = _plan_guidance(payload)
    return payload


def inspect_start(catalog: Catalog, goat_root: Path, repo: Repo | str) -> dict[str, Any]:
    if isinstance(repo, str):
        repo = catalog.repo(repo)
    path = catalog.repo_path(goat_root, repo)
    payload = _empty_service(repo, path)
    if not path.exists():
        payload["blocked"] = "repo is not cloned"
        payload["notes"].append("Clone this repo before starting it.")
        return payload

    discovered = discover_start(path, repo)
    payload.update(discovered)
    _attach_launch(payload, repo, path, goat_root)
    if not payload.get("command"):
        if payload.get("run_via") == "vscode" and payload.get("launch"):
            payload["notes"].append(
                "No shell start command. Use VS Code Run Without Debugging on "
                f"{payload['launch'].get('configuration')!r}."
            )
        else:
            payload["blocked"] = "no start command found"
            payload["notes"].append(
                "Add a command to workspaces/<id>.start.yml or a start/serve/dev script."
            )
    elif payload.get("role") == "infra" and payload.get("kind") == "compose":
        payload["notes"].append(
            "Do not start docker compose unless the user asked for the local stack."
        )
    if payload.get("proxies") and payload.get("role") == "frontend":
        payload["notes"].append(
            "Update proxy targets after backend ports are known, then start this app."
        )
    if payload.get("port_hint") is None and payload.get("command"):
        payload["notes"].append(
            "Port is unknown until the process starts. Read the startup logs."
        )
    return payload


SAVED_PLAN_HEADER = """\
# Saved start sequence for the {workspace} workspace.
# Written by: goat start --workspace {workspace} --save
# Edit this file when the boot order or commands change.
# goat start reuses the pinned order and commands here; it still scans the
# workspace for repos that are new (unplanned) or removed (stale).
"""


def load_saved_start_plan(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise GoatError(f"Invalid YAML in saved start plan {path}: {exc}") from exc
    except OSError as exc:
        raise GoatError(f"Cannot read saved start plan {path}: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise GoatError(f"Saved start plan must be a mapping: {path}")
    services_raw = raw.get("services") or []
    if not isinstance(services_raw, list):
        raise GoatError(f"Saved start plan services must be a list: {path}")
    services: list[dict[str, Any]] = []
    for item in services_raw:
        if not isinstance(item, dict) or not item.get("name"):
            raise GoatError(f"Each saved start service needs a name: {path}")
        entry: dict[str, Any] = {"name": str(item["name"])}
        command = str(item.get("command") or "").strip()
        if command:
            entry["command"] = command
        port = _as_port(item.get("port"))
        if item.get("port") not in (None, "") and port is None:
            raise GoatError(
                f"Saved start plan {path} service {entry['name']} port must be an integer"
            )
        if port:
            entry["port"] = port
        role = str(item.get("role") or "").strip().lower()
        if role:
            entry["role"] = role
        wait = str(item.get("wait") or item.get("health") or "").strip()
        if wait:
            entry["wait"] = wait
        cwd = str(item.get("cwd") or "").strip()
        if cwd:
            entry["cwd"] = _relative_cwd(f"Saved start plan {path} cwd", cwd)
        launch = str(item.get("launch") or item.get("configuration") or "").strip()
        if launch:
            entry["launch"] = launch
        env_file = str(item.get("env_file") or item.get("envFile") or "").strip()
        if env_file:
            entry["env_file"] = _relative_cwd(
                f"Saved start plan {path} env_file", env_file
            )
        method = str(item.get("method") or "").strip().lower()
        if method == "coboose":
            method = "goat"
        if method and method not in {"terminal", "vscode", "goat"}:
            raise GoatError(
                f"Saved start plan {path} service {entry['name']} "
                "method must be terminal, vscode, or goat"
            )
        if method:
            entry["method"] = method
        if "depends_on" in item:
            entry["depends_on"] = as_list(item.get("depends_on"))
        notes = item.get("notes")
        if notes:
            entry["notes"] = as_list(notes)
        services.append(entry)
    order = as_list(raw.get("order"))
    if not order:
        order = [item["name"] for item in services]
    return {
        "workspace": str(raw.get("workspace") or "").strip() or None,
        "order": order,
        "services": services,
        "notes": as_list(raw.get("notes")),
    }


def apply_saved_start_plan(
    payload: dict[str, Any],
    saved: dict[str, Any],
    catalog: Catalog,
    goat_root: Path,
    *,
    only: list[str] | None = None,
) -> dict[str, Any]:
    workspace_id = payload.get("workspace")
    workspace_names = (
        set(catalog.workspace_repo_names(workspace_id))
        if workspace_id
        else {item["name"] for item in payload["services"]}
    )
    known = {repo.name for repo in catalog.repos}
    wanted = set(only) if only else None
    saved_names: list[str] = []
    for name in list(saved.get("order") or []) + [
        item["name"] for item in saved["services"]
    ]:
        if name not in saved_names:
            saved_names.append(name)
    pins = {item["name"]: item for item in saved["services"]}
    discovered = {item["name"]: item for item in payload["services"]}
    services: list[dict[str, Any]] = []
    stale: list[str] = []
    for name in saved_names:
        if name not in known or name not in workspace_names:
            if name not in stale:
                stale.append(name)
            continue
        if wanted is not None and name not in wanted:
            continue
        item = discovered.get(name) or inspect_start(catalog, goat_root, name)
        services.append(
            _apply_saved_service(
                item,
                pins.get(name) or {},
                catalog.repo(name),
                goat_root,
            )
        )
    unplanned_items: list[dict[str, Any]] = []
    for item in payload["services"]:
        if item["name"] in saved_names:
            continue
        extra = dict(item)
        extra["notes"] = [
            *list(extra.get("notes") or []),
            "Not in the saved workspace start plan.",
        ]
        unplanned_items.append(extra)
    unplanned_items.sort(key=_service_sort_key)
    services.extend(unplanned_items)
    merged = dict(payload)
    merged["plan_source"] = "saved"
    merged["order"] = [item["name"] for item in services]
    merged["services"] = services
    merged["blocked"] = _blocked_entries(services)
    merged["unplanned"] = [item["name"] for item in unplanned_items]
    merged["stale"] = stale
    if saved.get("notes"):
        merged["saved_notes"] = list(saved["notes"])
    return merged


def write_saved_start_plan(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    existed = path.is_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace = str(payload.get("workspace") or "workspace")
    document = saved_start_document(payload)
    body = yaml.safe_dump(
        document,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    path.write_text(
        SAVED_PLAN_HEADER.format(workspace=workspace) + body,
        encoding="utf-8",
    )
    return {
        "path": str(path),
        "action": "updated" if existed else "created",
    }


def saved_start_document(payload: dict[str, Any]) -> dict[str, Any]:
    services: list[dict[str, Any]] = []
    for item in payload.get("services") or []:
        entry: dict[str, Any] = {"name": item["name"]}
        if item.get("command"):
            entry["command"] = item["command"]
        if item.get("port_hint"):
            entry["port"] = item["port_hint"]
        role = str(item.get("role") or "").strip()
        if role and role != "unknown":
            entry["role"] = role
        if item.get("wait"):
            entry["wait"] = item["wait"]
        cwd = _saved_relative_cwd(item)
        if cwd:
            entry["cwd"] = cwd
        if item.get("depends_on"):
            entry["depends_on"] = list(item["depends_on"])
        launch = item.get("launch") or {}
        if isinstance(launch, dict) and launch.get("configuration"):
            entry["launch"] = launch["configuration"]
        elif isinstance(launch, str) and launch.strip():
            entry["launch"] = launch.strip()
        if isinstance(launch, dict) and launch.get("env_file"):
            entry["env_file"] = launch["env_file"]
        method = str(item.get("method") or item.get("run_via") or "").strip()
        if method and method != "terminal":
            entry["method"] = method
        services.append(entry)
    document: dict[str, Any] = {
        "workspace": payload.get("workspace"),
        "order": list(payload.get("order") or [item["name"] for item in services]),
        "services": services,
    }
    if payload.get("saved_notes"):
        document["notes"] = list(payload["saved_notes"])
    return document


def _apply_saved_service(
    discovered: dict[str, Any],
    pin: dict[str, Any],
    repo: Repo,
    goat_root: Path,
) -> dict[str, Any]:
    merged = dict(discovered)
    applied = False
    if pin.get("command"):
        merged["command"] = pin["command"]
        merged["command_source"] = "workspace start plan"
        applied = True
    if pin.get("port"):
        merged["port_hint"] = pin["port"]
        merged["port_source"] = "workspace start plan"
        if not pin.get("wait"):
            merged["wait"] = _default_wait(pin["port"])
        applied = True
    if pin.get("wait"):
        merged["wait"] = pin["wait"]
        applied = True
    if pin.get("role"):
        merged["role"] = pin["role"]
        applied = True
    if pin.get("cwd"):
        base = merged.get("path") or merged.get("cwd")
        merged["cwd"] = str(Path(str(base)) / pin["cwd"])
        applied = True
    if "depends_on" in pin:
        merged["depends_on"] = list(pin["depends_on"])
        applied = True
    if pin.get("notes"):
        merged["notes"] = [*list(merged.get("notes") or []), *pin["notes"]]
    if pin.get("launch") or pin.get("env_file") or pin.get("method"):
        _attach_launch(
            merged,
            repo,
            Path(str(merged.get("path") or merged.get("cwd"))),
            goat_root,
            configuration=pin.get("launch"),
            env_file=pin.get("env_file"),
            method=pin.get("method") or "",
        )
        applied = True
    if applied:
        merged["source"] = "saved"
        merged["confidence"] = "high"
    if merged.get("command") and merged.get("blocked") == "no start command found":
        merged["blocked"] = None
        merged["notes"] = [
            note
            for note in (merged.get("notes") or [])
            if "start/serve/dev script" not in note
        ]
    return merged


def _saved_relative_cwd(item: dict[str, Any]) -> str | None:
    cwd = item.get("cwd")
    root = item.get("path")
    if not cwd or not root:
        return None
    try:
        relative = Path(str(cwd)).resolve().relative_to(Path(str(root)).resolve())
    except ValueError:
        return None
    if not relative.parts or relative.parts == (".",):
        return None
    return relative.as_posix()


def _relative_cwd(label: str, value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise GoatError(f"{label} must be a relative path inside the repo: {value}")
    return value


def _blocked_entries(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"name": item["name"], "reason": item.get("blocked")}
        for item in services
        if item.get("blocked")
    ]


def _plan_guidance(payload: dict[str, Any]) -> list[str]:
    lines = [
        "This command prints a plan. It does not start processes.",
        "Start backends (and infra) first, one at a time. Give each app its "
        "own VS Code terminal. Reuse a terminal already running that app; "
        "never start a second long-running process in a busy terminal.",
        "If port_hint is missing or the app binds a different port, read the "
        "startup logs and use the live port.",
        "Rewrite Angular proxy targets to the live backend URL in the sibling "
        "working tree. Do not commit that change unless the user asked.",
        "If discovery is wrong, edit workspaces/<id>.start.yml or rerun with "
        "--save after you have the right commands.",
        "Run this CLI from the goat repo (invoke.cwd). After cd into a "
        "sibling, `uv run goat` cannot spawn. Re-run with invoke.command "
        "or scripts/goat.sh; do not reuse an app terminal for goat.",
    ]
    services = payload.get("services") or []
    if any((item.get("launch") or {}).get("secret_risk") for item in services):
        lines.append(
            "When run_via is goat or launch.secret_risk is true, start that "
            "app with invoke.command plus `start run --repo <name>` (or the "
            "service `copilot_command`) or VS Code Run Without Debugging. "
            "start run applies env to the child process only. Use "
            "`start env --repo <name>` for keys and collisions, or "
            "`start env --repo <name> --shell` to apply values in a terminal. "
            "Never read launch.json, envFile, or .env, and never reconstruct "
            "env or args in the terminal."
        )
    workspace = payload.get("workspace")
    saved = payload.get("saved")
    if saved:
        lines.append(
            f"Saved the sequence to {saved.get('path')} ({saved.get('action')}). "
            "Later starts reuse this file's pinned order and commands (goat still "
            "scans the workspace for new or removed repos)."
        )
    elif workspace and payload.get("plan_source") == "saved":
        lines.append(
            f"Using saved sequence at {payload.get('plan_file')}. "
            "Pass --refresh to rediscover, or edit that file / --save to update it."
        )
    elif workspace and payload.get("plan_exists"):
        lines.append(
            f"A saved sequence exists at {payload.get('plan_file')}. "
            "This run rediscovered. Omit --refresh to use the saved file, "
            "or pass --save to overwrite it."
        )
    elif workspace:
        lines.append(
            "This workspace has no saved start sequence yet. When the order "
            f"looks right, run `goat start --save` "
            f"(or `--workspace {workspace} --save`) "
            "to write workspaces/<id>.start.yml and pin the order and commands "
            "for next time."
        )
    unplanned = payload.get("unplanned") or []
    if unplanned:
        lines.append(
            "Workspace repos missing from the saved plan: "
            + ", ".join(unplanned)
            + ". Add them to the YAML or rerun with --refresh --save."
        )
    stale = payload.get("stale") or []
    if stale:
        lines.append(
            "Saved plan lists repos that are not in this workspace: "
            + ", ".join(stale)
            + "."
        )
    return lines


def discover_start(repo_path: Path, repo: Repo) -> dict[str, Any]:
    markers = _markers(repo_path)
    package_scripts = _all_package_scripts(repo_path)
    make_targets = _make_start_targets(repo_path)
    kind, role_from_kind = _detect_kind(repo_path, markers, package_scripts)
    role = role_from_kind or _role_from_tags(repo.tags) or "unknown"
    command, command_source = _detect_command(
        repo_path, kind, package_scripts, make_targets
    )
    port_hint, port_source = _detect_port(repo_path, kind, package_scripts)
    proxies = _detect_proxies(repo_path, kind)
    compose = _compose_files(repo_path)
    confidence = _confidence(kind, command, port_hint)
    notes: list[str] = []
    if compose and kind != "compose":
        notes.append(
            "Compose file present; start it only if this service needs those containers."
        )
    return {
        "cloned": True,
        "kind": kind,
        "role": role,
        "confidence": confidence,
        "source": "discovered",
        "command": command,
        "command_source": command_source,
        "cwd": str(repo_path),
        "port_hint": port_hint,
        "port_source": port_source,
        "wait": _default_wait(port_hint),
        "proxies": proxies,
        "compose": compose,
        "markers": markers,
        "notes": notes,
        "blocked": None,
    }


def _empty_service(repo: Repo, path: Path) -> dict[str, Any]:
    return {
        "name": repo.name,
        "id": repo.name,
        "path": str(path),
        "relpath": repo.path,
        "group": repo.group,
        "tags": list(repo.tags),
        "cloned": False,
        "kind": "unknown",
        "role": _role_from_tags(repo.tags) or "unknown",
        "confidence": "none",
        "source": "none",
        "command": None,
        "command_source": None,
        "cwd": str(path),
        "port_hint": None,
        "port_source": None,
        "wait": None,
        "depends_on": [],
        "proxies": [],
        "compose": [],
        "markers": [],
        "notes": [],
        "blocked": None,
        "run_via": "terminal",
        "copilot_command": None,
        "launch": None,
    }


def _markers(repo_path: Path) -> list[str]:
    names = [
        ("angular", "angular.json"),
        ("package.json", "package.json"),
        ("pom", "pom.xml"),
        ("gradle", "build.gradle"),
        ("gradle-kts", "build.gradle.kts"),
        ("makefile", "Makefile"),
        ("pyproject", "pyproject.toml"),
        ("manage.py", "manage.py"),
        ("mvnw", "mvnw"),
        ("gradlew", "gradlew"),
        ("launch.json", ".vscode/launch.json"),
    ]
    found = [name for name, relative in names if (repo_path / relative).exists()]
    if any((repo_path / name).exists() for name in COMPOSE_FILENAMES) and "compose" not in found:
        found.append("compose")
    return found


def _detect_kind(
    repo_path: Path, markers: list[str], package_scripts: dict[str, str]
) -> tuple[str, str | None]:
    if "angular" in markers:
        return "angular", "frontend"
    if _is_spring_boot(repo_path):
        return "spring-boot", "backend"
    if "manage.py" in markers:
        return "django", "backend"
    if _looks_like_python_web(repo_path):
        return "python", "backend"
    if "package.json" in markers:
        role = "frontend" if _js_looks_frontend(package_scripts) else None
        return "node", role
    if "compose" in markers and not {"pom", "gradle", "gradle-kts", "pyproject"} & set(markers):
        return "compose", "infra"
    if "makefile" in markers:
        return "make", None
    return "unknown", None


def _detect_command(
    repo_path: Path,
    kind: str,
    package_scripts: dict[str, str],
    make_targets: list[str],
) -> tuple[str | None, str | None]:
    if kind == "spring-boot":
        if (repo_path / "mvnw").is_file() or (repo_path / "mvnw.cmd").is_file():
            return "./mvnw spring-boot:run", "mvnw"
        if (repo_path / "gradlew").is_file() or (repo_path / "gradlew.bat").is_file():
            return "./gradlew bootRun", "gradlew"
        if (repo_path / "pom.xml").is_file():
            return "mvn spring-boot:run", "pom.xml"
        if (repo_path / "build.gradle").is_file() or (repo_path / "build.gradle.kts").is_file():
            return "gradle bootRun", "build.gradle"
    if kind == "django":
        return "python manage.py runserver", "manage.py"
    if kind == "compose":
        compose = _compose_files(repo_path)
        filename = Path(compose[0]).name if compose else "compose.yaml"
        return f"docker compose -f {filename} up", filename
    if package_scripts:
        runner = _js_runner(repo_path)
        for name in PACKAGE_START_SCRIPTS:
            if name in package_scripts:
                return f"{runner} {name}", f"package.json scripts.{name}"
    if make_targets:
        preferred = next(
            (name for name in ("start", "run", "serve", "dev", "up") if name in make_targets),
            make_targets[0],
        )
        return f"make {preferred}", f"Makefile {preferred}"
    if kind == "python":
        return None, None
    return None, None


def _detect_port(
    repo_path: Path, kind: str, package_scripts: dict[str, str]
) -> tuple[int | None, str | None]:
    if kind == "angular":
        port, source = _angular_serve_port(repo_path)
        if port:
            return port, source
        script_port = _port_from_scripts(package_scripts)
        if script_port:
            return script_port
        return 4200, "angular default"
    if kind == "spring-boot":
        found = _spring_port(repo_path)
        if found:
            return found
        return 8080, "spring-boot default"
    if kind == "django":
        script_port = _port_from_scripts(package_scripts)
        return script_port if script_port else (8000, "django default")
    script_port = _port_from_scripts(package_scripts)
    if script_port:
        return script_port
    return None, None


def _detect_proxies(repo_path: Path, kind: str) -> list[dict[str, Any]]:
    paths: list[Path] = []
    seen: set[str] = set()
    configured = _angular_proxy_files(repo_path) if kind == "angular" else []
    for relative in [*configured, *PROXY_FILENAMES]:
        path = (repo_path / relative).resolve()
        key = str(path)
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        paths.append(path)
    proxies: list[dict[str, Any]] = []
    for path in paths:
        item: dict[str, Any] = {
            "path": str(path),
            "relative": str(path.relative_to(repo_path)),
            "targets": [],
        }
        if path.suffix == ".json":
            item["targets"] = _parse_proxy_json(path)
        else:
            item["targets"] = _parse_proxy_js_targets(path)
        proxies.append(item)
    return proxies


def _angular_proxy_files(repo_path: Path) -> list[str]:
    data = _read_json(repo_path / "angular.json")
    if not isinstance(data, dict):
        return []
    found: list[str] = []
    for project in (data.get("projects") or {}).values():
        if not isinstance(project, dict):
            continue
        serve = _angular_serve_block(project)
        options = serve.get("options") if isinstance(serve.get("options"), dict) else {}
        proxy = options.get("proxyConfig")
        if isinstance(proxy, str):
            found.append(proxy)
    return found


def _angular_serve_port(repo_path: Path) -> tuple[int | None, str | None]:
    data = _read_json(repo_path / "angular.json")
    if not isinstance(data, dict):
        return None, None
    for name, project in (data.get("projects") or {}).items():
        if not isinstance(project, dict):
            continue
        serve = _angular_serve_block(project)
        options = serve.get("options") if isinstance(serve.get("options"), dict) else {}
        port = _as_port(options.get("port"))
        if port:
            return port, f"angular.json projects.{name}.serve.options.port"
    return None, None


def _angular_serve_block(project: dict[str, Any]) -> dict[str, Any]:
    for key in ("architect", "targets"):
        block = project.get(key)
        if isinstance(block, dict) and isinstance(block.get("serve"), dict):
            return block["serve"]
    return {}


def _spring_port(repo_path: Path) -> tuple[int | None, str | None]:
    preferred = (
        "application-local.yml",
        "application-local.yaml",
        "application-local.properties",
        "application-dev.yml",
        "application-dev.yaml",
        "application-dev.properties",
        "application.yml",
        "application.yaml",
        "application.properties",
    )
    search_dirs = (
        repo_path / "src" / "main" / "resources",
        repo_path / "src" / "main" / "resources" / "config",
        repo_path / "config",
        repo_path,
    )
    candidates: list[Path] = []
    seen: set[str] = set()
    for directory in search_dirs:
        if not directory.is_dir() and directory != repo_path:
            continue
        for name in preferred:
            path = directory / name
            key = str(path)
            if key in seen or not path.is_file():
                continue
            seen.add(key)
            candidates.append(path)
    candidates.sort(
        key=lambda item: (
            preferred.index(item.name),
            0 if "local" in item.name else 1,
            len(item.parts),
        )
    )
    for path in candidates:
        port = _parse_server_port(_read_text(path))
        if port:
            try:
                relative = str(path.relative_to(repo_path))
            except ValueError:
                relative = path.name
            return port, relative
    return None, None


def _parse_server_port(text: str) -> int | None:
    match = _SERVER_PORT_FLAT.search(text) or _SERVER_PORT_PROP.search(text)
    if match:
        return _as_port(match.group(1))
    in_server = False
    server_indent = 0
    for raw in text.splitlines():
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        label = stripped.strip()
        if re.match(r"server\s*:", label):
            in_server = True
            server_indent = indent
            continue
        if in_server:
            if indent <= server_indent:
                in_server = False
            else:
                match = re.match(
                    r"port\s*:\s*(?:\$\{[^:]+:)?(\d{2,5})", label
                )
                if match:
                    return _as_port(match.group(1))
    return None


def _parse_proxy_json(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path)
    targets: list[dict[str, Any]] = []
    if isinstance(data, dict):
        for context, spec in data.items():
            if not isinstance(context, str) or context.startswith("$"):
                continue
            if isinstance(spec, dict) and spec.get("target"):
                targets.append({"context": context, "target": str(spec["target"])})
    elif isinstance(data, list):
        for spec in data:
            if not isinstance(spec, dict) or not spec.get("target"):
                continue
            context = spec.get("context") or spec.get("path") or spec.get("contextPath")
            targets.append({"context": context, "target": str(spec["target"])})
    return targets


def _parse_proxy_js_targets(path: Path) -> list[dict[str, Any]]:
    text = _read_text(path)
    targets: list[dict[str, Any]] = []
    for match in re.finditer(r"""target\s*:\s*['"]([^'"]+)['"]""", text):
        targets.append({"context": None, "target": match.group(1)})
    return targets


def _port_from_scripts(package_scripts: dict[str, str]) -> tuple[int | None, str | None]:
    for name in PACKAGE_START_SCRIPTS:
        script = package_scripts.get(name)
        if not script:
            continue
        match = _PORT_IN_SCRIPT.search(script)
        if match:
            return _as_port(match.group(1)), f"package.json scripts.{name}"
    return None, None


def _all_package_scripts(repo_path: Path) -> dict[str, str]:
    data = _read_json(repo_path / "package.json")
    if not isinstance(data, dict):
        return {}
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return {}
    return {
        str(name): str(value)
        for name, value in scripts.items()
        if isinstance(value, str)
    }


def _make_start_targets(repo_path: Path) -> list[str]:
    makefile = repo_path / "Makefile"
    if not makefile.is_file():
        return []
    found: list[str] = []
    for raw in _read_text(makefile).splitlines():
        if raw.startswith("\t") or raw.startswith("#") or ":" not in raw:
            continue
        target = raw.split(":", 1)[0].strip().lower()
        if target in MAKE_START_TARGETS and target not in found:
            found.append(target)
    return found


def _is_spring_boot(repo_path: Path) -> bool:
    needles = ("spring-boot", "org.springframework.boot")
    for relative in ("pom.xml", "build.gradle", "build.gradle.kts"):
        path = repo_path / relative
        if path.is_file() and any(needle in _read_text(path).lower() for needle in needles):
            return True
    return False


def _looks_like_python_web(repo_path: Path) -> bool:
    needles = ("uvicorn", "fastapi", "flask", "django", "gunicorn")
    for relative in ("pyproject.toml", "requirements.txt", "Pipfile"):
        path = repo_path / relative
        if path.is_file() and any(needle in _read_text(path).lower() for needle in needles):
            return True
    return False


def _js_looks_frontend(package_scripts: dict[str, str]) -> bool:
    blob = " ".join(package_scripts.values()).lower()
    return any(token in blob for token in ("ng serve", "vite", "next", "webpack", "react-scripts"))


def _role_from_tags(tags: list[str]) -> str | None:
    lowered = {tag.lower() for tag in tags}
    if lowered & FRONTEND_TAGS:
        return "frontend"
    if lowered & BACKEND_TAGS:
        return "backend"
    if lowered & INFRA_TAGS:
        return "infra"
    if lowered & MOBILE_TAGS:
        return "mobile"
    return None


def _compose_files(repo_path: Path) -> list[str]:
    found = []
    for name in COMPOSE_FILENAMES:
        path = repo_path / name
        if path.is_file():
            found.append(str(path))
    return found


def _confidence(kind: str, command: str | None, port_hint: int | None) -> str:
    if kind in {"angular", "spring-boot", "django"} and command:
        return "high"
    if command and port_hint:
        return "medium"
    if command:
        return "medium"
    return "low"


def _default_wait(port: int | None) -> str | None:
    if not port:
        return None
    return f"listen:{port}"


def _js_runner(repo_path: Path) -> str:
    if (repo_path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_path / "yarn.lock").exists():
        return "yarn"
    if (repo_path / "bun.lockb").exists() or (repo_path / "bun.lock").exists():
        return "bun run"
    return "npm run"


def _as_port(value: Any) -> int | None:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if port < 1 or port > 65535:
        return None
    return port


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _service_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    role_rank = ROLE_ORDER.get(str(item.get("role") or ""), 9)
    blocked = 1 if item.get("blocked") else 0
    return (role_rank, blocked, str(item.get("name") or ""))


def _attach_launch(
    payload: dict[str, Any],
    repo: Repo,
    repo_path: Path,
    goat_root: Path,
    *,
    configuration: str | None = None,
    env_file: str | None = None,
    method: str = "",
) -> None:
    launch = summarize_launch(
        repo_path,
        kind=str(payload.get("kind") or ""),
        repo_name=repo.name,
        configuration=configuration or None,
        env_file=env_file or None,
    )
    payload["launch"] = launch
    payload["run_via"] = _run_via(payload.get("command"), method, launch)
    payload["copilot_command"] = _copilot_command(
        repo.name, payload["run_via"], launch, goat_root
    )
    if not launch:
        return
    if launch.get("file"):
        payload.setdefault("markers", [])
        if "launch.json" not in payload["markers"]:
            payload["markers"].append("launch.json")
    if launch.get("secret_risk"):
        config = launch.get("configuration") or "the named launch configuration"
        if payload["run_via"] == "vscode":
            payload["notes"].append(
                f"This app has launch.json env/args. Start with VS Code Run "
                f"Without Debugging on {config!r}. Do not read launch.json or "
                "reconstruct env in the terminal."
            )
        else:
            payload["notes"].append(
                f"This app has launch.json env/args. Start with "
                f"`{invoke_spec(goat_root)['command']} start run --repo {repo.name}` "
                "or VS Code Run "
                f"Without Debugging on {config!r}. Do not read launch.json or "
                "reconstruct env in the terminal."
            )


def _run_via(
    command: str | None,
    method: str,
    launch: dict[str, Any] | None,
) -> str:
    secret_risk = bool(launch and launch.get("secret_risk"))
    uses_inputs = bool(launch and launch.get("uses_vscode_inputs"))
    if uses_inputs:
        return "vscode"
    if method == "vscode":
        return "vscode"
    if method in {"goat", "coboose"} and command:
        return "goat"
    if method == "terminal" and secret_risk:
        return "goat" if command else "vscode"
    if method == "terminal":
        return "terminal"
    if secret_risk and command:
        return "goat"
    if secret_risk:
        return "vscode"
    return "terminal"


def _copilot_command(
    repo_name: str,
    run_via: str,
    launch: dict[str, Any] | None,
    goat_root: Path,
) -> str | None:
    if run_via != "goat":
        return None
    command = f"{invoke_spec(goat_root)['command']} start run --repo {repo_name}"
    config = (launch or {}).get("configuration")
    if isinstance(config, str) and config:
        command += f" --configuration {shlex.quote(config)}"
    return command


def workspace_folder_map(catalog: Catalog, goat_root: Path) -> dict[str, Path]:
    folders = {
        repo.name: catalog.repo_path(goat_root, repo) for repo in catalog.repos
    }
    folders["goat"] = Path(goat_root).resolve()
    return folders


def prepare_project_env(
    catalog: Catalog,
    goat_root: Path,
    repo_name: str,
    *,
    configuration: str | None = None,
) -> dict[str, Any]:
    """Load launch.json / envFile keys in-process. No start command required."""
    service = inspect_start(catalog, goat_root, repo_name)
    if service.get("blocked") == "repo is not cloned":
        raise GoatError(f"Repository {repo_name} is not cloned")
    launch = service.get("launch")
    if isinstance(configuration, str) and configuration.strip():
        launch = summarize_launch(
            Path(service["path"]),
            kind=str(service.get("kind") or ""),
            repo_name=repo_name,
            configuration=configuration.strip(),
            env_file=(launch or {}).get("env_file") if launch else None,
        )
        service["launch"] = launch
    runtime = load_launch_runtime(
        Path(service["path"]),
        launch if isinstance(launch, dict) else None,
        configuration=configuration,
        environ=os.environ.copy(),
        workspace_folders=workspace_folder_map(catalog, goat_root),
    )
    if runtime.get("uses_vscode_inputs"):
        raise GoatError(
            "launch.json env/args use VS Code input variables. "
            "Use Run Without Debugging on "
            f"{(launch or {}).get('configuration')!r}; "
            "do not reconstruct those values in the terminal."
        )
    env = dict(runtime.get("env") or {})
    cwd = runtime.get("cwd") or Path(service["cwd"])
    return {
        "name": service["name"],
        "cwd": str(cwd),
        "command": service.get("command"),
        "kind": str(service.get("kind") or ""),
        "env": env,
        "env_keys": sorted(env),
        "env_file": (launch or {}).get("env_file") if launch else None,
        "launch_configuration": (launch or {}).get("configuration") if launch else None,
        "args": runtime.get("args"),
        "vm_args": runtime.get("vm_args"),
        "applied_args": bool(runtime.get("args")),
        "applied_vm_args": bool(runtime.get("vm_args")),
        "run_via": "goat",
    }


def prepare_start_run(
    catalog: Catalog,
    goat_root: Path,
    repo_name: str,
    *,
    configuration: str | None = None,
) -> dict[str, Any]:
    """Build a redacted start-run payload and the in-process env/args."""
    prepared = prepare_project_env(
        catalog, goat_root, repo_name, configuration=configuration
    )
    command = prepared.get("command")
    if not command:
        config = prepared.get("launch_configuration")
        raise GoatError(
            "No shell start command for "
            f"{repo_name}. Use VS Code Run Without Debugging on {config!r}."
        )
    env = dict(prepared["env"])
    exec_env = dict(env)
    exec_command = _command_with_launch_args(
        str(command),
        str(prepared.get("kind") or ""),
        prepared.get("args"),
        prepared.get("vm_args"),
        exec_env,
    )
    return {
        **prepared,
        "command": str(command),
        "exec_command": exec_command,
        "env": env,
        "env_keys": sorted(env),
        "run_via": "goat",
    }


def start_run_preview(
    prepared: dict[str, Any],
    applied: Any | None = None,
) -> dict[str, Any]:
    """JSON-safe view of a prepared run. No env/arg values."""
    command = str(prepared.get("command") or "")
    payload = {
        "name": prepared["name"],
        "cwd": prepared["cwd"],
        "command": prepared["command"],
        "exec_command": redacted_exec_command(
            command,
            prepared.get("args"),
            prepared.get("vm_args"),
        ),
        "arg_count": _cli_token_count(prepared.get("args")),
        "vm_arg_count": _cli_token_count(prepared.get("vm_args")),
        "java_tool_options": _uses_java_tool_options(command, prepared.get("vm_args")),
        "env_keys": list(prepared.get("env_keys") or []),
        "env_file": prepared.get("env_file"),
        "launch_configuration": prepared.get("launch_configuration"),
        "applied_args": bool(prepared.get("applied_args")),
        "applied_vm_args": bool(prepared.get("applied_vm_args")),
        "run_via": "goat",
        "dry_run": True,
    }
    if applied is not None:
        payload.update(applied_env_preview(applied))
    return payload


def execute_start_run(
    catalog: Catalog,
    goat_root: Path,
    repo_name: str,
    *,
    configuration: str | None = None,
    dry_run: bool = False,
    prefix: str | None = None,
    keep_existing: bool = False,
    run: RunFn | None = None,
) -> dict[str, Any]:
    prepared = prepare_start_run(
        catalog, goat_root, repo_name, configuration=configuration
    )
    applied = apply_project_env(
        prepared["env"],
        os.environ,
        repo_name=prepared["name"],
        configuration=prepared.get("launch_configuration"),
        prefix=prefix,
        keep_existing=keep_existing,
    )
    # Prefix is applied to launch keys only. Recompute JVM extras on the
    # merged child env so JAVA_TOOL_OPTIONS keeps its unprefixed name.
    exec_command = _command_with_launch_args(
        str(prepared["command"]),
        str(prepared.get("kind") or ""),
        prepared.get("args"),
        prepared.get("vm_args"),
        applied.env,
    )
    preview = start_run_preview(prepared, applied)
    if dry_run:
        return preview
    _print_run_banner(preview, action="Starting")
    runner = run or _run_foreground
    exit_code = runner(exec_command, Path(prepared["cwd"]), applied.env)
    return {
        **preview,
        "dry_run": False,
        "exit_code": exit_code,
    }


def start_env_preview(
    prepared: dict[str, Any],
    applied: Any,
) -> dict[str, Any]:
    """JSON-safe view of a project env apply. No values."""
    return {
        "name": prepared["name"],
        "cwd": prepared["cwd"],
        "command": prepared.get("command"),
        "env_file": prepared.get("env_file"),
        "launch_configuration": prepared.get("launch_configuration"),
        "run_via": "goat",
        "shell": False,
        **applied_env_preview(applied),
    }


def execute_start_env(
    catalog: Catalog,
    goat_root: Path,
    repo_name: str,
    *,
    configuration: str | None = None,
    prefix: str | None = None,
    keep_existing: bool = False,
    shell: bool = False,
    exec_fn: Callable[[dict[str, str], Path], None] | None = None,
) -> dict[str, Any]:
    """Apply one repo's launch env in-process, or exec a shell that has it."""
    prepared = prepare_project_env(
        catalog, goat_root, repo_name, configuration=configuration
    )
    applied = apply_project_env(
        prepared["env"],
        os.environ,
        repo_name=prepared["name"],
        configuration=prepared.get("launch_configuration"),
        prefix=prefix,
        keep_existing=keep_existing,
    )
    preview = start_env_preview(prepared, applied)
    if not shell:
        return preview
    _print_run_banner(preview, action="Applying")
    runner = exec_fn or _exec_login_shell
    runner(applied.env, Path(prepared["cwd"]))
    return {**preview, "shell": True}


def _print_run_banner(preview: dict[str, Any], *, action: str = "Starting") -> None:
    keys = preview.get("env_keys") or []
    config = preview.get("launch_configuration")
    parts = [f"{action} {preview['name']}"]
    if config:
        parts.append(f"launch {config!r}")
    if keys:
        parts.append("env_keys=" + ",".join(keys))
    overwritten = preview.get("overwritten_keys") or []
    if overwritten:
        parts.append("overwritten=" + ",".join(overwritten))
    skipped = preview.get("skipped_keys") or []
    if skipped:
        parts.append("kept=" + ",".join(skipped))
    prefix = preview.get("prefix")
    if prefix:
        parts.append(f"prefix={prefix}")
    print(" ".join(parts), file=sys.stderr)
    exec_command = preview.get("exec_command")
    if exec_command:
        print(f"exec_command {exec_command}", file=sys.stderr)


def _run_foreground(command: str, cwd: Path, env: dict[str, str]) -> int:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        shell=True,
        check=False,
    )
    return int(completed.returncode)


def _exec_login_shell(env: dict[str, str], cwd: Path) -> None:
    """Replace this process with a shell that already has project env."""
    os.chdir(cwd)
    if os.name == "nt":
        shell = os.environ.get("COMSPEC") or "cmd.exe"
        os.execvpe(shell, [shell], env)
        return
    shell = os.environ.get("SHELL") or "/bin/sh"
    os.execvpe(shell, [shell], env)


REDACTED_ARG = "<redacted>"


def redacted_exec_command(command: str, args: Any, vm_args: Any) -> str:
    """Same argv shape as the real exec, with launch arg values hidden."""
    return _assemble_exec_command(command, args, vm_args, redact=True)


def _command_with_launch_args(
    command: str,
    kind: str,
    args: Any,
    vm_args: Any,
    env: dict[str, str],
) -> str:
    del kind
    if _uses_java_tool_options(command, vm_args):
        existing = env.get("JAVA_TOOL_OPTIONS", "")
        env["JAVA_TOOL_OPTIONS"] = f"{existing} {_join_cli_args(vm_args)}".strip()
    return _assemble_exec_command(command, args, vm_args, redact=False)


def _assemble_exec_command(
    command: str,
    args: Any,
    vm_args: Any,
    *,
    redact: bool,
) -> str:
    args_str = _join_cli_args(args)
    vm_str = _join_cli_args(vm_args)
    args_out = REDACTED_ARG if redact and args_str else args_str
    vm_out = REDACTED_ARG if redact and vm_str else vm_str
    if not args_str and not (vm_str and "spring-boot:run" in command):
        return command
    if "spring-boot:run" in command:
        extra: list[str] = []
        if args_str:
            extra.append(
                f"-Dspring-boot.run.arguments={args_out if redact else shlex.quote(args_str)}"
            )
        if vm_str:
            extra.append(
                f"-Dspring-boot.run.jvmArguments={vm_out if redact else shlex.quote(vm_str)}"
            )
        return f"{command} {' '.join(extra)}"
    if "bootRun" in command and args_str:
        suffix = args_out if redact else shlex.quote(args_str)
        return f"{command} --args={suffix}"
    if args_str:
        rendered = REDACTED_ARG if redact else _quote_cli_args(args)
        return f"{command} {rendered}".strip()
    return command


def _uses_java_tool_options(command: str, vm_args: Any) -> bool:
    return bool(_join_cli_args(vm_args)) and "spring-boot:run" not in command


def _cli_token_count(value: Any) -> int:
    if value is None or value == "" or value == []:
        return 0
    if isinstance(value, list):
        return len([part for part in value if part is not None and part != ""])
    text = str(value).strip()
    if not text:
        return 0
    return len(shlex.split(text))


def _join_cli_args(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(part) for part in value if part is not None and part != "")
    return str(value)


def _cli_arg_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(part) for part in value if part is not None and part != ""]
    text = str(value).strip()
    if not text:
        return []
    return shlex.split(text)


def _quote_cli_args(value: Any) -> str:
    """Shell-quote each launch arg. The generic exec path runs through a shell,
    so unquoted tokens with spaces or metacharacters would split or execute.
    """
    return " ".join(shlex.quote(part) for part in _cli_arg_list(value))

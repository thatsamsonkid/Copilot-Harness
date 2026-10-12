"""Discover Bruno collections and wrap the bru CLI.

Yard Goat does not reimplement HTTP. ``bru run`` already executes a request
or folder with ``--env`` / ``--env-var``. This module tells Copilot where
the sibling Bruno repo is, what collections / environments / workflows
exist, and which cwd + env to pass to bru.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import yaml

from goat import GoatError
from goat.bruno_fields import (
    DEFAULT_ENV,
    DEFAULT_SERVICES_FILE,
    DEFAULT_WORKFLOWS_FILE,
    INVENTORY_NOTE,
    LEGACY_SERVICES_FILE,
    LEGACY_WORKFLOWS_FILE,
    BrunoService,
    BrunoSettings,
    project_bruno,
)
from goat.catalog import Catalog, Repo, as_list

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".bruno",
}

HTTP_METHODS = (
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
    "graphql",
)
_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_:-]*")
_META_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)$")
_DOCS_LIMIT = 240
_OUTPUT_LIMIT = 4000
_ERR_LIMIT = 2000
_RUN_TIMEOUT = 60

RunFn = Callable[..., Any]


@dataclass
class BrunoCollection:
    id: str
    name: str
    repo: str
    path: Path
    relpath: str
    requests: list[dict[str, Any]] = field(default_factory=list)
    environments: list[dict[str, Any]] = field(default_factory=list)
    folders: list[str] = field(default_factory=list)
    services: list[dict[str, Any]] = field(default_factory=list)
    workflows: list[dict[str, Any]] = field(default_factory=list)


def bru_cli_status() -> dict[str, Any]:
    path = shutil.which("bru")
    return {"present": bool(path), "path": path}


def _overlay_file(root: Path, preferred: str, legacy: str) -> Path:
    """Prefer goat.* overlay files; still read coboose.* when that is all that exists."""
    primary = root / preferred
    if primary.is_file() or preferred == legacy:
        return primary
    fallback = root / legacy
    return fallback if fallback.is_file() else primary


def collect_bruno_inventory(
    catalog: Catalog,
    goat_root: Path,
    *,
    settings: BrunoSettings | None = None,
) -> dict[str, Any]:
    settings = settings or catalog.bruno
    discovered = _discover(catalog, goat_root, settings)
    payload = {
        "kind": "bruno_inventory",
        "bru_cli": discovered["bru_cli"],
        "default_env": settings.default_env,
        "repos": discovered["repos"],
        "collections": [_collection_summary(item) for item in discovered["collections"]],
        "services": discovered["services"],
        "workflows": [_workflow_summary(item) for item in discovered["workflows"]],
        "missing_repos": discovered["missing_repos"],
        "clone_command": discovered["clone_command"],
        "note": INVENTORY_NOTE,
    }
    return project_bruno(payload, settings)


def list_bruno_requests(
    catalog: Catalog,
    goat_root: Path,
    target: str | None = None,
    *,
    settings: BrunoSettings | None = None,
) -> dict[str, Any]:
    settings = settings or catalog.bruno
    discovered = _discover(catalog, goat_root, settings)
    collections = discovered["collections"]
    collection = None
    if target:
        collection = _optional_collection(collections, target)
    if collection is not None:
        requests = list(collection.requests)
    elif target:
        requests = [
            item
            for item in _all_requests(collections)
            if _request_matches(item, target)
        ]
        if not requests:
            raise GoatError(
                f"Unknown Bruno collection or request {target!r}. "
                "Run `goat bruno collections` or `goat bruno requests`."
            )
    else:
        requests = _all_requests(collections)
    payload = {
        "kind": "bruno_requests",
        "collection": collection.id if collection else None,
        "requests": requests,
        "note": INVENTORY_NOTE,
    }
    return project_bruno(payload, settings)


def list_bruno_envs(
    catalog: Catalog,
    goat_root: Path,
    target: str | None = None,
    *,
    settings: BrunoSettings | None = None,
) -> dict[str, Any]:
    settings = settings or catalog.bruno
    discovered = _discover(catalog, goat_root, settings)
    collections = discovered["collections"]
    collection = _optional_collection(collections, target) if target else None
    if target and collection is None:
        raise GoatError(
            f"Unknown Bruno collection {target!r}. "
            "Run `goat bruno collections`."
        )
    chosen = [collection] if collection else collections
    environments = [item for col in chosen for item in col.environments]
    payload = {
        "kind": "bruno_envs",
        "default_env": settings.default_env,
        "collection": collection.id if collection else None,
        "environments": environments,
        "services": [
            item
            for item in discovered["services"]
            if collection is None or _service_matches_collection(item, collection)
        ],
        "note": (
            "Environment values are not returned. Use `bru run --env NAME` "
            "or `goat bruno run REQUEST --env NAME`. Secrets stay in "
            "the Bruno environment file."
        ),
    }
    return project_bruno(payload, settings)


def list_bruno_workflows(
    catalog: Catalog,
    goat_root: Path,
    name: str | None = None,
    *,
    settings: BrunoSettings | None = None,
) -> dict[str, Any]:
    settings = settings or catalog.bruno
    discovered = _discover(catalog, goat_root, settings)
    workflows = discovered["workflows"]
    if name:
        workflows = [
            item
            for item in workflows
            if item["id"] == name or item["id"].endswith(f"/{name}")
        ]
        if not workflows:
            raise GoatError(
                f"Unknown Bruno workflow {name!r}. "
                "Run `goat bruno workflows`."
            )
        workflows = [
            _workflow_plan(item, discovered["collections"], settings)
            for item in workflows
        ]
    else:
        workflows = [_workflow_summary(item) for item in workflows]
    payload = {
        "kind": "bruno_workflows",
        "default_env": settings.default_env,
        "workflows": workflows,
        "note": (
            "A workflow is a plan, not an HTTP runner. Execute each step "
            "with `goat bruno run` (or `bru run` from the collection "
            "root). Pick values from the previous response, then pass them "
            "as `--env-var`."
        ),
    }
    return project_bruno(payload, settings)


def run_bruno_request(
    catalog: Catalog,
    goat_root: Path,
    target: str,
    *,
    collection: str | None = None,
    service: str | None = None,
    env: str | None = None,
    env_vars: list[str] | None = None,
    dry_run: bool = False,
    settings: BrunoSettings | None = None,
    run_fn: RunFn | None = None,
) -> dict[str, Any]:
    settings = settings or catalog.bruno
    discovered = _discover(catalog, goat_root, settings)
    collections = discovered["collections"]
    if not collections and discovered["missing_repos"]:
        raise GoatError(
            "Bruno repo is not cloned. "
            + (discovered["clone_command"] or "Add a repositories.yml entry tagged `bruno`.")
        )
    scoped = collections
    if collection:
        match = _require_collection(collections, collection)
        scoped = [match]
    if service:
        service_row = _require_service(discovered["services"], service)
        match = _collection_for_service(scoped, service_row)
        scoped = [match]
        if not env:
            env = service_row.get("env") or None
    request = _require_request(scoped, target)
    owner = _collection_by_id(collections, request["collection"])
    if owner is None:
        raise GoatError(f"Request {target!r} has no collection")
    resolved_env = _resolve_env(settings, owner, env, discovered["services"])
    pairs = parse_env_vars(env_vars)
    display_cmd = _bru_command(request["path"], resolved_env, pairs, redact=True)
    real_cmd = _bru_command(request["path"], resolved_env, pairs, redact=False)
    payload: dict[str, Any] = {
        "kind": "bruno_run",
        "dry_run": dry_run,
        "cwd": str(owner.path),
        "collection": owner.id,
        "request": request,
        "env": resolved_env,
        "env_var_keys": [key for key, _ in pairs],
        "bru_command": display_cmd,
        "note": INVENTORY_NOTE,
    }
    if dry_run:
        return project_bruno(payload, settings)

    bru = shutil.which("bru")
    if not bru:
        raise GoatError(
            "bru is not on PATH. Install the Bruno CLI "
            "(`npm install -g @usebruno/cli`) and retry. "
            "Discovery (`goat bruno collections`) does not need bru."
        )
    runner = run_fn or subprocess.run
    result = runner(
        real_cmd,
        cwd=str(owner.path),
        capture_output=True,
        text=True,
        timeout=_RUN_TIMEOUT,
        check=False,
    )
    payload["exit_code"] = int(getattr(result, "returncode", 0) or 0)
    payload["stdout"] = _clip(getattr(result, "stdout", "") or "", _OUTPUT_LIMIT)
    payload["stderr"] = _clip(getattr(result, "stderr", "") or "", _ERR_LIMIT)
    projected = project_bruno(payload, settings)
    if payload["exit_code"] != 0:
        raise GoatError("bru run failed", payload=projected)
    return projected


def parse_env_vars(values: Iterable[str] | None) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in values or []:
        text = str(raw).strip()
        if not text or "=" not in text:
            raise GoatError(
                f"Invalid --env-var {raw!r}. Use KEY=value (repeatable)."
            )
        key, value = text.split("=", 1)
        key = key.strip()
        if not key:
            raise GoatError(f"Invalid --env-var {raw!r}. Use KEY=value.")
        pairs.append((key, value))
    return pairs


def parse_bru_blocks(text: str) -> list[tuple[str, str]]:
    """Return top-level Bru `(name, body)` blocks. Body excludes the braces."""
    blocks: list[tuple[str, str]] = []
    i = 0
    length = len(text)
    while i < length:
        while i < length and text[i].isspace():
            i += 1
        if i >= length:
            break
        if text.startswith("//", i):
            newline = text.find("\n", i)
            i = length if newline == -1 else newline + 1
            continue
        match = _IDENT.match(text, i)
        if not match:
            i += 1
            continue
        name = match.group(0)
        i = match.end()
        while i < length and text[i].isspace():
            i += 1
        if i >= length or text[i] not in "{[":
            continue
        opener = text[i]
        closer = "}" if opener == "{" else "]"
        end = _matching_close(text, i, opener, closer)
        if end == -1:
            break
        blocks.append((name, text[i + 1 : end]))
        i = end + 1
    return blocks


def parse_bru_request(path: Path, collection_root: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    blocks = {name: body for name, body in parse_bru_blocks(text)}
    meta = _parse_meta(blocks.get("meta", ""))
    kind = (meta.get("type") or "http").lower()
    if kind in {"folder", "collection"}:
        return None
    method = next((name for name in HTTP_METHODS if name in blocks), "")
    url = ""
    if method:
        url = _meta_value(blocks[method], "url")
    rel = path.relative_to(collection_root).as_posix()
    folder = path.parent.relative_to(collection_root).as_posix()
    if folder == ".":
        folder = ""
    seq_raw = meta.get("seq") or ""
    try:
        seq = int(seq_raw) if seq_raw else None
    except ValueError:
        seq = None
    docs = _clip(blocks.get("docs", "").strip(), _DOCS_LIMIT)
    name = meta.get("name") or path.stem
    return {
        "id": "",
        "name": name,
        "method": method.upper() if method and method != "graphql" else method,
        "url": url,
        "path": rel,
        "collection": "",
        "seq": seq,
        "docs": docs,
        "folder": folder,
    }


def parse_bru_environment(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {"name": path.stem, "path": path.name, "vars": [], "secrets": []}
    vars_names: list[str] = []
    secrets: list[str] = []
    for name, body in parse_bru_blocks(text):
        lowered = name.lower()
        if lowered == "vars":
            vars_names.extend(_block_keys(body))
        elif lowered in {"vars:secret", "secret"}:
            secrets.extend(_secret_names(body))
    # Never return values — names only.
    unique_vars = _unique(vars_names)
    unique_secrets = _unique(secrets)
    return {
        "name": path.stem,
        "path": path.name,
        "vars": [item for item in unique_vars if item not in set(unique_secrets)],
        "secrets": unique_secrets,
    }


def parse_workflow_file(
    path: Path,
    *,
    collection_id: str = "",
    repo: str = "",
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        return []
    except yaml.YAMLError as exc:
        warnings.warn(
            f"Ignoring malformed Bruno workflow file {path}: {exc}", stacklevel=2
        )
        return []
    items = _workflow_items(raw)
    workflows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        workflow_id = str(item.get("id") or item.get("name") or "").strip()
        if not workflow_id:
            continue
        steps = []
        for step in item.get("steps") or []:
            if not isinstance(step, dict):
                continue
            request = str(step.get("request") or step.get("bru") or "").strip()
            if not request:
                continue
            pick = step.get("pick") or {}
            if not isinstance(pick, dict):
                pick = {}
            env_vars = step.get("env_vars") or step.get("vars") or {}
            if not isinstance(env_vars, dict):
                env_vars = {}
            steps.append(
                {
                    "id": str(step.get("id") or Path(request).stem),
                    "request": request,
                    "pick": {str(key): str(value) for key, value in pick.items()},
                    "needs": as_list(step.get("needs")),
                    "env_vars": {
                        str(key): str(value) for key, value in env_vars.items()
                    },
                    "env": str(step.get("env") or "").strip(),
                }
            )
        workflows.append(
            {
                "id": workflow_id,
                "description": str(item.get("description") or ""),
                "env": str(item.get("env") or "").strip(),
                "service": str(item.get("service") or "").strip(),
                "collection": str(item.get("collection") or collection_id),
                "repo": repo,
                "steps": steps,
                "source": str(path),
            }
        )
    return workflows


def parse_services_file(
    path: Path,
    *,
    collection_id: str = "",
    repo: str = "",
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        return []
    except yaml.YAMLError as exc:
        warnings.warn(
            f"Ignoring malformed Bruno services file {path}: {exc}", stacklevel=2
        )
        return []
    items = _service_items(raw)
    services: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        service_id = str(item.get("id") or item.get("name") or "").strip()
        if not service_id:
            continue
        services.append(
            {
                "id": service_id,
                "collection": str(item.get("collection") or collection_id),
                "env": str(item.get("env") or "").strip(),
                "description": str(item.get("description") or ""),
                "repo": str(item.get("repo") or repo),
            }
        )
    return services


def resolve_bruno_repos(catalog: Catalog, settings: BrunoSettings | None = None) -> list[Repo]:
    settings = settings or catalog.bruno
    selected: list[Repo] = []
    seen: set[str] = set()
    if settings.repos:
        unknown = [name for name in settings.repos if name not in {repo.name for repo in catalog.repos}]
        if unknown:
            raise GoatError(
                "Unknown bruno.repos name(s): "
                + ", ".join(unknown)
                + ". Add them to repositories.yml."
            )
        for name in settings.repos:
            repo = catalog.repo(name)
            if repo.name not in seen:
                selected.append(repo)
                seen.add(repo.name)
    for repo in catalog.repos_with_tags(settings.tags):
        if repo.name not in seen:
            selected.append(repo)
            seen.add(repo.name)
    return [repo for repo in selected if repo.enabled]


def _discover(
    catalog: Catalog, goat_root: Path, settings: BrunoSettings
) -> dict[str, Any]:
    bru = bru_cli_status()
    repos_payload: list[dict[str, Any]] = []
    collections: list[BrunoCollection] = []
    missing: list[dict[str, Any]] = []
    wanted = resolve_bruno_repos(catalog, settings)
    for repo in wanted:
        path = catalog.repo_path(goat_root, repo)
        cloned = path.is_dir()
        found: list[BrunoCollection] = []
        if cloned:
            found = _scan_repo(repo, path, settings)
            collections.extend(found)
        else:
            missing.append({"id": repo.name, "path": str(path)})
        repos_payload.append(
            {
                "name": repo.name,
                "path": str(path),
                "cloned": cloned,
                "placeholder": repo.is_placeholder,
                "collections": [item.id for item in found],
            }
        )
    _uniquify_collection_ids(collections)
    for collection in collections:
        for request in collection.requests:
            request["collection"] = collection.id
            request["id"] = f"{collection.id}/{Path(request['path']).with_suffix('').as_posix()}"
        for env in collection.environments:
            env["collection"] = collection.id
    services = _merge_services(settings, collections)
    workflows = _all_workflows(collections)
    clone_command = (
        "goat clone --only " + ",".join(item["id"] for item in missing)
        if missing
        else None
    )
    if not wanted:
        note_missing = [
            {
                "id": "(none)",
                "path": (
                    "No Bruno repo is configured. Tag a repositories.yml "
                    f"entry with {', '.join(settings.tags) or 'bruno'} "
                    "or set catalog/stack.yaml bruno.repos."
                ),
            }
        ]
        # Keep this as a hint, not a missing clone.
        hint = note_missing[0]["path"]
    else:
        hint = None
        note_missing = missing
    return {
        "bru_cli": bru,
        "repos": repos_payload,
        "collections": collections,
        "services": services,
        "workflows": workflows,
        "missing_repos": note_missing if wanted else [],
        "clone_command": clone_command,
        "configure_hint": hint,
    }


def _scan_repo(repo: Repo, root: Path, settings: BrunoSettings) -> list[BrunoCollection]:
    collections: list[BrunoCollection] = []
    for bruno_json in _walk_bruno_json(root):
        collection = _load_collection(repo, root, bruno_json.parent, settings)
        if collection is not None:
            collections.append(collection)
    repo_workflows = parse_workflow_file(
        _overlay_file(root, settings.workflows_file, LEGACY_WORKFLOWS_FILE),
        repo=repo.name,
    )
    repo_services = parse_services_file(
        _overlay_file(root, settings.services_file, LEGACY_SERVICES_FILE),
        repo=repo.name,
    )
    if repo_workflows or repo_services:
        if collections:
            for collection in collections:
                if repo_workflows and not collection.workflows:
                    collection.workflows = [
                        item
                        if item.get("collection")
                        else {**item, "collection": collection.id}
                        for item in repo_workflows
                    ]
                if repo_services and not collection.services:
                    collection.services = [
                        item
                        if item.get("collection")
                        else {**item, "collection": collection.id}
                        for item in repo_services
                    ]
        elif repo_workflows or repo_services:
            # Workflows/services at repo root with no bruno.json yet.
            collections.append(
                BrunoCollection(
                    id=repo.name,
                    name=repo.name,
                    repo=repo.name,
                    path=root,
                    relpath=".",
                    services=repo_services,
                    workflows=repo_workflows,
                )
            )
    return collections


def _load_collection(
    repo: Repo, repo_root: Path, collection_root: Path, settings: BrunoSettings
) -> BrunoCollection | None:
    manifest = collection_root / "bruno.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except OSError:
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        warnings.warn(
            f"Ignoring malformed Bruno manifest {manifest}: {exc}", stacklevel=2
        )
        return None
    if not isinstance(data, dict):
        return None
    name = str(data.get("name") or collection_root.name)
    relpath = collection_root.relative_to(repo_root).as_posix()
    # A nested bruno.json marks its own collection; do not fold its requests
    # into this parent collection (which would double-count and mis-attribute).
    nested_roots = [
        manifest_path.parent
        for manifest_path in _walk_bruno_json(collection_root)
        if manifest_path.parent != collection_root
    ]
    requests: list[dict[str, Any]] = []
    folders: list[str] = []
    for bru_file in _walk_bru_files(collection_root):
        if bru_file.parent.name == "environments":
            continue
        if any(bru_file.is_relative_to(nested) for nested in nested_roots):
            continue
        parsed = parse_bru_request(bru_file, collection_root)
        if parsed is None:
            meta_type = _file_meta_type(bru_file)
            if meta_type == "folder":
                folder = bru_file.parent.relative_to(collection_root).as_posix()
                if folder != ".":
                    folders.append(folder)
            continue
        requests.append(parsed)
    environments = []
    env_dir = collection_root / "environments"
    if env_dir.is_dir():
        for env_file in sorted(env_dir.glob("*.bru")):
            env = parse_bru_environment(env_file)
            environments.append(env)
    collection_id = name
    workflows = parse_workflow_file(
        _overlay_file(collection_root, settings.workflows_file, LEGACY_WORKFLOWS_FILE),
        collection_id=collection_id,
        repo=repo.name,
    )
    services = parse_services_file(
        _overlay_file(collection_root, settings.services_file, LEGACY_SERVICES_FILE),
        collection_id=collection_id,
        repo=repo.name,
    )
    return BrunoCollection(
        id=collection_id,
        name=name,
        repo=repo.name,
        path=collection_root,
        relpath=relpath,
        requests=sorted(requests, key=lambda item: (item.get("seq") is None, item.get("seq") or 0, item["path"])),
        environments=environments,
        folders=_unique(folders),
        services=services,
        workflows=workflows,
    )


def _walk_bruno_json(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        if "bruno.json" in filenames:
            found.append(Path(dirpath) / "bruno.json")
    return sorted(found)


def _walk_bru_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        for name in filenames:
            if name.endswith(".bru"):
                found.append(Path(dirpath) / name)
    return sorted(found)


def _file_meta_type(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    blocks = dict(parse_bru_blocks(text))
    return (_parse_meta(blocks.get("meta", "")).get("type") or "").lower()


def _uniquify_collection_ids(collections: list[BrunoCollection]) -> None:
    counts: dict[str, int] = {}
    for collection in collections:
        counts[collection.id] = counts.get(collection.id, 0) + 1
    for collection in collections:
        if counts.get(collection.id, 0) > 1:
            suffix = collection.relpath if collection.relpath not in {".", ""} else collection.repo
            collection.id = f"{collection.repo}/{suffix}"


def _collection_summary(collection: BrunoCollection) -> dict[str, Any]:
    return {
        "id": collection.id,
        "name": collection.name,
        "repo": collection.repo,
        "path": str(collection.path),
        "relpath": collection.relpath,
        "request_count": len(collection.requests),
        "environments": [item["name"] for item in collection.environments],
        "folders": list(collection.folders),
    }


def _workflow_summary(workflow: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": workflow.get("id"),
        "description": workflow.get("description"),
        "env": workflow.get("env"),
        "service": workflow.get("service"),
        "collection": workflow.get("collection"),
        "repo": workflow.get("repo"),
        "steps": [
            {
                "id": step.get("id"),
                "request": step.get("request"),
                "needs": list(step.get("needs") or []),
            }
            for step in (workflow.get("steps") or [])
        ],
    }


def _workflow_plan(
    workflow: Mapping[str, Any],
    collections: list[BrunoCollection],
    settings: BrunoSettings,
) -> dict[str, Any]:
    env = workflow.get("env") or settings.default_env
    steps = []
    for step in workflow.get("steps") or []:
        step_env = step.get("env") or env
        request_target = str(step.get("request") or "")
        bru_command = ["bru", "run", request_target]
        if step_env:
            bru_command.extend(["--env", str(step_env)])
        for key in (step.get("env_vars") or {}):
            bru_command.extend(["--env-var", f"{key}=<from-previous-step>"])
        owner = None
        if workflow.get("collection"):
            owner = _optional_collection(collections, str(workflow["collection"]))
        resolved = None
        if request_target:
            try:
                resolved = _require_request(
                    [owner] if owner else collections, request_target
                )
            except GoatError:
                resolved = None
        if resolved:
            bru_command[2] = resolved["path"]
        steps.append(
            {
                "id": step.get("id"),
                "request": request_target,
                "pick": dict(step.get("pick") or {}),
                "needs": list(step.get("needs") or []),
                "env_vars": {
                    key: "<redacted>" if _looks_secret(key) else str(value)
                    for key, value in (step.get("env_vars") or {}).items()
                },
                "env": step_env,
                "bru_command": bru_command,
            }
        )
    return {
        "id": workflow.get("id"),
        "description": workflow.get("description"),
        "env": env,
        "service": workflow.get("service"),
        "collection": workflow.get("collection"),
        "repo": workflow.get("repo"),
        "steps": steps,
    }


def _all_requests(collections: list[BrunoCollection]) -> list[dict[str, Any]]:
    return [item for collection in collections for item in collection.requests]


def _all_workflows(collections: list[BrunoCollection]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    workflows: list[dict[str, Any]] = []
    for collection in collections:
        for item in collection.workflows:
            key = f"{item.get('repo')}:{item.get('id')}:{item.get('collection')}"
            if key in seen:
                continue
            seen.add(key)
            workflows.append(item)
    return workflows


def _merge_services(
    settings: BrunoSettings, collections: list[BrunoCollection]
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for collection in collections:
        for item in collection.services:
            by_id[item["id"]] = dict(item)
    for item in settings.services:
        row = item.as_dict()
        existing = by_id.get(row["id"], {})
        by_id[row["id"]] = {**existing, **{k: v for k, v in row.items() if v}}
    if not by_id:
        for collection in collections:
            default_env = ""
            if collection.environments:
                names = [env["name"] for env in collection.environments]
                default_env = (
                    settings.default_env
                    if settings.default_env in names
                    else names[0]
                )
            by_id[collection.id] = {
                "id": collection.id,
                "collection": collection.id,
                "env": default_env or settings.default_env or DEFAULT_ENV,
                "description": collection.name,
                "repo": collection.repo,
            }
    return list(by_id.values())


def _optional_collection(
    collections: list[BrunoCollection], target: str
) -> BrunoCollection | None:
    needle = target.strip()
    matches = [
        item
        for item in collections
        if item.id == needle
        or item.name == needle
        or item.relpath == needle
        or item.relpath.rstrip("/") == needle.rstrip("/")
        or item.path.name == needle
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _require_collection(
    collections: list[BrunoCollection], target: str
) -> BrunoCollection:
    match = _optional_collection(collections, target)
    if match is None:
        known = ", ".join(item.id for item in collections) or "(none)"
        raise GoatError(
            f"Unknown Bruno collection {target!r}. Known: {known}"
        )
    return match


def _collection_by_id(
    collections: list[BrunoCollection], collection_id: str
) -> BrunoCollection | None:
    for item in collections:
        if item.id == collection_id:
            return item
    return None


def _require_service(services: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [item for item in services if item["id"] == name]
    if len(matches) != 1:
        known = ", ".join(item["id"] for item in services) or "(none)"
        raise GoatError(f"Unknown Bruno service {name!r}. Known: {known}")
    return matches[0]


def _collection_for_service(
    collections: list[BrunoCollection], service: Mapping[str, Any]
) -> BrunoCollection:
    target = str(service.get("collection") or service.get("id") or "")
    match = _optional_collection(collections, target)
    if match is None:
        raise GoatError(
            f"Service {service.get('id')!r} collection {target!r} was not found"
        )
    return match


def _service_matches_collection(
    service: Mapping[str, Any], collection: BrunoCollection
) -> bool:
    target = str(service.get("collection") or "")
    return (
        not target
        or target == collection.id
        or target == collection.name
        or service.get("id") == collection.id
    )


def _require_request(
    collections: list[BrunoCollection], target: str
) -> dict[str, Any]:
    needle = target.strip().replace("\\", "/")
    matches = [
        item for item in _all_requests(collections) if _request_matches(item, needle)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise GoatError(
            f"Unknown Bruno request {target!r}. "
            "Run `goat bruno requests` for ids and paths."
        )
    ids = ", ".join(item["id"] for item in matches)
    raise GoatError(
        f"Request {target!r} is ambiguous ({ids}). "
        "Pass a collection id or the relative .bru path."
    )


def _request_matches(request: Mapping[str, Any], target: str) -> bool:
    needle = target.strip().replace("\\", "/")
    path = str(request.get("path") or "")
    stem = Path(path).with_suffix("").as_posix()
    name = str(request.get("name") or "")
    request_id = str(request.get("id") or "")
    candidates = {
        path,
        stem,
        name,
        name.lower(),
        request_id,
        Path(path).name,
        Path(path).stem,
    }
    if needle in candidates or needle.lower() == name.lower():
        return True
    if needle.endswith(".bru") and path.endswith(needle):
        return True
    if path.endswith(f"{needle}.bru") or stem.endswith(needle):
        return True
    return False


def _resolve_env(
    settings: BrunoSettings,
    collection: BrunoCollection,
    explicit: str | None,
    services: list[dict[str, Any]],
) -> str:
    if explicit:
        return explicit
    for service in services:
        if _service_matches_collection(service, collection) and service.get("env"):
            return str(service["env"])
    names = [item["name"] for item in collection.environments]
    if settings.default_env and settings.default_env in names:
        return settings.default_env
    if names:
        return names[0]
    return settings.default_env or DEFAULT_ENV


def _bru_command(
    relpath: str,
    env: str | None,
    pairs: list[tuple[str, str]],
    *,
    redact: bool,
) -> list[str]:
    command = ["bru", "run", relpath]
    if env:
        command.extend(["--env", env])
    for key, value in pairs:
        shown = "<redacted>" if redact else value
        command.extend(["--env-var", f"{key}={shown}"])
    return command


def _matching_close(text: str, start: int, opener: str, closer: str) -> int:
    depth = 0
    in_string: str | None = None
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            continue
        # Only double quotes delimit strings (they guard braces inside JSON
        # bodies). Apostrophes in prose (e.g. `docs { don't }`) must NOT start a
        # string, or the closing brace would be swallowed and every later block
        # silently dropped.
        if char == '"':
            in_string = char
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _parse_meta(body: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in body.splitlines():
        match = _META_LINE.match(line.strip())
        if match:
            meta[match.group(1)] = match.group(2).strip()
    return meta


def _meta_value(body: str, key: str) -> str:
    prefix = f"{key}:"
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return ""


def _block_keys(body: str) -> list[str]:
    keys: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        match = _META_LINE.match(stripped)
        if match:
            keys.append(match.group(1))
    return keys


def _secret_names(body: str) -> list[str]:
    names: list[str] = []
    for raw in re.split(r"[\n,]", body):
        token = raw.strip().strip("[]")
        if not token or token.startswith("//"):
            continue
        match = _META_LINE.match(token)
        names.append(match.group(1) if match else token)
    return [item for item in names if item]


def _workflow_items(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if isinstance(raw.get("workflows"), list):
            return raw["workflows"]
        if raw.get("id") or raw.get("name"):
            return [raw]
    return []


def _service_items(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if isinstance(raw.get("services"), list):
            return raw["services"]
        if raw.get("id") or raw.get("name"):
            return [raw]
        # mapping form: cart: { env: staging }
        items = []
        for key, value in raw.items():
            if key == "services":
                continue
            if isinstance(value, dict):
                items.append({"id": key, **value})
        return items
    return []


def _unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _clip(text: str, limit: int) -> str:
    text = text.replace("\x00", "")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _looks_secret(key: str) -> bool:
    lowered = key.lower()
    return any(
        token in lowered
        for token in ("secret", "token", "password", "passwd", "api_key", "apikey")
    )

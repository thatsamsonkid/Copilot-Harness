from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import yaml

from goat import GoatError
from goat.catalog import (
    Catalog,
    Repo,
    load_catalog,
    refuse_local_clone_in_goat,
    resolve_local_clone_path,
)
from goat.gitinfo import list_remotes
from goat.paths import REPOS_LOCAL_RELATIVE
from goat.workspace import generate_workspaces

STATUS_EXPECTED = "expected"
STATUS_MAPPED = "mapped"
STATUS_REMAP = "remap"
STATUS_MISSING = "missing"
STATUS_CONFLICT = "conflict"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_NAME_ONLY = "name_only"
STATUS_PINNED = "pinned"

WRITEABLE = frozenset({STATUS_REMAP, STATUS_PINNED})

_SET_PAIR = re.compile(r"^([^=]+)=(.*)$")
_OVERLAY_HEADER = (
    "# Local clone locations. Do not commit.\n"
    "# Names must match repositories.yml.\n"
    "# Paths may be absolute, ~, or relative to this goat.\n"
)


def normalize_git_url(url: str) -> str:
    """Collapse SSH/HTTPS/.git variants so catalog remotes match existing clones."""
    text = (url or "").strip()
    if not text:
        return ""
    if text.startswith("git@") and ":" in text.split("@", 1)[-1]:
        host, path = text.split(":", 1)
        host = host.removeprefix("git@")
        return _canonical_host_path(host, path)
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https", "ssh", "git"}:
        host = parsed.hostname or ""
        path = parsed.path
        return _canonical_host_path(host, path)
    if parsed.scheme == "file":
        text = parsed.path or text
    return _canonical_local_path(text)


def parse_set_paths(values: list[str] | None) -> dict[str, str]:
    pins: dict[str, str] = {}
    for item in values or []:
        match = _SET_PAIR.match(item.strip())
        if not match or not match.group(1).strip() or not match.group(2).strip():
            raise GoatError(
                f"Invalid --set {item!r}. Use NAME=PATH (example: frontend=~/code/shop-web)."
            )
        pins[match.group(1).strip()] = match.group(2).strip()
    return pins


def format_overlay_path(goat_root: Path, path: Path) -> str:
    resolved = path.expanduser().resolve()
    goat = goat_root.resolve()
    relative = Path(os.path.relpath(resolved, goat))
    if ".." not in relative.parts or len(relative.parts) <= 6:
        return relative.as_posix()
    home = Path.home().resolve()
    try:
        return "~/" + resolved.relative_to(home).as_posix()
    except ValueError:
        return resolved.as_posix()


def map_clones(
    catalog: Catalog,
    goat_root: Path,
    *,
    extra_search: list[str] | None = None,
    only: list[str] | None = None,
    pins: dict[str, str] | None = None,
    run: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    goat_root = Path(goat_root)
    selected = catalog.enabled_repos(only)
    discovered = discover_git_clones(
        catalog,
        goat_root,
        extra_search=extra_search,
        run=run,
    )
    by_url: dict[str, list[dict[str, Any]]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for clone in discovered:
        for key in clone["keys"]:
            if key:
                by_url.setdefault(key, []).append(clone)
        by_name.setdefault(clone["name"], []).append(clone)

    pins = pins or {}
    unknown = sorted(set(pins).difference(repo.name for repo in catalog.repos))
    if unknown:
        raise GoatError(
            "Unknown repo name(s) in --set: " + ", ".join(unknown)
        )

    rows: list[dict[str, Any]] = []
    matched_paths: set[str] = set()
    for repo in selected:
        row = _classify_repo(
            catalog,
            goat_root,
            repo,
            by_url=by_url,
            by_name=by_name,
            pin=pins.get(repo.name),
            run=run,
        )
        rows.append(row)
        if row.get("found"):
            matched_paths.add(str(Path(row["found"]).resolve()))

    unmatched = [
        {
            "path": clone["path"],
            "name": clone["name"],
            "remotes": clone["remotes"],
        }
        for clone in discovered
        if str(Path(clone["path"]).resolve()) not in matched_paths
    ]
    remaps = [row["id"] for row in rows if row["status"] == STATUS_REMAP]
    missing = [row["id"] for row in rows if row["status"] == STATUS_MISSING]
    conflicts = [row["id"] for row in rows if row["status"] == STATUS_CONFLICT]
    ambiguous = [row["id"] for row in rows if row["status"] == STATUS_AMBIGUOUS]
    writable = [row["id"] for row in rows if row["status"] in WRITEABLE]
    return {
        "kind": "workspace_map",
        "goat_root": str(goat_root),
        "sibling_root": str(catalog.sibling_root(goat_root)),
        "overlay": str(goat_root / REPOS_LOCAL_RELATIVE),
        "overlay_exists": (goat_root / REPOS_LOCAL_RELATIVE).exists(),
        "search": _search_roots_for_report(catalog, goat_root, extra_search),
        "repos": rows,
        "unmatched": unmatched,
        "remap": remaps,
        "missing": missing,
        "conflicts": conflicts,
        "ambiguous": ambiguous,
        "writable": writable,
        "hint": _hint(remaps, missing, writable),
    }


def apply_workspace_map(
    catalog: Catalog,
    goat_root: Path,
    *,
    extra_search: list[str] | None = None,
    only: list[str] | None = None,
    pins: dict[str, str] | None = None,
    write: bool = False,
    generate: bool = False,
    dry_run: bool = False,
    run: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    payload = map_clones(
        catalog,
        goat_root,
        extra_search=extra_search,
        only=only,
        pins=pins,
        run=run,
    )
    payload["wrote"] = False
    payload["generated"] = []
    if dry_run:
        payload["dry_run"] = True
        return payload

    overlay_path = goat_root / REPOS_LOCAL_RELATIVE
    if write:
        updates = {
            row["id"]: row["found"]
            for row in payload["repos"]
            if row["status"] in WRITEABLE and row.get("found")
        }
        if updates or catalog.local_paths:
            written = write_local_overlay(
                overlay_path,
                goat_root,
                catalog,
                updates,
                extra_search=extra_search,
                only=only,
            )
            payload["wrote"] = written["changed"]
            payload["overlay"] = written["file"]
            catalog = load_catalog(
                goat_root,
                stack_path=catalog.source,
                repos_path=catalog.repos_source,
                templates_path=catalog.templates_source,
            )
            payload["overlay_exists"] = True
            for row in payload["repos"]:
                if row["id"] in catalog.local_paths:
                    row["mapped"] = True
                    row["resolved"] = str(catalog.repo_path(goat_root, row["id"]))

    if generate:
        payload["generated"] = generate_workspaces(catalog, goat_root)
        payload["hint"] = (
            "Wrote workspaces/*.code-workspace from catalog/stack.yaml. "
            "Do not commit those files or repositories.local.yml."
        )
    elif write and payload.get("wrote"):
        payload["hint"] = (
            "Pinned clones in repositories.local.yml. "
            "Run `goat workspace generate` (or rerun with --generate)."
        )
    return payload


def write_local_overlay(
    path: Path,
    goat_root: Path,
    catalog: Catalog,
    updates: dict[str, str],
    *,
    extra_search: list[str] | None = None,
    only: list[str] | None = None,
) -> dict[str, Any]:
    paths = dict(catalog.local_paths)
    for name, dest in updates.items():
        paths[name] = _store_path(goat_root, dest)
    if not only:
        for name in list(paths):
            if name in updates:
                continue
            repo = catalog.repo(name)
            expected = catalog.expected_repo_path(goat_root, repo)
            current = resolve_local_clone_path(goat_root, paths[name])
            if current == expected.resolve():
                paths.pop(name)

    search = _merge_search(catalog.local_search, extra_search)
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if not paths and not search:
        if path.exists():
            path.unlink()
            return {"file": str(path), "changed": True, "paths": {}, "search": []}
        return {"file": str(path), "changed": False, "paths": {}, "search": []}

    ordered = {name: paths[name] for name in sorted(paths)}
    data: dict[str, Any] = {"paths": ordered}
    if search:
        data["search"] = search
    text = _OVERLAY_HEADER + yaml.safe_dump(data, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    return {
        "file": str(path),
        "changed": previous != text,
        "paths": ordered,
        "search": search,
    }


def discover_git_clones(
    catalog: Catalog,
    goat_root: Path,
    *,
    extra_search: list[str] | None = None,
    run: Callable[..., Any] | None = None,
) -> list[dict[str, Any]]:
    roots = _search_root_paths(catalog, goat_root, extra_search)
    goat = goat_root.resolve()
    found: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in _iter_git_clones(root, goat, depth=2):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            remotes = list_remotes(path, run=run)
            found.append(
                {
                    "path": str(resolved),
                    "name": path.name,
                    "remotes": remotes,
                    "keys": [normalize_git_url(url) for url in remotes],
                }
            )
    return found


def discover_remap_hints(
    catalog: Catalog,
    goat_root: Path,
    *,
    run: Callable[..., Any] | None = None,
) -> dict[str, str]:
    """Sibling-only URL matches for doctor/init when a catalog dest is empty."""
    payload = map_clones(catalog, goat_root, run=run)
    return {
        row["id"]: row["found"]
        for row in payload["repos"]
        if row["status"] == STATUS_REMAP and row.get("found")
    }


def _classify_repo(
    catalog: Catalog,
    goat_root: Path,
    repo: Repo,
    *,
    by_url: dict[str, list[dict[str, Any]]],
    by_name: dict[str, list[dict[str, Any]]],
    pin: str | None,
    run: Callable[..., Any] | None,
) -> dict[str, Any]:
    expected = catalog.expected_repo_path(goat_root, repo)
    resolved = catalog.repo_path(goat_root, repo)
    catalog_key = normalize_git_url(repo.url)
    url_matches = list(by_url.get(catalog_key, [])) if catalog_key else []
    row: dict[str, Any] = {
        "id": repo.name,
        "url": repo.url,
        "expected": str(expected),
        "resolved": str(resolved),
        "mapped": catalog.is_mapped(repo),
        "found": None,
        "remotes": [],
        "status": STATUS_MISSING,
        "detail": f"{expected} is not cloned",
    }

    if pin:
        target = resolve_local_clone_path(goat_root, pin)
        refuse_local_clone_in_goat(target, goat_root)
        remotes = list_remotes(target, run=run)
        keys = [normalize_git_url(url) for url in remotes]
        row["found"] = str(target)
        row["resolved"] = str(target)
        row["remotes"] = remotes
        row["mapped"] = True
        row["status"] = STATUS_PINNED
        if not target.exists():
            raise GoatError(f"--set {repo.name}={pin} does not exist")
        if not remotes and not (target / ".git").exists():
            raise GoatError(f"--set {repo.name}={pin} is not a git repo")
        if catalog_key and keys and catalog_key not in keys:
            row["status"] = STATUS_CONFLICT
            row["detail"] = (
                f"{target} remote does not match {repo.url}. "
                "Not writing this pin."
            )
            return row
        row["detail"] = f"pin {repo.name} to {target}"
        return row

    expected_remotes = list_remotes(expected, run=run)
    expected_keys = [normalize_git_url(url) for url in expected_remotes]
    if expected.exists() and (expected / ".git").exists():
        row["found"] = str(expected.resolve())
        row["remotes"] = expected_remotes
        if catalog_key and catalog_key in expected_keys:
            row["status"] = STATUS_MAPPED if catalog.is_mapped(repo) else STATUS_EXPECTED
            row["detail"] = (
                f"{expected} matches {repo.url}"
                if row["status"] == STATUS_EXPECTED
                else f"{expected} is pinned and matches {repo.url}"
            )
            return row
        if expected_keys:
            row["status"] = STATUS_CONFLICT
            row["detail"] = (
                f"{expected} exists but remotes {expected_remotes} "
                f"do not match {repo.url}"
            )
            return row

    if catalog.is_mapped(repo):
        remotes = list_remotes(resolved, run=run)
        keys = [normalize_git_url(url) for url in remotes]
        row["found"] = str(resolved) if resolved.exists() else None
        row["remotes"] = remotes
        if resolved.exists() and (resolved / ".git").exists():
            if catalog_key and keys and catalog_key not in keys:
                row["status"] = STATUS_CONFLICT
                row["detail"] = (
                    f"overlay {resolved} remotes {remotes} do not match {repo.url}"
                )
                return row
            row["status"] = STATUS_MAPPED
            row["detail"] = f"overlay maps {repo.name} to {resolved}"
            return row
        row["status"] = STATUS_MAPPED
        row["detail"] = f"overlay maps {repo.name} to {resolved} (path missing)"
        return row

    elsewhere = [
        clone
        for clone in url_matches
        if Path(clone["path"]).resolve() != expected.resolve()
    ]
    if len(elsewhere) == 1:
        clone = elsewhere[0]
        row["found"] = clone["path"]
        row["remotes"] = clone["remotes"]
        row["status"] = STATUS_REMAP
        row["detail"] = f"found {repo.url} at {clone['path']}"
        return row
    if len(elsewhere) > 1:
        row["status"] = STATUS_AMBIGUOUS
        row["found"] = None
        row["matches"] = [clone["path"] for clone in elsewhere]
        row["detail"] = (
            f"multiple clones match {repo.url}: "
            + ", ".join(clone["path"] for clone in elsewhere)
        )
        return row

    name_hits = [
        clone
        for clone in by_name.get(repo.name, [])
        if Path(clone["path"]).resolve() != expected.resolve()
    ]
    if name_hits:
        row["status"] = STATUS_NAME_ONLY
        row["matches"] = [clone["path"] for clone in name_hits]
        row["detail"] = (
            f"folder name {repo.name} found at {name_hits[0]['path']} "
            "but remotes do not match; not auto-mapping"
        )
        return row

    row["status"] = STATUS_MISSING
    row["detail"] = f"{expected} is not cloned"
    return row


def _iter_git_clones(root: Path, goat: Path, *, depth: int) -> list[Path]:
    found: list[Path] = []
    try:
        children = sorted(root.iterdir())
    except OSError:
        return found
    for child in children:
        if not child.is_dir() or child.name.startswith("."):
            continue
        try:
            resolved = child.resolve()
        except OSError:
            continue
        if resolved == goat or goat in resolved.parents:
            continue
        if (child / ".git").exists():
            found.append(child)
            continue
        if depth > 1:
            found.extend(_iter_git_clones(child, goat, depth=depth - 1))
    return found


def _search_root_paths(
    catalog: Catalog,
    goat_root: Path,
    extra_search: list[str] | None,
) -> list[Path]:
    roots: list[Path] = [catalog.sibling_root(goat_root)]
    for raw in [*catalog.local_search, *(extra_search or [])]:
        path = resolve_local_clone_path(goat_root, raw)
        if path not in roots:
            roots.append(path)
    return roots


def _search_roots_for_report(
    catalog: Catalog, goat_root: Path, extra_search: list[str] | None
) -> list[str]:
    return [str(path) for path in _search_root_paths(catalog, goat_root, extra_search)]


def _merge_search(existing: list[str], extra: list[str] | None) -> list[str]:
    merged: list[str] = []
    for item in [*existing, *(extra or [])]:
        text = str(item).strip()
        if text and text not in merged:
            merged.append(text)
    return merged


def _store_path(goat_root: Path, raw: str) -> str:
    return format_overlay_path(goat_root, resolve_local_clone_path(goat_root, raw))


def _canonical_host_path(host: str, path: str) -> str:
    host = (host or "").lower().strip()
    path = (path or "").strip().strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    path = path.strip("/").lower()
    if not host:
        return path
    return f"{host}/{path}"


def _canonical_local_path(url: str) -> str:
    text = url.strip()
    if text.endswith(".git"):
        text = text[: -len(".git")]
    path = Path(text).expanduser()
    try:
        return str(path.resolve()).lower()
    except OSError:
        return text.lower()


def _hint(remaps: list[str], missing: list[str], writable: list[str]) -> str:
    parts: list[str] = []
    if remaps or writable:
        parts.append(
            "Run `goat workspace map --write --generate` to pin existing clones "
            "in repositories.local.yml and rewrite workspaces/*.code-workspace."
        )
    if missing:
        parts.append(
            "Clone the rest with `goat clone` "
            "(or `goat clone --only " + ",".join(missing) + "`)."
        )
    if not parts:
        parts.append(
            "Catalog dests already match, or pin a path with "
            "`goat workspace map --set name=/path --write --generate`."
        )
    return " ".join(parts)

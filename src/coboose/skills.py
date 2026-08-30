"""Discover sibling skills and copy them into the Coboose workspace root.

VS Code Agents does not scan multi-root child folders. This is a temporary
shim: list skills in this coboose and cloned siblings, then lift selected
ones (or pull a remote skills git repo) into ``.github/skills`` on the first
workspace folder so the Agents window can load them.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from coboose import CobooseError
from coboose.catalog import Catalog, Repo
from coboose.clone import rewrite_clone_url
from coboose.prompt import PromptSession
from coboose.workspace_detect import resolve_workspace_scope, scoped_repos

COBOOSE_SOURCE_ID = "coboose"
DEST_RELATIVE = Path(".github") / "skills"
SOURCE_MARKER = ".coboose-source.json"
MANIFEST_RELATIVE = Path(".coboose") / "skills-install.json"
IGNORE_BEGIN = "# begin coboose-skills-install"
IGNORE_END = "# end coboose-skills-install"
SKILL_FILENAMES = ("SKILL.md", "skill.md")
SKILL_DIR_NAMES = (
    ".github/skills",
    ".agents/skills",
    ".cursor/skills",
    ".claude/skills",
    "skills",
)
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
}
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

RunFn = Callable[..., Any]


def skills_dest(coboose_root: Path, catalog: Catalog, *, parent: bool = False) -> Path:
    if parent:
        return catalog.require_safe_sibling_root(coboose_root) / DEST_RELATIVE
    return coboose_root.resolve() / DEST_RELATIVE


def list_skills(
    catalog: Catalog,
    coboose_root: Path,
    *,
    only: list[str] | None = None,
    workspace_id: str | None = None,
    all_repos: bool = False,
    parent: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    dest = skills_dest(coboose_root, catalog, parent=parent)
    scope = resolve_workspace_scope(
        catalog,
        coboose_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    sources = _collect_sources(
        catalog,
        coboose_root,
        dest,
        only=only,
        scope=scope,
        include_top_level=False,
    )
    installed = _installed_skills(dest)
    available = _flatten_available(sources)
    return {
        "dest": str(dest),
        "dest_kind": "parent" if parent else "workspace",
        "workspace": scope.id,
        "workspace_scope": scope.as_payload(),
        "sources": sources,
        "available": available,
        "installed": installed,
        "guidance": _guidance(parent=parent),
        "next_commands": [
            "uv run coboose skills lift",
            "uv run coboose skills lift --only <name,name>",
            "uv run coboose skills pull <git-url>",
        ],
    }


def lift_skills(
    catalog: Catalog,
    coboose_root: Path,
    *,
    only: list[str] | None = None,
    names: list[str] | None = None,
    workspace_id: str | None = None,
    all_repos: bool = False,
    parent: bool = False,
    force: bool = False,
    dry_run: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    payload = list_skills(
        catalog,
        coboose_root,
        only=only,
        workspace_id=workspace_id,
        all_repos=all_repos,
        parent=parent,
        environ=environ,
    )
    dest = Path(payload["dest"])
    selected = _select_available(payload["available"], names)
    results = _install_records(
        dest,
        coboose_root,
        selected,
        parent=parent,
        force=force,
        dry_run=dry_run,
    )
    if not dry_run and (results["copied"] or results["updated"]):
        _write_manifest(coboose_root, dest, results)
        _ignore_installed(coboose_root, dest, results)
    payload.update(results)
    payload["dry_run"] = dry_run
    payload["ok"] = not results["conflicts"]
    return payload


def sync_root_skills(
    catalog: Catalog,
    coboose_root: Path,
    *,
    only: list[str] | None = None,
    workspace_id: str | None = None,
    all_repos: bool = False,
    parent: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Lift coboose + scoped sibling skills. Never raises for init/prepare."""
    try:
        return lift_skills(
            catalog,
            coboose_root,
            only=only,
            workspace_id=workspace_id,
            all_repos=all_repos,
            parent=parent,
            environ=environ,
        )
    except (CobooseError, OSError) as exc:
        return {
            "ok": False,
            "error": str(exc),
            "dest": str(skills_dest(coboose_root, catalog, parent=parent)),
            "dest_kind": "parent" if parent else "workspace",
            "copied": [],
            "updated": [],
            "skipped": [],
            "conflicts": [],
            "native": [],
            "installed": [],
            "available": [],
        }


def pull_skills(
    catalog: Catalog,
    coboose_root: Path,
    url: str,
    *,
    ref: str | None = None,
    names: list[str] | None = None,
    all_skills: bool = False,
    parent: bool = False,
    force: bool = False,
    dry_run: bool = False,
    https: bool = False,
    prompt: PromptSession | None = None,
    run: RunFn | None = None,
) -> dict[str, Any]:
    url = rewrite_clone_url(url.strip(), https=https)
    if not url:
        raise CobooseError("Pass a git URL for coboose skills pull")
    if "your_org" in url.lower() or "example.com" in url.lower():
        raise CobooseError("Refusing to clone a placeholder skills URL")

    dest = skills_dest(coboose_root, catalog, parent=parent)
    prompt = prompt or PromptSession()
    with tempfile.TemporaryDirectory(prefix="coboose-skills-") as tmp:
        clone_dir = Path(tmp) / "repo"
        if dry_run:
            available: list[dict[str, Any]] = []
            clone_action = "clone"
        else:
            _clone_skills_repo(url, clone_dir, ref=ref, run=run)
            available = discover_skills_in_tree(
                clone_dir,
                source_id=_remote_source_id(url),
                source_kind="remote",
                include_top_level=True,
            )
            clone_action = "cloned"

        payload: dict[str, Any] = {
            "url": url,
            "ref": ref,
            "dest": str(dest),
            "dest_kind": "parent" if parent else "workspace",
            "clone": clone_action,
            "available": available,
            "needs_selection": False,
            "dry_run": dry_run,
            "guidance": _guidance(parent=parent),
        }
        if dry_run:
            payload["needs_selection"] = not (names or all_skills)
            payload["install_command"] = _pull_install_command(url, ref, names)
            payload.update(_empty_results())
            payload["ok"] = True
            return payload

        selected_names = names
        if all_skills:
            selected_names = None
        elif not selected_names:
            if prompt.can_prompt():
                selected_names = _prompt_skill_names(prompt, available)
            else:
                payload["needs_selection"] = True
                payload["install_command"] = _pull_install_command(url, ref, None)
                payload["detail"] = (
                    "Pick skills from available[], then rerun with --only "
                    "name,name or --all"
                )
                payload.update(_empty_results())
                payload["ok"] = True
                return payload

        selected = _select_available(available, selected_names)
        if not selected:
            raise CobooseError(
                "No matching skills in that repository. "
                "Run coboose skills pull without --only to list them."
            )
        results = _install_records(
            dest,
            coboose_root,
            selected,
            parent=parent,
            force=force,
            dry_run=False,
        )
        _write_manifest(coboose_root, dest, results)
        _ignore_installed(coboose_root, dest, results)
        payload.update(results)
        payload["ok"] = not results["conflicts"]
        return payload


def discover_skills_in_tree(
    root: Path,
    *,
    source_id: str,
    source_kind: str,
    include_top_level: bool = False,
) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    search_dirs = [root / relative for relative in SKILL_DIR_NAMES]
    if include_top_level:
        search_dirs.append(root)
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for child in sorted(directory.iterdir()):
            record = _skill_from_dir(
                child,
                source_id=source_id,
                source_kind=source_kind,
                root=root,
            )
            if record is None:
                continue
            key = str(Path(record["path"]).resolve())
            if key in seen:
                continue
            seen.add(key)
            found.append(record)
    return found


def parse_skill_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta: dict[str, Any] = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            raw = parts[1]
            try:
                import yaml

                loaded = yaml.safe_load(raw)
            except Exception:  # noqa: BLE001 - skill files may have loose YAML
                loaded = None
            if isinstance(loaded, dict):
                meta = loaded
    return {
        "name": str(meta["name"]).strip() if meta.get("name") else path.parent.name,
        "description": str(meta.get("description") or "").strip(),
        "argument_hint": str(
            meta.get("argument-hint") or meta.get("argument_hint") or ""
        ).strip(),
    }


def _collect_sources(
    catalog: Catalog,
    coboose_root: Path,
    dest: Path,
    *,
    only: list[str] | None,
    scope: Any,
    include_top_level: bool,
) -> list[dict[str, Any]]:
    sources = [
        _source_payload(
            COBOOSE_SOURCE_ID,
            "coboose",
            coboose_root.resolve(),
            cloned=True,
            include_top_level=include_top_level,
            skip_installed_at=dest,
        )
    ]
    for repo in scoped_repos(catalog, scope, only=only):
        path = catalog.repo_path(coboose_root, repo)
        sources.append(
            _source_payload(
                repo.name,
                "sibling",
                path,
                cloned=path.exists(),
                include_top_level=include_top_level,
                skip_installed_at=None,
                repo=repo,
            )
        )
    return sources


def _source_payload(
    source_id: str,
    kind: str,
    path: Path,
    *,
    cloned: bool,
    include_top_level: bool,
    skip_installed_at: Path | None,
    repo: Repo | None = None,
) -> dict[str, Any]:
    skills = (
        discover_skills_in_tree(
            path,
            source_id=source_id,
            source_kind=kind,
            include_top_level=include_top_level,
        )
        if cloned
        else []
    )
    if skip_installed_at is not None:
        skills = [item for item in skills if not item.get("installed")]
    payload: dict[str, Any] = {
        "id": source_id,
        "kind": kind,
        "path": str(path),
        "cloned": cloned,
        "skills": skills,
    }
    if repo is not None:
        payload["relpath"] = repo.path
        payload["group"] = repo.group
    return payload


def _skill_from_dir(
    directory: Path,
    *,
    source_id: str,
    source_kind: str,
    root: Path,
) -> dict[str, Any] | None:
    if not directory.is_dir() or directory.name in SKIP_DIR_NAMES:
        return None
    skill_file = _skill_file(directory)
    if skill_file is None:
        return None
    if _is_installed_copy(directory):
        marker = _read_marker(directory)
        name = str(marker.get("installed_as") or directory.name)
        return {
            "name": name,
            "source_name": str(marker.get("name") or name),
            "description": str(marker.get("description") or ""),
            "path": str(directory),
            "file": str(skill_file),
            "source_id": str(marker.get("source_id") or source_id),
            "source_kind": str(marker.get("source_kind") or "installed"),
            "relative": str(directory.relative_to(root)) if _is_relative_to(directory, root) else directory.name,
            "installed": True,
            "installed_as": name,
        }
    meta = parse_skill_frontmatter(skill_file)
    name = _safe_name(str(meta.get("name") or directory.name), directory.name)
    return {
        "name": name,
        "source_name": name,
        "description": meta.get("description") or "",
        "path": str(directory),
        "file": str(skill_file),
        "source_id": source_id,
        "source_kind": source_kind,
        "relative": str(directory.relative_to(root)) if _is_relative_to(directory, root) else directory.name,
        "installed": False,
        "argument_hint": meta.get("argument_hint") or "",
    }


def _skill_file(directory: Path) -> Path | None:
    for filename in SKILL_FILENAMES:
        path = directory / filename
        if path.is_file():
            return path
    return None


def _is_installed_copy(directory: Path) -> bool:
    return (directory / SOURCE_MARKER).is_file()


def _read_marker(directory: Path) -> dict[str, Any]:
    path = directory / SOURCE_MARKER
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _installed_skills(dest: Path) -> list[dict[str, Any]]:
    if not dest.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for child in sorted(dest.iterdir()):
        if not child.is_dir() or not _is_installed_copy(child):
            continue
        record = _skill_from_dir(
            child,
            source_id=COBOOSE_SOURCE_ID,
            source_kind="installed",
            root=dest.parent.parent if dest.parent.name == ".github" else dest,
        )
        if record:
            found.append(record)
    return found


def _flatten_available(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        for skill in source.get("skills") or []:
            key = (skill["source_id"], skill["name"])
            if key in seen:
                continue
            seen.add(key)
            item = dict(skill)
            item["pick"] = (
                skill["name"]
                if skill["source_id"] == COBOOSE_SOURCE_ID
                else f"{skill['source_id']}:{skill['name']}"
            )
            available.append(item)
    return available


def _select_available(
    available: list[dict[str, Any]], names: list[str] | None
) -> list[dict[str, Any]]:
    if not names:
        return list(available)
    wanted = [_normalize_pick(name) for name in names]
    selected: list[dict[str, Any]] = []
    unmatched = list(wanted)
    for skill in available:
        keys = {
            _normalize_pick(skill["name"]),
            _normalize_pick(skill.get("pick") or skill["name"]),
            _normalize_pick(f"{skill['source_id']}:{skill['name']}"),
            _normalize_pick(f"{skill['source_id']}--{skill['name']}"),
        }
        hit = next((item for item in wanted if item in keys), None)
        if hit is None:
            continue
        selected.append(skill)
        if hit in unmatched:
            unmatched.remove(hit)
    if unmatched:
        raise CobooseError(
            "Unknown skill name(s): "
            + ", ".join(unmatched)
            + ". Run coboose skills list and pass --only with available[].pick"
        )
    return selected


def _normalize_pick(value: str) -> str:
    return value.strip().lower().replace("/", "-")


def _install_records(
    dest: Path,
    coboose_root: Path,
    selected: list[dict[str, Any]],
    *,
    parent: bool,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    coboose_dest = (coboose_root.resolve() / DEST_RELATIVE).resolve()
    copied: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    native: list[dict[str, Any]] = []

    for skill in selected:
        source_path = Path(skill["path"])
        same_tree = (
            not parent
            and skill["source_id"] == COBOOSE_SOURCE_ID
            and source_path.resolve().parent == coboose_dest
        )
        if same_tree:
            record = {**skill, "action": "native", "installed_as": skill["name"]}
            native.append(record)
            skipped.append(record)
            continue

        installed_as = _dest_name(dest, skill, force=force)
        target = dest / installed_as
        if target.exists() and _is_native_skill(target):
            conflicts.append(
                {
                    **skill,
                    "action": "conflict",
                    "installed_as": installed_as,
                    "detail": (
                        f"{installed_as} is a first-party coboose skill. "
                        "Refusing to overwrite it."
                    ),
                }
            )
            continue

        action = "update" if target.exists() and _is_installed_copy(target) else "copy"
        record = {
            **skill,
            "action": action,
            "installed_as": installed_as,
            "dest": str(target),
        }
        if dry_run:
            (updated if action == "update" else copied).append(record)
            continue
        _copy_skill_dir(source_path, target)
        _write_marker(target, skill, installed_as=installed_as)
        if action == "update":
            updated.append(record)
        else:
            copied.append(record)

    installed = _installed_skills(dest)
    return {
        "copied": copied,
        "updated": updated,
        "skipped": skipped,
        "conflicts": conflicts,
        "native": native,
        "installed": installed,
    }


def _dest_name(dest: Path, skill: dict[str, Any], *, force: bool) -> str:
    preferred = _safe_name(skill["name"], skill["name"])
    target = dest / preferred
    if not target.exists():
        return preferred
    if _is_installed_copy(target):
        marker = _read_marker(target)
        if marker.get("source_id") == skill["source_id"] or force:
            return preferred
    if _is_native_skill(target):
        return _safe_name(f"{skill['source_id']}--{skill['name']}", preferred)
    if _is_installed_copy(target) and not force:
        return _safe_name(f"{skill['source_id']}--{skill['name']}", preferred)
    return preferred


def _is_native_skill(directory: Path) -> bool:
    return directory.is_dir() and _skill_file(directory) is not None and not _is_installed_copy(directory)


def _copy_skill_dir(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=_copy_ignore)
    marker = dest / SOURCE_MARKER
    if marker.exists():
        marker.unlink()


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in SKIP_DIR_NAMES or name == SOURCE_MARKER}
    return ignored


def _write_marker(target: Path, skill: dict[str, Any], *, installed_as: str) -> None:
    payload = {
        "name": skill.get("source_name") or skill["name"],
        "description": skill.get("description") or "",
        "source_id": skill["source_id"],
        "source_kind": skill["source_kind"],
        "source_path": skill["path"],
        "installed_as": installed_as,
        "copied_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    (target / SOURCE_MARKER).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_manifest(coboose_root: Path, dest: Path, results: dict[str, Any]) -> None:
    path = coboose_root / MANIFEST_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except json.JSONDecodeError:
            existing = {}
    by_name = {
        item["installed_as"]: item
        for item in existing.get("skills") or []
        if isinstance(item, dict) and item.get("installed_as")
    }
    for group in ("copied", "updated"):
        for item in results.get(group) or []:
            by_name[item["installed_as"]] = {
                "name": item.get("source_name") or item["name"],
                "installed_as": item["installed_as"],
                "source_id": item["source_id"],
                "source_kind": item["source_kind"],
                "source_path": item["path"],
            }
    path.write_text(
        json.dumps(
            {
                "dest": str(dest),
                "updated_at": datetime.now(tz=timezone.utc).isoformat(),
                "skills": list(by_name.values()),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _ignore_installed(coboose_root: Path, dest: Path, results: dict[str, Any]) -> None:
    names = sorted(
        {
            item["installed_as"]
            for group in ("copied", "updated")
            for item in results.get(group) or []
            if item.get("installed_as")
        }
        | {item["installed_as"] for item in _installed_skills(dest) if item.get("installed_as")}
    )
    if dest.resolve() == (coboose_root.resolve() / DEST_RELATIVE).resolve():
        _write_ignore_file(
            dest / ".gitignore",
            [f"{name}/" for name in names],
            prefix="",
        )
        git_dir = coboose_root / ".git"
        if git_dir.exists():
            _write_ignore_file(
                git_dir / "info" / "exclude",
                [f".github/skills/{name}/" for name in names]
                + [
                    ".github/skills/.gitignore",
                    ".coboose/",
                    ".github/skills/*/.coboose-source.json",
                ],
                prefix="",
            )


def _write_ignore_file(path: Path, entries: list[str], *, prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    block_lines = [IGNORE_BEGIN, *(_prefix(entry, prefix) for entry in entries), IGNORE_END]
    block = "\n".join(block_lines) + "\n"
    if IGNORE_BEGIN in existing and IGNORE_END in existing:
        before, rest = existing.split(IGNORE_BEGIN, 1)
        _, after = rest.split(IGNORE_END, 1)
        text = before.rstrip() + "\n\n" + block + after.lstrip("\n")
    else:
        text = existing.rstrip() + ("\n\n" if existing.strip() else "") + block
    path.write_text(text, encoding="utf-8")


def _prefix(entry: str, prefix: str) -> str:
    return f"{prefix}{entry}" if prefix else entry


def _clone_skills_repo(
    url: str,
    dest: Path,
    *,
    ref: str | None,
    run: RunFn | None,
) -> None:
    if not shutil.which("git") and run is None:
        raise CobooseError("git is not installed or not on PATH")
    runner = run or _run_git
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = ["git", "clone", "--depth", "1", "--single-branch"]
    if ref:
        command.extend(["--branch", ref])
    command.extend([url, str(dest)])
    runner(command, dest.parent)


def _run_git(command: list[str], cwd: Path) -> Any:
    import subprocess

    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise CobooseError(
            f"Command failed ({exc.returncode}): {' '.join(command)}"
            + (f"\n{detail}" if detail else "")
        ) from exc


def _prompt_skill_names(prompt: PromptSession, available: list[dict[str, Any]]) -> list[str]:
    if not available:
        raise CobooseError("That repository has no SKILL.md folders")
    lines = ["Skills in the cloned repository:\n"]
    for index, skill in enumerate(available, start=1):
        detail = f" — {skill['description']}" if skill.get("description") else ""
        lines.append(f"  {index}. {skill['name']}{detail}\n")
    prompt.write("".join(lines))
    raw = prompt.ask("Install which skills? (comma-separated names/numbers, or all)")
    return _parse_skill_selection(raw, available)


def _parse_skill_selection(text: str, available: list[dict[str, Any]]) -> list[str]:
    text = text.strip()
    if not text:
        raise CobooseError("Pick at least one skill, or all")
    if text.lower() in {"all", "*"}:
        return [skill["name"] for skill in available]
    by_index = {str(index): skill["name"] for index, skill in enumerate(available, start=1)}
    by_name = {skill["name"].lower(): skill["name"] for skill in available}
    selected: list[str] = []
    for token in re.split(r"[,\s]+", text):
        if not token:
            continue
        if token in by_index:
            _append_unique(selected, by_index[token])
            continue
        lowered = token.lower()
        if lowered in by_name:
            _append_unique(selected, by_name[lowered])
            continue
        raise CobooseError(
            f"Unknown skill {token!r}. Use a listed name, number, or all."
        )
    return selected


def _pull_install_command(url: str, ref: str | None, names: list[str] | None) -> str:
    command = f"uv run coboose skills pull {url}"
    if ref:
        command += f" --ref {ref}"
    if names:
        command += " --only " + ",".join(names)
    else:
        command += " --only <name,name>"
    return command


def _remote_source_id(url: str) -> str:
    cleaned = url.rstrip("/").removesuffix(".git")
    name = cleaned.rsplit("/", 1)[-1]
    name = name.rsplit(":", 1)[-1]
    return _safe_name(name, "remote")


def _safe_name(value: str, fallback: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    if NAME_RE.match(value):
        return value
    fallback = re.sub(r"[^A-Za-z0-9._-]+", "-", fallback).strip("-")
    if NAME_RE.match(fallback):
        return fallback
    return "skill"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _empty_results() -> dict[str, Any]:
    return {
        "copied": [],
        "updated": [],
        "skipped": [],
        "conflicts": [],
        "native": [],
        "installed": [],
    }


def _guidance(*, parent: bool) -> list[str]:
    dest = (
        "parent_dir/.github/skills (open that folder as a single-root window)"
        if parent
        else "this Coboose repo's .github/skills (first multi-root folder)"
    )
    return [
        "VS Code Agents does not scan skills in multi-root child folders.",
        f"Lift or pull copies into {dest} so chat can load them natively.",
        "First-party coboose skills stay in this repo and are not overwritten.",
        "Lifted copies are local-only (gitignored). Do not commit product skills here.",
        "Use coboose skills list, then skills lift --only <pick>, or skills pull <url>.",
    ]

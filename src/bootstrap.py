from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from goat import GoatError
from goat.catalog import Catalog, Repo, parse_project_destination, paths_collide
from goat.clone import RunFn, clone_one, rewrite_clone_url
from goat.templates import Template, get_template, template_to_dict


def bootstrap_project(
    catalog: Catalog,
    goat_root: Path,
    *,
    template_name: str,
    dest_name: str | None = None,
    group: str | None = None,
    register: bool = False,
    remote: str | None = None,
    tags: list[str] | None = None,
    fresh_git: bool = False,
    keep_remote: bool = False,
    dry_run: bool = False,
    https: bool = False,
    run: RunFn | None = None,
) -> dict[str, Any]:
    if keep_remote and fresh_git:
        raise GoatError("Use either --keep-remote or --fresh-git, not both")

    if not catalog.templates:
        raise GoatError(
            f"No templates listed. Add entries to {catalog.templates_source}."
        )

    template = get_template(catalog.templates, template_name)
    if not template.enabled:
        raise GoatError(f"Template {template.name} is disabled")

    dest_raw = (dest_name or template.name).strip()
    project_name, project_path, project_group = parse_project_destination(
        dest_raw, group
    )

    sibling_root = catalog.require_safe_sibling_root(goat_root)
    dest = sibling_root / project_path
    dest_resolved = dest.resolve()
    goat = goat_root.resolve()
    if dest_resolved == goat or goat in dest_resolved.parents:
        raise GoatError("Refusing to bootstrap onto the Goat repo itself")
    if dest.exists():
        raise GoatError(
            f"{dest} already exists. Choose another --name or move that folder aside."
        )

    colliding = [repo.name for repo in catalog.repos if repo.name == project_name]
    path_colliding = [
        repo.name
        for repo in catalog.repos
        if paths_collide(repo.path, project_path)
    ]
    if (colliding or path_colliding) and register:
        conflict = colliding[0] if colliding else path_colliding[0]
        raise GoatError(
            f"{conflict} already occupies this name or path in repositories.yml. "
            "Pick a different --name / --group or update the manifest by hand."
        )

    repo = template.as_repo(project_name, path=project_path, group=project_group)
    clone_record = clone_one(
        repo,
        dest,
        sibling_root=sibling_root,
        update=False,
        dry_run=dry_run,
        https=https,
        run=run,
    )
    if clone_record.get("action") == "blocked":
        raise GoatError(
            "Template URL is still a placeholder. Update templates.yml first.",
            payload={"template": template_to_dict(template), "project": clone_record},
        )

    remote_state = "kept" if keep_remote else "detached"
    if fresh_git:
        remote_state = "fresh"
    origin_url = rewrite_clone_url(remote, https=https) if remote else None

    if not dry_run and clone_record.get("action") == "clone":
        runner = run or _require_run()
        remote_state = _post_clone(
            dest,
            run=runner,
            keep_remote=keep_remote,
            fresh_git=fresh_git,
            origin_url=origin_url,
            template_name=template.name,
        )

    registered = False
    register_record: dict[str, Any] | None = None
    if register:
        register_repo = Repo(
            name=project_name,
            url=origin_url or f"git@github.com:YOUR_ORG/{project_name}.git",
            path=project_path,
            default_branch=template.default_branch,
            description=template.description,
            tags=tags or list(template.tags),
            enabled=True,
            group=project_group,
        )
        if dry_run:
            register_record = {
                "action": "register",
                "name": register_repo.name,
                "url": register_repo.url,
                "path": register_repo.path,
                "group": register_repo.group,
                "tags": register_repo.tags,
                "manifest": str(catalog.repos_source),
            }
        else:
            register_record = append_repository(catalog.repos_source, register_repo)
            registered = True

    payload = {
        "template": template_to_dict(template),
        "project": {
            "name": project_name,
            "group": project_group,
            "relpath": project_path,
            "path": str(dest),
            "cloned": bool(clone_record.get("cloned")) and not dry_run,
            "action": "bootstrap" if clone_record.get("action") == "clone" else clone_record.get("action"),
            "url": clone_record.get("url"),
            "branch": template.default_branch,
            "remote": remote_state,
            "origin": origin_url,
        },
        "registered": registered,
        "register": register_record,
        "dry_run": dry_run,
        "next_steps": _next_steps(
            project_name,
            dest,
            registered=registered,
            origin_url=origin_url,
            remote_state=remote_state,
        ),
    }
    return payload


def append_repository(path: Path, repo: Repo) -> dict[str, Any]:
    if not path.exists():
        raise GoatError(f"File not found: {path}")
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if raw is None:
        raw = {}
    if isinstance(raw, list):
        raise GoatError(
            f"{path} is a top-level list. Add the new repo by hand; "
            "auto-register only supports the `repositories:` mapping form."
        )
    if not isinstance(raw, dict):
        raise GoatError(f"{path} must be a mapping to auto-register a repo")
    items = raw.get("repositories") or []
    if not isinstance(items, list):
        raise GoatError(f"{path} repositories: must be a list")
    for item in items:
        if isinstance(item, dict) and (item.get("name") or item.get("id")) == repo.name:
            raise GoatError(f"{repo.name} is already listed in {path}")

    indent = _repo_list_indent(text)
    entry = _repo_yaml_entry(repo, indent=indent)
    updated = _insert_repository_entry(text, entry)
    try:
        yaml.safe_load(updated)
    except yaml.YAMLError as exc:
        raise GoatError(f"Refusing to write invalid YAML to {path}: {exc}") from exc
    path.write_text(updated, encoding="utf-8")
    return {
        "action": "registered",
        "name": repo.name,
        "url": repo.url,
        "path": repo.path,
        "group": repo.group,
        "tags": repo.tags,
        "manifest": str(path),
    }


def _post_clone(
    dest: Path,
    *,
    run: RunFn,
    keep_remote: bool,
    fresh_git: bool,
    origin_url: str | None,
    template_name: str,
) -> str:
    if fresh_git:
        git_dir = dest / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)
        run(["git", "init", "-b", "main"], dest)
        run(["git", "add", "-A"], dest)
        run(
            [
                "git",
                "-c",
                "user.email=goat@local",
                "-c",
                "user.name=goat",
                "commit",
                "-m",
                f"Bootstrap from {template_name}",
            ],
            dest,
        )
        if origin_url:
            run(["git", "remote", "add", "origin", origin_url], dest)
        return "fresh"

    if keep_remote:
        if origin_url:
            run(["git", "remote", "set-url", "origin", origin_url], dest)
        return "kept"

    remotes = _git_remotes(dest, run)
    if "origin" in remotes:
        if "template" in remotes:
            run(["git", "remote", "remove", "origin"], dest)
        else:
            run(["git", "remote", "rename", "origin", "template"], dest)
    if origin_url:
        run(["git", "remote", "add", "origin", origin_url], dest)
    return "detached"


def _git_remotes(dest: Path, run: RunFn) -> set[str]:
    result = run(["git", "remote"], dest)
    return {line.strip() for line in (result.stdout or "").splitlines() if line.strip()}


def _require_run() -> RunFn:
    from goat.clone import _run

    return _run


def _repo_list_indent(text: str) -> str:
    for line in text.splitlines():
        stripped = line.lstrip(" ")
        if stripped.startswith("- name:") or stripped.startswith("- id:"):
            return line[: len(line) - len(stripped)]
    return "  "


def _repo_yaml_entry(repo: Repo, indent: str = "  ") -> str:
    field = indent + "  "
    tags = ", ".join(repo.tags)
    lines = [
        f"{indent}- name: {repo.name}",
        f"{field}url: {repo.url}",
        f"{field}tags: [{tags}]",
    ]
    if repo.group:
        lines.append(f"{field}group: {repo.group}")
    derived = f"{repo.group}/{repo.name}" if repo.group else repo.name
    if repo.path != derived:
        lines.append(f"{field}path: {repo.path}")
    if repo.description:
        lines.append(f"{field}description: {_yaml_scalar(repo.description)}")
    return "\n".join(lines) + "\n"


def _yaml_scalar(value: str) -> str:
    if value == "" or any(ch in value for ch in ":#{}[],&*!|>'\"%@`"):
        return json.dumps(value)
    return value


def _insert_repository_entry(text: str, entry: str) -> str:
    stripped = text.rstrip()
    if "repositories: []" in stripped.splitlines()[-1:]:
        prefix = stripped.rsplit("repositories: []", 1)[0]
        return prefix + "repositories:\n" + entry
    if stripped.endswith("repositories:"):
        return stripped + "\n" + entry
    return stripped + "\n\n" + entry


def _next_steps(
    name: str,
    dest: Path,
    *,
    registered: bool,
    origin_url: str | None,
    remote_state: str,
) -> list[str]:
    steps = [f"Open the new project: code {dest}"]
    if not origin_url:
        steps.append(
            f"Add a GitHub remote when ready: git -C {dest} remote add origin "
            f"git@github.com:YOUR_ORG/{name}.git"
        )
    if remote_state == "detached":
        steps.append(
            "The template remote is named `template`. Push to `origin` after you add it."
        )
    if not registered:
        steps.append(
            f"To track this project in the stack: add it to repositories.yml "
            f"or rerun with --register --name {name}"
        )
    else:
        steps.append("Run `goat workspace generate` if a feature workspace should include it.")
    return steps

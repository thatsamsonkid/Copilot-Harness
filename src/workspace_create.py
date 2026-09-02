from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

from goat import GoatError
from goat.catalog import (
    Catalog,
    Repo,
    Workspace,
    WorkspaceMatch,
    load_catalog,
)
from goat.prompt import PromptSession
from goat.skills import compact_sync_result, sync_root_skills
from goat.stack_edit import upsert_workspace_in_stack
from goat.workspace import open_command, write_workspace_file

_WORKSPACE_ID = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_RANGE = re.compile(r"^(\d+)\s*-\s*(\d+)$")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def title_from_id(workspace_id: str) -> str:
    return workspace_id.replace("-", " ").replace("_", " ").title()


def validate_workspace_id(workspace_id: str) -> str:
    workspace_id = slugify(workspace_id)
    if not workspace_id or not _WORKSPACE_ID.match(workspace_id):
        raise GoatError(
            "Workspace id must be a lowercase slug such as checkout or checkout-flow."
        )
    return workspace_id


def parse_project_selection(text: str, repos: Sequence[Repo]) -> list[str]:
    """Parse numbers, ranges, names, 'all', or tag:<tag> into repository names."""
    text = text.strip()
    if not text:
        raise GoatError("Select at least one project from repositories.yml.")
    if text.lower() in {"all", "*"}:
        names = [repo.name for repo in repos if repo.enabled]
        if not names:
            raise GoatError("No enabled repositories in repositories.yml.")
        return names

    by_name = {repo.name.lower(): repo.name for repo in repos}
    by_index = {str(index): repo.name for index, repo in enumerate(repos, start=1)}
    selected: list[str] = []

    for raw_token in _split_tokens(text):
        token = raw_token.strip()
        if not token:
            continue
        lowered = token.lower()
        if lowered in {"all", "*"}:
            for repo in repos:
                if repo.enabled:
                    _append_unique(selected, repo.name)
            continue
        if lowered.startswith("tag:"):
            tag = token.split(":", 1)[1].strip()
            matched = [
                repo.name
                for repo in repos
                if tag.lower() in {item.lower() for item in repo.tags}
            ]
            if not matched:
                known = sorted({tag for repo in repos for tag in repo.tags})
                raise GoatError(
                    f"No repositories.yml entry has tag {tag!r}. "
                    f"Known tags: {', '.join(known) or '(none)'}."
                )
            for name in matched:
                _append_unique(selected, name)
            continue
        range_match = _RANGE.match(token)
        if range_match:
            start = int(range_match.group(1))
            stop = int(range_match.group(2))
            if start > stop:
                start, stop = stop, start
            for index in range(start, stop + 1):
                _append_unique(selected, _index_name(index, repos, by_index))
            continue
        if token.isdigit():
            _append_unique(selected, _index_name(int(token), repos, by_index))
            continue
        if lowered in by_name:
            _append_unique(selected, by_name[lowered])
            continue
        known = ", ".join(
            f"{index}:{repo.name}" for index, repo in enumerate(repos, start=1)
        )
        raise GoatError(
            f"Unknown project {token!r}. Choose from repositories.yml ({known})."
        )
    if not selected:
        raise GoatError("Select at least one project from repositories.yml.")
    return selected


def format_project_menu(repos: Sequence[Repo]) -> str:
    if not repos:
        return "No repositories found in repositories.yml.\n"
    lines = ["Repositories from repositories.yml:\n"]
    for index, repo in enumerate(repos, start=1):
        tags = ", ".join(repo.tags) if repo.tags else "(no tags)"
        disabled = "" if repo.enabled else " [disabled]"
        lines.append(f"  {index}. {repo.name}{disabled}")
        detail = f"tags: {tags}"
        if repo.path != repo.name:
            detail = f"path: {repo.path}  ·  {detail}"
        if repo.description:
            detail += f"  ·  {repo.description}"
        lines.append(f"     {detail}")
    lines.append("")
    lines.append("Enter numbers, names, ranges (1-3), all, or tag:<tag>.")
    return "\n".join(lines) + "\n"


def create_workspace(
    catalog: Catalog,
    goat_root: Path,
    *,
    workspace_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
    folders: list[str] | None = None,
    tags: list[str] | None = None,
    include_goat: bool | None = None,
    fallback: bool = False,
    match_projects: list[str] | None = None,
    match_components: list[str] | None = None,
    match_labels: list[str] | None = None,
    match_keywords: list[str] | None = None,
    force: bool = False,
    generate: bool = True,
    dry_run: bool = False,
    prompt: PromptSession | None = None,
) -> dict[str, Any]:
    prompt = prompt or PromptSession()

    workspace_id = _resolve_id(workspace_id, prompt)
    existing = _existing_workspace(catalog, workspace_id)
    if existing is not None and not force:
        if prompt.can_prompt() and folders is None and tags is None:
            if prompt.confirm(
                f"Workspace {workspace_id} already exists. Replace it?",
                default=False,
            ):
                force = True
            else:
                raise GoatError(
                    f"Workspace {workspace_id} already exists. Pass --force to replace it."
                )
        else:
            raise GoatError(
                f"Workspace {workspace_id} already exists. Pass --force to replace it."
            )

    name = _resolve_name(name, workspace_id, prompt)
    description = _resolve_description(description, prompt)
    folders, tags = _resolve_projects(catalog, folders, tags, prompt)
    include_goat = _resolve_include_goat(include_goat, prompt)

    if fallback:
        current = [item.id for item in catalog.workspaces if item.fallback]
        if current and current != [workspace_id]:
            raise GoatError(
                f"Only one workspace can be fallback=true; {current[0]} already is. "
                "Edit catalog/stack.yaml to change it."
            )

    workspace = Workspace(
        id=workspace_id,
        name=name,
        description=description or "",
        folders=folders,
        tags=tags,
        include_goat=include_goat,
        fallback=fallback,
        match=WorkspaceMatch(
            projects=match_projects or [],
            components=match_components or [],
            labels=match_labels or [],
            issue_types=[],
            keywords=match_keywords or [],
        ),
    )

    included = catalog.workspace_repo_names(workspace)
    if not included:
        raise GoatError(
            "Workspace would include no repositories. "
            "Choose projects or tags from repositories.yml."
        )
    stack_path = catalog.source
    replaced = existing is not None

    if dry_run:
        document_folders = ["goat"] if include_goat else []
        document_folders.extend(catalog.workspace_repo_names(workspace))
        return _payload(
            catalog,
            goat_root,
            workspace,
            created=not replaced,
            replaced=replaced,
            generated=False,
            dry_run=True,
            folders=document_folders,
        )

    upsert_workspace_in_stack(stack_path, workspace, replace=force or replaced)
    refreshed = load_catalog(
        goat_root,
        stack_path=stack_path,
        repos_path=catalog.repos_source,
    )
    persisted = refreshed.workspace(workspace_id)

    written: dict[str, Any] | None = None
    if generate:
        written = write_workspace_file(refreshed, goat_root, persisted)

    payload = _payload(
        refreshed,
        goat_root,
        persisted,
        created=not replaced,
        replaced=replaced,
        generated=written is not None,
        dry_run=False,
        folders=(written or {}).get("folders")
        or (["goat"] if include_goat else [])
        + refreshed.workspace_repo_names(persisted),
        file=(written or {}).get("file"),
    )
    payload["skills"] = compact_sync_result(
        sync_root_skills(
            refreshed,
            goat_root,
            workspace_id=persisted.id,
        )
    )
    return payload


def create_menu(catalog: Catalog, goat_root: Path) -> dict[str, Any]:
    """Compact picker for /new-workspace. No URLs, graphify, skills, or CLI catalog."""
    projects: list[dict[str, Any]] = []
    for index, repo in enumerate(catalog.repos, start=1):
        repo_path = catalog.repo_path(goat_root, repo)
        item: dict[str, Any] = {
            "n": index,
            "name": repo.name,
            "tags": list(repo.tags),
            "description": repo.description,
            "enabled": repo.enabled,
            "cloned": repo_path.exists(),
        }
        if repo.group:
            item["group"] = repo.group
        if repo.path != repo.name:
            item["path"] = repo.path
        projects.append(item)
    tags = sorted({tag for repo in catalog.repos for tag in repo.tags})
    return {
        "kind": "workspace_create_menu",
        "projects": [item for item in projects if item["enabled"]],
        "disabled": [item["name"] for item in projects if not item["enabled"]],
        "workspaces": [
            {"id": item.id, "name": item.name} for item in catalog.workspaces
        ],
        "tags": tags,
        "select": "numbers, names, ranges (1-3), all, or tag:<tag>",
        "create_command": (
            "uv run goat workspace create <id> --projects <names> "
            "--no-prompt --format json"
        ),
        "defaults": {"include_goat": True},
        "guidance": [
            "Show a compact numbered list from projects[] (n, name, tags).",
            "If there are more than 12 projects, show tags[] first and ask "
            "whether to filter with tag:<tag> or see the full list.",
            "Do not run goat repos, goat catalog, goat workspace list, "
            "goat commands, goat skills list, or goat context.",
            "Ask for id, then projects. Skip description unless they offer one.",
            "After confirm, run create_command. Report workspace.file and "
            "open_command only.",
        ],
    }


def _existing_workspace(catalog: Catalog, workspace_id: str) -> Workspace | None:
    return next(
        (item for item in catalog.workspaces if item.id == workspace_id), None
    )


def _resolve_id(workspace_id: str | None, prompt: PromptSession) -> str:
    if workspace_id:
        return validate_workspace_id(workspace_id)
    if not prompt.can_prompt():
        raise GoatError(
            "workspace create needs --id, or a terminal so it can prompt."
        )
    raw = prompt.ask("Workspace id (slug, e.g. checkout)")
    workspace_id = validate_workspace_id(raw)
    if raw.strip() != workspace_id:
        prompt.write(f"Using id: {workspace_id}\n")
    return workspace_id


def _resolve_name(
    name: str | None, workspace_id: str, prompt: PromptSession
) -> str:
    if name:
        return name
    default = title_from_id(workspace_id)
    if not prompt.can_prompt():
        return default
    return prompt.ask("Display name", default=default) or default


def _resolve_description(description: str | None, prompt: PromptSession) -> str:
    if description is not None:
        return description
    if not prompt.can_prompt():
        return ""
    return prompt.ask("Description (optional)", default="")


def _resolve_projects(
    catalog: Catalog,
    folders: list[str] | None,
    tags: list[str] | None,
    prompt: PromptSession,
) -> tuple[list[str], list[str]]:
    folders = list(folders or [])
    tags = list(tags or [])
    if folders or tags:
        _validate_folders(catalog, folders)
        _validate_tags(catalog, tags)
        return folders, tags
    if not prompt.can_prompt():
        raise GoatError(
            "workspace create needs --projects / --folders or --tag, "
            "or a terminal so it can prompt."
        )
    repos = list(catalog.repos)
    prompt.write("\n" + format_project_menu(repos))
    while True:
        try:
            selected = parse_project_selection(
                prompt.ask("Projects to include"),
                repos,
            )
            return selected, []
        except (GoatError, EOFError) as exc:
            if isinstance(exc, EOFError):
                raise GoatError(
                    "Select at least one project from repositories.yml."
                ) from exc
            prompt.write(f"{exc.message}\n")


def _resolve_include_goat(
    include_goat: bool | None, prompt: PromptSession
) -> bool:
    if include_goat is not None:
        return include_goat
    if not prompt.can_prompt():
        return True
    return prompt.confirm(
        "Include this Goat repo as the first workspace folder?",
        default=True,
    )


def _validate_folders(catalog: Catalog, folders: list[str]) -> None:
    unknown = [name for name in folders if name not in {repo.name for repo in catalog.repos}]
    if unknown:
        known = ", ".join(repo.name for repo in catalog.repos)
        raise GoatError(
            "Unknown repo name(s): "
            + ", ".join(unknown)
            + f". Add them to repositories.yml or choose from: {known}."
        )


def _validate_tags(catalog: Catalog, tags: list[str]) -> None:
    known = {tag.lower() for repo in catalog.repos for tag in repo.tags}
    unknown = [tag for tag in tags if tag.lower() not in known]
    if unknown:
        raise GoatError(
            "Unknown tag(s): "
            + ", ".join(unknown)
            + ". Known tags: "
            + ", ".join(sorted({tag for repo in catalog.repos for tag in repo.tags}))
            + "."
        )


def _payload(
    catalog: Catalog,
    goat_root: Path,
    workspace: Workspace,
    *,
    created: bool,
    replaced: bool,
    generated: bool,
    dry_run: bool,
    folders: list[str],
    file: str | None = None,
) -> dict[str, Any]:
    path = catalog.workspace_file(goat_root, workspace)
    repos = []
    for repo_id in catalog.workspace_repo_names(workspace):
        repo = catalog.repo(repo_id)
        repo_path = catalog.repo_path(goat_root, repo)
        repos.append(
            {
                "name": repo.name,
                "cloned": repo_path.exists(),
            }
        )
    return {
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "description": workspace.description,
            "folders": catalog.workspace_repo_names(workspace),
            "tags": workspace.tags,
            "include_goat": workspace.include_goat,
            "fallback": workspace.fallback,
            "file": file or str(path),
            "catalog": str(catalog.source),
            "exists": path.exists(),
        },
        "repos": repos,
        "folders": folders,
        "created": created,
        "replaced": replaced,
        "generated": generated,
        "dry_run": dry_run,
        "open_command": open_command(path),
    }


def _split_tokens(text: str) -> list[str]:
    return [part for part in re.split(r"[,\s]+", text) if part]


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _index_name(index: int, repos: Sequence[Repo], by_index: dict[str, str]) -> str:
    name = by_index.get(str(index))
    if not name:
        raise GoatError(
            f"Project number {index} is out of range (1-{len(repos)})."
        )
    return name

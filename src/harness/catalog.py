from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from harness import HarnessError


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise HarnessError(f"Expected a list or string, got {type(value).__name__}")


@dataclass(frozen=True)
class Repo:
    id: str
    url: str
    path: str
    default_branch: str = "main"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    enabled: bool = True

    @property
    def is_placeholder(self) -> bool:
        needle = self.url.lower()
        return "your_org" in needle or "example.com" in needle or "example/" in needle


@dataclass(frozen=True)
class WorkspaceMatch:
    projects: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    issue_types: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    description: str = ""
    folders: list[str] = field(default_factory=list)
    include_harness: bool = True
    fallback: bool = False
    match: WorkspaceMatch = field(default_factory=WorkspaceMatch)


@dataclass(frozen=True)
class JiraSettings:
    extra_fields: list[str] = field(default_factory=list)
    field_aliases: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Catalog:
    parent_dir: str
    repos: list[Repo]
    workspaces: list[Workspace]
    jira: JiraSettings
    source: Path

    def repo(self, repo_id: str) -> Repo:
        for repo in self.repos:
            if repo.id == repo_id:
                return repo
        raise HarnessError(f"Unknown repo id: {repo_id}")

    def workspace(self, workspace_id: str) -> Workspace:
        for workspace in self.workspaces:
            if workspace.id == workspace_id:
                return workspace
        raise HarnessError(f"Unknown workspace id: {workspace_id}")

    def enabled_repos(self, only: list[str] | None = None) -> list[Repo]:
        selected = [repo for repo in self.repos if repo.enabled]
        if only:
            wanted = set(only)
            unknown = wanted.difference(repo.id for repo in self.repos)
            if unknown:
                raise HarnessError(
                    "Unknown repo id(s): " + ", ".join(sorted(unknown))
                )
            selected = [repo for repo in selected if repo.id in wanted]
        return selected

    def sibling_root(self, harness_root: Path) -> Path:
        return (harness_root / self.parent_dir).resolve()

    def require_safe_sibling_root(self, harness_root: Path) -> Path:
        root = self.sibling_root(harness_root)
        if root == Path(root.anchor):
            raise HarnessError(
                f"parent_dir resolves to the filesystem root ({root}). "
                "Keep the harness in a project folder so clones land as siblings, not in /."
            )
        return root

    def repo_path(self, harness_root: Path, repo: Repo | str) -> Path:
        if isinstance(repo, str):
            repo = self.repo(repo)
        return self.sibling_root(harness_root) / repo.path

    def workspace_file(self, harness_root: Path, workspace: Workspace | str) -> Path:
        if isinstance(workspace, str):
            workspace = self.workspace(workspace)
        return harness_root / "workspaces" / f"{workspace.id}.code-workspace"


def load_catalog(path: Path) -> Catalog:
    if not path.exists():
        raise HarnessError(f"Catalog not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise HarnessError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise HarnessError(f"Catalog root must be a mapping: {path}")
    return _parse_catalog(raw, path)


def _parse_catalog(raw: dict[str, Any], source: Path) -> Catalog:
    repos: list[Repo] = []
    seen_repo_ids: set[str] = set()
    seen_repo_paths: set[str] = set()
    for item in raw.get("repos") or []:
        if not isinstance(item, dict) or "id" not in item or "url" not in item:
            raise HarnessError("Each repo needs id and url")
        repo_id = str(item["id"])
        repo_path = str(item.get("path") or repo_id)
        if repo_id in seen_repo_ids:
            raise HarnessError(f"Duplicate repo id: {repo_id}")
        if repo_path in seen_repo_paths:
            raise HarnessError(f"Duplicate repo path: {repo_path}")
        if Path(repo_path).is_absolute() or ".." in Path(repo_path).parts:
            raise HarnessError(
                f"Repo path must be a single sibling folder name: {repo_path}"
            )
        seen_repo_ids.add(repo_id)
        seen_repo_paths.add(repo_path)
        repos.append(
            Repo(
                id=repo_id,
                url=str(item["url"]),
                path=repo_path,
                default_branch=str(item.get("default_branch") or "main"),
                description=str(item.get("description") or ""),
                tags=_as_list(item.get("tags")),
                enabled=bool(item.get("enabled", True)),
            )
        )

    workspaces: list[Workspace] = []
    seen_workspace_ids: set[str] = set()
    for item in raw.get("workspaces") or []:
        if not isinstance(item, dict) or "id" not in item:
            raise HarnessError("Each workspace needs an id")
        workspace_id = str(item["id"])
        if workspace_id in seen_workspace_ids:
            raise HarnessError(f"Duplicate workspace id: {workspace_id}")
        seen_workspace_ids.add(workspace_id)
        match_raw = item.get("match") or {}
        if not isinstance(match_raw, dict):
            raise HarnessError(f"Workspace {workspace_id} match must be a mapping")
        folders = _as_list(item.get("folders"))
        unknown = [folder for folder in folders if folder not in seen_repo_ids]
        if unknown:
            raise HarnessError(
                f"Workspace {workspace_id} references unknown repo id(s): "
                + ", ".join(unknown)
            )
        workspaces.append(
            Workspace(
                id=workspace_id,
                name=str(item.get("name") or workspace_id),
                description=str(item.get("description") or ""),
                folders=folders,
                include_harness=bool(item.get("include_harness", True)),
                fallback=bool(item.get("fallback", False)),
                match=WorkspaceMatch(
                    projects=_as_list(match_raw.get("projects")),
                    components=_as_list(match_raw.get("components")),
                    labels=_as_list(match_raw.get("labels")),
                    issue_types=_as_list(match_raw.get("issue_types")),
                    keywords=_as_list(match_raw.get("keywords")),
                ),
            )
        )

    jira_raw = raw.get("jira") or {}
    if not isinstance(jira_raw, dict):
        raise HarnessError("jira settings must be a mapping")
    aliases = jira_raw.get("field_aliases") or {}
    if not isinstance(aliases, dict):
        raise HarnessError("jira.field_aliases must be a mapping")

    fallbacks = [workspace.id for workspace in workspaces if workspace.fallback]
    if len(fallbacks) > 1:
        raise HarnessError(
            "Only one workspace can be fallback=true; found: " + ", ".join(fallbacks)
        )

    return Catalog(
        parent_dir=str(raw.get("parent_dir") or ".."),
        repos=repos,
        workspaces=workspaces,
        jira=JiraSettings(
            extra_fields=_as_list(jira_raw.get("extra_fields")),
            field_aliases={str(key): str(value) for key, value in aliases.items()},
        ),
        source=source,
    )


def catalog_to_dict(catalog: Catalog, harness_root: Path) -> dict[str, Any]:
    sibling_root = catalog.sibling_root(harness_root)
    return {
        "source": str(catalog.source),
        "parent_dir": catalog.parent_dir,
        "sibling_root": str(sibling_root),
        "repos": [
            {
                "id": repo.id,
                "url": repo.url,
                "path": repo.path,
                "resolved_path": str(catalog.repo_path(harness_root, repo)),
                "default_branch": repo.default_branch,
                "description": repo.description,
                "tags": repo.tags,
                "enabled": repo.enabled,
                "placeholder": repo.is_placeholder,
            }
            for repo in catalog.repos
        ],
        "workspaces": [
            {
                "id": workspace.id,
                "name": workspace.name,
                "description": workspace.description,
                "folders": workspace.folders,
                "include_harness": workspace.include_harness,
                "fallback": workspace.fallback,
                "file": str(catalog.workspace_file(harness_root, workspace)),
                "match": {
                    "projects": workspace.match.projects,
                    "components": workspace.match.components,
                    "labels": workspace.match.labels,
                    "issue_types": workspace.match.issue_types,
                    "keywords": workspace.match.keywords,
                },
            }
            for workspace in catalog.workspaces
        ],
        "jira": {
            "extra_fields": catalog.jira.extra_fields,
            "field_aliases": catalog.jira.field_aliases,
        },
    }

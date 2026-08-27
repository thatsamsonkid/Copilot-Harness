from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from harness import HarnessError
from harness.jira_fields import DEFAULT_OUTPUT_FIELDS, JiraSettings
from harness.paths import (
    PERSONAL_WORKSPACES_DIR,
    REPOS_RELATIVE,
    STACK_RELATIVE,
    TEMPLATES_RELATIVE,
    WORKSPACES_DIR,
)

if TYPE_CHECKING:
    from harness.templates import Template


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise HarnessError(f"Expected a list or string, got {type(value).__name__}")


def read_yaml(path: Path) -> Any:
    if not path.exists():
        raise HarnessError(f"File not found: {path}")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise HarnessError(f"Invalid YAML in {path}: {exc}") from exc


_as_list = as_list
_read_yaml = read_yaml


@dataclass(frozen=True)
class GraphifyConfig:
    out: str = "graphify-out"
    enabled: bool = True


@dataclass(frozen=True)
class StartConfig:
    """Optional repositories.yml override when start discovery is wrong."""

    command: str = ""
    port: int | None = None
    role: str = ""
    wait: str = ""
    cwd: str = ""

    def configured(self) -> bool:
        return bool(self.command or self.port or self.role or self.wait or self.cwd)

    def to_dict(self) -> dict[str, Any] | None:
        if not self.configured():
            return None
        return {
            "command": self.command or None,
            "port": self.port,
            "role": self.role or None,
            "wait": self.wait or None,
            "cwd": self.cwd or None,
        }


@dataclass(frozen=True)
class Repo:
    name: str
    url: str
    path: str
    default_branch: str = "main"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    enabled: bool = True
    graphify: GraphifyConfig = field(default_factory=GraphifyConfig)
    group: str = ""
    start: StartConfig = field(default_factory=StartConfig)

    @property
    def id(self) -> str:
        return self.name

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
    tags: list[str] = field(default_factory=list)
    include_harness: bool = True
    fallback: bool = False
    personal: bool = False
    match: WorkspaceMatch = field(default_factory=WorkspaceMatch)


@dataclass(frozen=True)
class Catalog:
    parent_dir: str
    repos: list[Repo]
    workspaces: list[Workspace]
    jira: JiraSettings
    source: Path
    repos_source: Path
    templates: list[Template] = field(default_factory=list)
    templates_source: Path | None = None

    def repo(self, repo_id: str) -> Repo:
        for repo in self.repos:
            if repo.name == repo_id:
                return repo
        raise HarnessError(f"Unknown repo name: {repo_id}")

    def template(self, template_id: str):
        from harness.templates import get_template

        return get_template(self.templates, template_id)

    def workspace(self, workspace_id: str) -> Workspace:
        for workspace in self.workspaces:
            if workspace.id == workspace_id:
                return workspace
        raise HarnessError(f"Unknown workspace id: {workspace_id}")

    def repos_with_tags(self, tags: list[str]) -> list[Repo]:
        wanted = {tag.lower() for tag in tags}
        return [
            repo
            for repo in self.repos
            if wanted.intersection(tag.lower() for tag in repo.tags)
        ]

    def enabled_repos(
        self, only: list[str] | None = None, tags: list[str] | None = None
    ) -> list[Repo]:
        selected = [repo for repo in self.repos if repo.enabled]
        if only:
            wanted = set(only)
            unknown = wanted.difference(repo.name for repo in self.repos)
            if unknown:
                raise HarnessError(
                    "Unknown repo name(s): " + ", ".join(sorted(unknown))
                )
            selected = [repo for repo in selected if repo.name in wanted]
        if tags:
            tagged = {repo.name for repo in self.repos_with_tags(tags)}
            selected = [repo for repo in selected if repo.name in tagged]
        return selected

    def workspace_repo_names(self, workspace: Workspace | str) -> list[str]:
        if isinstance(workspace, str):
            workspace = self.workspace(workspace)
        names: list[str] = []
        for name in [*workspace.folders, *(repo.name for repo in self.repos_with_tags(workspace.tags))]:
            if name not in names:
                names.append(name)
        return names

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
        directory = PERSONAL_WORKSPACES_DIR if workspace.personal else WORKSPACES_DIR
        return harness_root / directory / f"{workspace.id}.code-workspace"

    def workspace_start_file(self, harness_root: Path, workspace: Workspace | str) -> Path:
        """YAML start sequence saved next to the .code-workspace file."""
        workspace_file = self.workspace_file(harness_root, workspace)
        return workspace_file.with_name(f"{workspace_file.stem}.start.yml")


def load_catalog(
    harness_root: Path,
    *,
    stack_path: Path | None = None,
    repos_path: Path | None = None,
    templates_path: Path | None = None,
) -> Catalog:
    from harness.templates import load_templates

    harness_root = Path(harness_root)
    repos_file = Path(repos_path) if repos_path else harness_root / REPOS_RELATIVE
    stack_file = Path(stack_path) if stack_path else harness_root / STACK_RELATIVE
    templates_file = (
        Path(templates_path) if templates_path else harness_root / TEMPLATES_RELATIVE
    )
    repos, parent_dir = load_repositories(repos_file)
    repo_names = {repo.name for repo in repos}
    workspaces, jira = load_stack(stack_file, repo_names)
    workspaces = [
        *workspaces,
        *load_personal_workspaces(
            harness_root,
            repo_names,
            reserved_ids={workspace.id for workspace in workspaces},
        ),
    ]
    templates = load_templates(templates_file)
    return Catalog(
        parent_dir=parent_dir,
        repos=repos,
        workspaces=workspaces,
        jira=jira,
        source=stack_file,
        repos_source=repos_file,
        templates=templates,
        templates_source=templates_file,
    )


def load_repositories(path: Path) -> tuple[list[Repo], str]:
    raw = _read_yaml(path)
    parent_dir = ".."
    items: list[Any]
    if raw is None:
        items = []
    elif isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        if raw.get("repos") and not raw.get("repositories"):
            raise HarnessError(
                f"{path} uses `repos:`. Rename that key to `repositories:` "
                "and give each entry name, url, and tags."
            )
        parent_dir = str(raw.get("parent_dir") or "..")
        items = raw.get("repositories") or []
    else:
        raise HarnessError(f"{path} must be a mapping or a list of repositories")

    repos: list[Repo] = []
    seen_names: set[str] = set()
    seen_paths: set[str] = set()
    for item in items:
        repo = _parse_repo(item)
        if repo.name in seen_names:
            raise HarnessError(f"Duplicate repository name: {repo.name}")
        if repo.path in seen_paths:
            raise HarnessError(f"Duplicate repository path: {repo.path}")
        seen_names.add(repo.name)
        seen_paths.add(repo.path)
        repos.append(repo)
    _assert_no_path_collisions(repos)
    if not repos:
        raise HarnessError(
            f"{path} has no repositories. Add entries with name, url, and tags."
        )
    return repos, parent_dir


def _parse_repo(item: Any) -> Repo:
    if not isinstance(item, dict):
        raise HarnessError("Each repository entry must be a mapping")
    name = item.get("name") or item.get("id")
    url = item.get("url") or item.get("clone_url") or item.get("git")
    if not name or not url:
        raise HarnessError("Each repository needs name and url (GitHub clone URL)")
    name = str(name)
    validate_repo_name(name)
    repo_path, group = resolve_repo_layout(name, item.get("path"), item.get("group"))
    tags = _as_list(item.get("tags"))
    if not tags:
        raise HarnessError(f"Repository {name} needs at least one tag")
    return Repo(
        name=name,
        url=str(url),
        path=repo_path,
        default_branch=str(item.get("default_branch") or item.get("branch") or "main"),
        description=str(item.get("description") or ""),
        tags=tags,
        enabled=bool(item.get("enabled", True)),
        graphify=_parse_graphify(name, item.get("graphify")),
        group=group,
        start=_parse_start(name, item.get("start")),
    )


def validate_repo_name(name: str) -> str:
    name = str(name).strip()
    dest = Path(name)
    if (
        not name
        or dest.is_absolute()
        or len(dest.parts) != 1
        or dest.parts[0] in {".", ".."}
        or "/" in name
        or "\\" in name
    ):
        raise HarnessError(
            f"Repository name must be a single id, not a path: {name}"
        )
    return name


def resolve_repo_layout(
    name: str, raw_path: Any, raw_group: Any
) -> tuple[str, str]:
    group = normalize_clone_relpath(str(raw_group), "Repository group") if raw_group else ""
    if raw_path:
        repo_path = normalize_clone_relpath(str(raw_path), "Repo path")
        if group and repo_path != group and not repo_path.startswith(f"{group}/"):
            raise HarnessError(
                f"Repository {name} path {repo_path!r} must be inside group {group!r}"
            )
        return repo_path, group
    if group:
        return f"{group}/{name}", group
    return name, ""


def parse_project_destination(
    dest_name: str, group: str | None = None
) -> tuple[str, str, str]:
    """Return (name, path, group) for a bootstrap destination under parent_dir."""
    dest_name = (dest_name or "").strip()
    if not dest_name:
        raise HarnessError("Project --name is required")
    dest_name = dest_name.replace("\\", "/")
    group = (group or "").strip().replace("\\", "/")
    if group:
        group = normalize_clone_relpath(group, "Project group")
        if "/" in dest_name:
            repo_path = normalize_clone_relpath(dest_name, "Project path")
            if repo_path != group and not repo_path.startswith(f"{group}/"):
                raise HarnessError(
                    f"Project path {repo_path!r} must be inside group {group!r}"
                )
        else:
            validate_repo_name(dest_name)
            repo_path = f"{group}/{dest_name}"
    else:
        repo_path = normalize_clone_relpath(dest_name, "Project path")
        if len(Path(repo_path).parts) > 1:
            group = "/".join(Path(repo_path).parts[:-1])
    name = Path(repo_path).name
    validate_repo_name(name)
    return name, repo_path, group


def normalize_clone_relpath(value: str, label: str) -> str:
    text = str(value).strip().replace("\\", "/")
    path = Path(text)
    if (
        not text
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise HarnessError(
            f"{label} must be a relative path under parent_dir, without '..': {value}"
        )
    return path.as_posix()


def paths_collide(left: str, right: str) -> bool:
    left_parts = Path(left).parts
    right_parts = Path(right).parts
    shared = min(len(left_parts), len(right_parts))
    return left_parts[:shared] == right_parts[:shared]


def _assert_no_path_collisions(repos: list[Repo]) -> None:
    for index, repo in enumerate(repos):
        for other in repos[index + 1 :]:
            if paths_collide(repo.path, other.path):
                raise HarnessError(
                    f"Repository paths collide: {repo.path!r} ({repo.name}) and "
                    f"{other.path!r} ({other.name}). One clone cannot live inside another."
                )


def _parse_start(repo_name: str, raw: Any) -> StartConfig:
    if raw is None:
        return StartConfig()
    if not isinstance(raw, dict):
        raise HarnessError(f"Repository {repo_name} start must be a mapping")
    port_raw = raw.get("port")
    port: int | None = None
    if port_raw is not None and port_raw != "":
        try:
            port = int(port_raw)
        except (TypeError, ValueError) as exc:
            raise HarnessError(
                f"Repository {repo_name} start.port must be an integer"
            ) from exc
        if port < 1 or port > 65535:
            raise HarnessError(f"Repository {repo_name} start.port is out of range")
    cwd = str(raw.get("cwd") or "").strip()
    if cwd:
        _require_relative_dir(f"Repository {repo_name} start.cwd", cwd)
    return StartConfig(
        command=str(raw.get("command") or "").strip(),
        port=port,
        role=str(raw.get("role") or "").strip().lower(),
        wait=str(raw.get("wait") or raw.get("health") or "").strip(),
        cwd=cwd,
    )


def _parse_graphify(repo_name: str, raw: Any) -> GraphifyConfig:
    if raw is None:
        return GraphifyConfig()
    if raw is False:
        return GraphifyConfig(enabled=False)
    if raw is True:
        return GraphifyConfig()
    if isinstance(raw, str):
        out = raw
    elif isinstance(raw, dict):
        out = str(raw.get("out") or "graphify-out")
        enabled = bool(raw.get("enabled", True))
        _require_relative_dir(f"Repository {repo_name} graphify.out", out)
        return GraphifyConfig(out=out, enabled=enabled)
    else:
        raise HarnessError(
            f"Repository {repo_name} graphify must be a mapping, path, or boolean"
        )
    _require_relative_dir(f"Repository {repo_name} graphify.out", out)
    return GraphifyConfig(out=out)


def _require_relative_dir(label: str, value: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise HarnessError(f"{label} must be a relative path inside the repo: {value}")


def load_stack(
    path: Path, repo_names: set[str]
) -> tuple[list[Workspace], JiraSettings]:
    raw = _read_yaml(path)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise HarnessError(f"Stack catalog root must be a mapping: {path}")
    if raw.get("repos") or raw.get("repositories"):
        raise HarnessError(
            f"{path} must not list repositories. Put them in {REPOS_RELATIVE}."
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
        tags = _as_list(item.get("tags"))
        unknown = [folder for folder in folders if folder not in repo_names]
        if unknown:
            raise HarnessError(
                f"Workspace {workspace_id} references unknown repo name(s): "
                + ", ".join(unknown)
                + f". Add them to {REPOS_RELATIVE}."
            )
        workspaces.append(
            Workspace(
                id=workspace_id,
                name=str(item.get("name") or workspace_id),
                description=str(item.get("description") or ""),
                folders=folders,
                tags=tags,
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
    configured_fields = _as_list(jira_raw.get("fields"))
    jira = JiraSettings(
        fields=configured_fields or list(DEFAULT_OUTPUT_FIELDS),
        extra_fields=_as_list(jira_raw.get("extra_fields")),
        field_aliases={str(key): str(value) for key, value in aliases.items()},
        include_comments=bool(jira_raw.get("include_comments", True)),
        max_comments=int(jira_raw.get("max_comments") or 15),
    )

    fallbacks = [workspace.id for workspace in workspaces if workspace.fallback]
    if len(fallbacks) > 1:
        raise HarnessError(
            "Only one workspace can be fallback=true; found: " + ", ".join(fallbacks)
        )

    return workspaces, jira


def load_personal_workspaces(
    harness_root: Path,
    repo_names: set[str],
    reserved_ids: set[str] | None = None,
) -> list[Workspace]:
    """Load local-only workspaces from workspaces/personal/ (gitignored)."""
    directory = Path(harness_root) / PERSONAL_WORKSPACES_DIR
    if not directory.is_dir():
        return []
    reserved = set(reserved_ids or ())
    workspaces: list[Workspace] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.code-workspace")):
        workspace = parse_personal_workspace(path, repo_names)
        if workspace is None:
            continue
        if workspace.id in reserved or workspace.id in seen:
            continue
        seen.add(workspace.id)
        workspaces.append(workspace)
    return workspaces


def parse_personal_workspace(path: Path, repo_names: set[str]) -> Workspace | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    meta = raw.get("harness") if isinstance(raw.get("harness"), dict) else {}
    workspace_id = str(meta.get("id") or path.stem).strip()
    if not workspace_id:
        return None
    folders = _as_list(meta.get("folders"))
    if not folders:
        folders = [
            str(folder.get("name"))
            for folder in (raw.get("folders") or [])
            if isinstance(folder, dict)
            and folder.get("name")
            and str(folder.get("name")) != "harness"
        ]
    folders = [name for name in folders if name in repo_names]
    include_harness = meta.get("include_harness")
    if include_harness is None:
        include_harness = any(
            isinstance(folder, dict) and folder.get("name") == "harness"
            for folder in (raw.get("folders") or [])
        )
    return Workspace(
        id=workspace_id,
        name=str(meta.get("name") or workspace_id.replace("-", " ").replace("_", " ").title()),
        description=str(meta.get("description") or ""),
        folders=folders,
        tags=_as_list(meta.get("tags")),
        include_harness=bool(include_harness),
        fallback=False,
        personal=True,
    )


def catalog_to_dict(catalog: Catalog, harness_root: Path) -> dict[str, Any]:
    sibling_root = catalog.sibling_root(harness_root)
    return {
        "source": str(catalog.source),
        "repos_source": str(catalog.repos_source),
        "parent_dir": catalog.parent_dir,
        "sibling_root": str(sibling_root),
        "repos": [
            {
                "name": repo.name,
                "url": repo.url,
                "path": repo.path,
                "group": repo.group,
                "resolved_path": str(catalog.repo_path(harness_root, repo)),
                "default_branch": repo.default_branch,
                "description": repo.description,
                "tags": repo.tags,
                "enabled": repo.enabled,
                "placeholder": repo.is_placeholder,
                "graphify": {
                    "out": repo.graphify.out,
                    "enabled": repo.graphify.enabled,
                },
                "start": repo.start.to_dict(),
            }
            for repo in catalog.repos
        ],
        "workspaces": [
            {
                "id": workspace.id,
                "name": workspace.name,
                "description": workspace.description,
                "folders": catalog.workspace_repo_names(workspace),
                "include_harness": workspace.include_harness,
                "fallback": workspace.fallback,
                "personal": workspace.personal,
                "file": str(catalog.workspace_file(harness_root, workspace)),
                "start_file": str(catalog.workspace_start_file(harness_root, workspace)),
                "start_plan": catalog.workspace_start_file(
                    harness_root, workspace
                ).is_file(),
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
        "jira": catalog.jira.schema(),
        "templates_source": str(catalog.templates_source) if catalog.templates_source else None,
        "templates": [
            {
                "name": template.name,
                "url": template.url,
                "tags": template.tags,
                "description": template.description,
                "language": template.language,
                "kind": template.kind,
                "default_branch": template.default_branch,
                "enabled": template.enabled,
                "placeholder": template.is_placeholder,
            }
            for template in catalog.templates
        ],
    }

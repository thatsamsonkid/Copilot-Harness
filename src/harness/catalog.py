from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from harness import HarnessError
from harness.jira_fields import DEFAULT_OUTPUT_FIELDS, JiraSettings
from harness.paths import ENV_RELATIVE, REPOS_RELATIVE, STACK_RELATIVE, TEMPLATES_RELATIVE

if TYPE_CHECKING:
    from harness.envspec import EnvVar
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
class Repo:
    name: str
    url: str
    path: str
    default_branch: str = "main"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    enabled: bool = True
    graphify: GraphifyConfig = field(default_factory=GraphifyConfig)

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
    env: list[str] = field(default_factory=list)
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
    env_vars: list[EnvVar] = field(default_factory=list)
    env_source: Path | None = None

    def workspace_env_names(self, workspace: Workspace | str) -> list[str]:
        if isinstance(workspace, str):
            workspace = self.workspace(workspace)
        return list(workspace.env)

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
        return harness_root / "workspaces" / f"{workspace.id}.code-workspace"


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
    env_file = harness_root / ENV_RELATIVE
    repos, parent_dir = load_repositories(repos_file)
    workspaces, jira = load_stack(stack_file, {repo.name for repo in repos})
    templates = load_templates(templates_file)
    from harness.envspec import load_env_spec, validate_env_spec

    env_vars, env_source = load_env_spec(env_file)
    validate_env_spec(
        env_vars,
        {workspace.id for workspace in workspaces},
        {workspace.id: workspace.env for workspace in workspaces},
        source=env_source,
    )
    return Catalog(
        parent_dir=parent_dir,
        repos=repos,
        workspaces=workspaces,
        jira=jira,
        source=stack_file,
        repos_source=repos_file,
        templates=templates,
        templates_source=templates_file,
        env_vars=env_vars,
        env_source=env_source,
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
    repo_path = str(item.get("path") or name)
    if Path(repo_path).is_absolute() or ".." in Path(repo_path).parts:
        raise HarnessError(
            f"Repo path must be a single sibling folder name: {repo_path}"
        )
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
                env=_as_list(item.get("env")),
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
                "env": workspace.env,
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
        "jira": catalog.jira.schema(),
        "env_source": str(catalog.env_source) if catalog.env_source else None,
        "env": [
            {
                "name": variable.name,
                "secret": variable.secret,
                "required": variable.required,
                "aliases": list(variable.aliases),
                "workspaces": list(variable.workspaces),
                "docs": variable.docs or None,
                "hint": variable.hint or None,
                "store": "keychain" if variable.secret else "env",
            }
            for variable in catalog.env_vars
        ],
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

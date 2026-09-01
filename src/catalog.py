from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from goat import GoatError
from goat.bruno_fields import (
    DEFAULT_ENV as BRUNO_DEFAULT_ENV,
    DEFAULT_OUTPUT_FIELDS as BRUNO_DEFAULT_OUTPUT_FIELDS,
    DEFAULT_SERVICES_FILE as BRUNO_DEFAULT_SERVICES_FILE,
    DEFAULT_SHAPES as BRUNO_DEFAULT_SHAPES,
    DEFAULT_TAGS as BRUNO_DEFAULT_TAGS,
    DEFAULT_WORKFLOWS_FILE as BRUNO_DEFAULT_WORKFLOWS_FILE,
    BrunoService,
    BrunoSettings,
)
from goat.figma_fields import (
    DEFAULT_COMMENT_FIELDS as FIGMA_DEFAULT_COMMENT_FIELDS,
    DEFAULT_DEPTH as FIGMA_DEFAULT_DEPTH,
    DEFAULT_FORMAT as FIGMA_DEFAULT_FORMAT,
    DEFAULT_MAX_COMMENTS as FIGMA_DEFAULT_MAX_COMMENTS,
    DEFAULT_MAX_DEPTH as FIGMA_DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_IDS as FIGMA_DEFAULT_MAX_IDS,
    DEFAULT_OUTPUT_FIELDS as FIGMA_DEFAULT_OUTPUT_FIELDS,
    DEFAULT_SCALE as FIGMA_DEFAULT_SCALE,
    DEFAULT_SHAPES as FIGMA_DEFAULT_SHAPES,
    ALLOWED_FORMATS as FIGMA_ALLOWED_FORMATS,
    FigmaSettings,
)
from goat.jira_fields import (
    DEFAULT_OUTPUT_FIELDS,
    DEFAULT_SEARCH_FIELDS,
    DEFAULT_SHAPES,
    JiraSettings,
)
from goat.paths import (
    ENV_RELATIVE,
    REPOS_LOCAL_RELATIVE,
    REPOS_RELATIVE,
    STACK_RELATIVE,
    TEMPLATES_RELATIVE,
    WORKSPACES_DIR,
)

if TYPE_CHECKING:
    from goat.envspec import EnvVar
    from goat.templates import Template


KIT_FOLDER_NAMES = frozenset({"goat", "coboose"})
WORKSPACE_META_KEYS = ("goat", "coboose")


def workspace_document_meta(raw: dict[str, Any]) -> dict[str, Any]:
    """Read generated workspace metadata. Accepts the current `goat` key and the legacy `coboose` key."""
    for key in WORKSPACE_META_KEYS:
        meta = raw.get(key)
        if isinstance(meta, dict):
            return meta
    return {}


def include_kit_from_mapping(item: dict[str, Any], default: bool = True) -> bool:
    """Whether a workspace includes this kit repo. Accepts `include_goat` and legacy `include_coboose`."""
    if "include_goat" in item:
        return bool(item.get("include_goat"))
    if "include_coboose" in item:
        return bool(item.get("include_coboose"))
    return default


def is_kit_folder_name(name: Any) -> bool:
    return str(name) in KIT_FOLDER_NAMES


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise GoatError(f"Expected a list or string, got {type(value).__name__}")


def read_yaml(path: Path) -> Any:
    if not path.exists():
        raise GoatError(f"File not found: {path}")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise GoatError(f"Invalid YAML in {path}: {exc}") from exc


_as_list = as_list
_read_yaml = read_yaml


def _positive_int(value: Any, default: int, label: str) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise GoatError(f"{label} must be a positive integer") from exc
    if parsed < 1:
        raise GoatError(f"{label} must be a positive integer")
    return parsed


def _as_shapes(
    value: Any,
    *,
    defaults: dict[str, tuple[str, ...] | list[str]],
    label: str,
) -> dict[str, list[str]]:
    shapes = {key: list(items) for key, items in defaults.items()}
    if value is None:
        return shapes
    if not isinstance(value, dict):
        raise GoatError(f"{label} must be a mapping of field name to nested keys")
    for key, items in value.items():
        shapes[str(key)] = _as_list(items)
    return shapes


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
    group: str = ""
    knowledge_dirs: tuple[str, ...] = ()

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
    include_goat: bool = True
    fallback: bool = False
    env: list[str] = field(default_factory=list)
    match: WorkspaceMatch = field(default_factory=WorkspaceMatch)


@dataclass(frozen=True)
class Catalog:
    parent_dir: str
    repos: list[Repo]
    workspaces: list[Workspace]
    jira: JiraSettings
    figma: FigmaSettings
    bruno: BrunoSettings
    source: Path
    repos_source: Path
    templates: list[Template] = field(default_factory=list)
    templates_source: Path | None = None
    env_vars: list[EnvVar] = field(default_factory=list)
    env_source: Path | None = None
    local_paths: dict[str, str] = field(default_factory=dict)
    local_search: list[str] = field(default_factory=list)
    local_source: Path | None = None

    def workspace_env_names(self, workspace: Workspace | str) -> list[str]:
        if isinstance(workspace, str):
            workspace = self.workspace(workspace)
        return list(workspace.env)

    def repo(self, repo_id: str) -> Repo:
        for repo in self.repos:
            if repo.name == repo_id:
                return repo
        raise GoatError(f"Unknown repo name: {repo_id}")

    def template(self, template_id: str):
        from goat.templates import get_template

        return get_template(self.templates, template_id)

    def workspace(self, workspace_id: str) -> Workspace:
        for workspace in self.workspaces:
            if workspace.id == workspace_id:
                return workspace
        raise GoatError(f"Unknown workspace id: {workspace_id}")

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
                raise GoatError(
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

    def sibling_root(self, goat_root: Path) -> Path:
        return (goat_root / self.parent_dir).resolve()

    def require_safe_sibling_root(self, goat_root: Path) -> Path:
        root = self.sibling_root(goat_root)
        if root == Path(root.anchor):
            raise GoatError(
                f"parent_dir resolves to the filesystem root ({root}). "
                "Keep Goat in a project folder so clones land as siblings, not in /."
            )
        return root

    def expected_repo_path(self, goat_root: Path, repo: Repo | str) -> Path:
        if isinstance(repo, str):
            repo = self.repo(repo)
        return self.sibling_root(goat_root) / repo.path

    def is_mapped(self, repo: Repo | str) -> bool:
        name = repo if isinstance(repo, str) else repo.name
        return name in self.local_paths

    def repo_path(self, goat_root: Path, repo: Repo | str) -> Path:
        if isinstance(repo, str):
            repo = self.repo(repo)
        override = self.local_paths.get(repo.name)
        if override:
            return resolve_local_clone_path(goat_root, override)
        return self.expected_repo_path(goat_root, repo)

    def workspace_file(self, goat_root: Path, workspace: Workspace | str) -> Path:
        if isinstance(workspace, str):
            workspace = self.workspace(workspace)
        return goat_root / WORKSPACES_DIR / f"{workspace.id}.code-workspace"

    def workspace_start_file(self, goat_root: Path, workspace: Workspace | str) -> Path:
        """YAML start sequence saved next to the .code-workspace file."""
        workspace_file = self.workspace_file(goat_root, workspace)
        return workspace_file.with_name(f"{workspace_file.stem}.start.yml")


def load_catalog(
    goat_root: Path,
    *,
    stack_path: Path | None = None,
    repos_path: Path | None = None,
    templates_path: Path | None = None,
) -> Catalog:
    from goat.templates import load_templates

    goat_root = Path(goat_root)
    repos_file = Path(repos_path) if repos_path else goat_root / REPOS_RELATIVE
    stack_file = Path(stack_path) if stack_path else goat_root / STACK_RELATIVE
    templates_file = (
        Path(templates_path) if templates_path else goat_root / TEMPLATES_RELATIVE
    )
    env_file = goat_root / ENV_RELATIVE
    repos, parent_dir = load_repositories(repos_file)
    repo_names = {repo.name for repo in repos}
    workspaces, jira, figma, bruno = load_stack(stack_file, repo_names)
    templates = load_templates(templates_file)
    from goat.envspec import load_env_spec, validate_env_spec

    env_vars, env_source = load_env_spec(env_file)
    validate_env_spec(
        env_vars,
        {workspace.id for workspace in workspaces},
        {workspace.id: workspace.env for workspace in workspaces},
        source=env_source,
    )
    local_file = goat_root / REPOS_LOCAL_RELATIVE
    local_paths, local_search = load_local_overlay(local_file, repo_names, goat_root)
    catalog = Catalog(
        parent_dir=parent_dir,
        repos=repos,
        workspaces=workspaces,
        jira=jira,
        figma=figma,
        bruno=bruno,
        source=stack_file,
        repos_source=repos_file,
        templates=templates,
        templates_source=templates_file,
        env_vars=env_vars,
        env_source=env_source,
        local_paths=local_paths,
        local_search=local_search,
        local_source=local_file if local_file.exists() else None,
    )
    _assert_unique_resolved_paths(catalog, goat_root)
    return catalog


def resolve_local_clone_path(goat_root: Path, raw: str) -> Path:
    text = str(raw).strip()
    if not text:
        raise GoatError("Local clone path is empty")
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = Path(goat_root) / path
    return path.resolve()


def refuse_local_clone_in_goat(dest: Path, goat_root: Path) -> None:
    dest_resolved = dest.resolve()
    goat = Path(goat_root).resolve()
    if dest_resolved == goat or goat in dest_resolved.parents:
        raise GoatError(
            f"Refusing local overlay path inside the Goat repo: {dest}. "
            "Keep product clones outside this repository."
        )


def load_local_overlay(
    path: Path, repo_names: set[str], goat_root: Path
) -> tuple[dict[str, str], list[str]]:
    if not path.exists():
        return {}, []
    raw = _read_yaml(path)
    if raw is None:
        return {}, []
    if not isinstance(raw, dict):
        raise GoatError(f"{path} must be a mapping with a paths: table")
    search = as_list(raw.get("search"))
    paths_raw = raw.get("paths")
    if paths_raw is None:
        reserved = {"paths", "search"}
        leftover = {key: value for key, value in raw.items() if key not in reserved}
        if leftover and all(isinstance(value, (str, int)) for value in leftover.values()):
            raise GoatError(
                f"{path} must use a paths: table (paths:\\n  frontend: ~/code/shop-web)."
            )
        return {}, search
    if not isinstance(paths_raw, dict):
        raise GoatError(f"{path} paths: must be a mapping of repo name to directory")
    paths: dict[str, str] = {}
    resolved: dict[str, Path] = {}
    for name, dest in paths_raw.items():
        name = str(name)
        if name not in repo_names:
            raise GoatError(
                f"{path} maps unknown repo {name!r}. "
                "Names must match repositories.yml."
            )
        if dest is None or str(dest).strip() == "":
            raise GoatError(f"{path} path for {name} is empty")
        dest_text = str(dest).strip()
        target = resolve_local_clone_path(goat_root, dest_text)
        refuse_local_clone_in_goat(target, goat_root)
        for other, other_path in resolved.items():
            if other_path == target:
                raise GoatError(
                    f"{path} maps {name} and {other} to the same directory: {target}"
                )
        paths[name] = dest_text
        resolved[name] = target
    return paths, search


def _assert_unique_resolved_paths(catalog: Catalog, goat_root: Path) -> None:
    seen: dict[Path, str] = {}
    for repo in catalog.repos:
        path = catalog.repo_path(goat_root, repo)
        other = seen.get(path)
        if other:
            raise GoatError(
                f"Repositories {other} and {repo.name} resolve to the same "
                f"directory: {path}"
            )
        seen[path] = repo.name


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
            raise GoatError(
                f"{path} uses `repos:`. Rename that key to `repositories:` "
                "and give each entry name, url, and tags."
            )
        parent_dir = str(raw.get("parent_dir") or "..")
        items = raw.get("repositories") or []
    else:
        raise GoatError(f"{path} must be a mapping or a list of repositories")

    repos: list[Repo] = []
    seen_names: set[str] = set()
    seen_paths: set[str] = set()
    for item in items:
        repo = _parse_repo(item)
        if repo.name in seen_names:
            raise GoatError(f"Duplicate repository name: {repo.name}")
        if repo.path in seen_paths:
            raise GoatError(f"Duplicate repository path: {repo.path}")
        seen_names.add(repo.name)
        seen_paths.add(repo.path)
        repos.append(repo)
    _assert_no_path_collisions(repos)
    if not repos:
        raise GoatError(
            f"{path} has no repositories. Add entries with name, url, and tags."
        )
    return repos, parent_dir


def _parse_repo(item: Any) -> Repo:
    if not isinstance(item, dict):
        raise GoatError("Each repository entry must be a mapping")
    name = item.get("name") or item.get("id")
    url = item.get("url") or item.get("clone_url") or item.get("git")
    if not name or not url:
        raise GoatError("Each repository needs name and url (GitHub clone URL)")
    name = str(name)
    validate_repo_name(name)
    repo_path, group = resolve_repo_layout(name, item.get("path"), item.get("group"))
    tags = _as_list(item.get("tags"))
    if not tags:
        raise GoatError(f"Repository {name} needs at least one tag")
    if item.get("start") is not None:
        raise GoatError(
            f"Repository {name} has a start: block. repositories.yml no longer "
            "owns start commands. Discover once with "
            "`goat start --workspace <id>`, then save "
            "workspaces/<id>.start.yml (or edit that file)."
        )
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
        knowledge_dirs=_parse_knowledge_dirs(name, item.get("knowledge")),
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
        raise GoatError(
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
            raise GoatError(
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
        raise GoatError("Project --name is required")
    dest_name = dest_name.replace("\\", "/")
    group = (group or "").strip().replace("\\", "/")
    if group:
        group = normalize_clone_relpath(group, "Project group")
        if "/" in dest_name:
            repo_path = normalize_clone_relpath(dest_name, "Project path")
            if repo_path != group and not repo_path.startswith(f"{group}/"):
                raise GoatError(
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
        raise GoatError(
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
                raise GoatError(
                    f"Repository paths collide: {repo.path!r} ({repo.name}) and "
                    f"{other.path!r} ({other.name}). One clone cannot live inside another."
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
        raise GoatError(
            f"Repository {repo_name} graphify must be a mapping, path, or boolean"
        )
    _require_relative_dir(f"Repository {repo_name} graphify.out", out)
    return GraphifyConfig(out=out)


def _parse_knowledge_dirs(repo_name: str, raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, list):
        dirs = _as_list(raw)
    elif isinstance(raw, dict):
        dirs = _as_list(raw.get("dirs"))
    else:
        raise GoatError(
            f"Repository {repo_name} knowledge must be a mapping or list of dirs"
        )
    for relative in dirs:
        _require_relative_dir(f"Repository {repo_name} knowledge dir", relative)
    return tuple(dirs)


def _require_relative_dir(label: str, value: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise GoatError(f"{label} must be a relative path inside the repo: {value}")


def load_stack(
    path: Path, repo_names: set[str]
) -> tuple[list[Workspace], JiraSettings, FigmaSettings, BrunoSettings]:
    raw = _read_yaml(path)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise GoatError(f"Stack catalog root must be a mapping: {path}")
    if raw.get("repos") or raw.get("repositories"):
        raise GoatError(
            f"{path} must not list repositories. Put them in {REPOS_RELATIVE}."
        )

    workspaces: list[Workspace] = []
    seen_workspace_ids: set[str] = set()
    for item in raw.get("workspaces") or []:
        if not isinstance(item, dict) or "id" not in item:
            raise GoatError("Each workspace needs an id")
        workspace_id = str(item["id"])
        if workspace_id in seen_workspace_ids:
            raise GoatError(f"Duplicate workspace id: {workspace_id}")
        seen_workspace_ids.add(workspace_id)
        match_raw = item.get("match") or {}
        if not isinstance(match_raw, dict):
            raise GoatError(f"Workspace {workspace_id} match must be a mapping")
        folders = _as_list(item.get("folders"))
        tags = _as_list(item.get("tags"))
        unknown = [folder for folder in folders if folder not in repo_names]
        if unknown:
            raise GoatError(
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
                include_goat=include_kit_from_mapping(item),
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
        raise GoatError("jira settings must be a mapping")
    aliases = jira_raw.get("field_aliases") or {}
    if not isinstance(aliases, dict):
        raise GoatError("jira.field_aliases must be a mapping")
    configured_fields = _as_list(jira_raw.get("fields"))
    search_raw = jira_raw.get("search_fields")
    jira = JiraSettings(
        fields=configured_fields or list(DEFAULT_OUTPUT_FIELDS),
        extra_fields=_as_list(jira_raw.get("extra_fields")),
        field_aliases={str(key): str(value) for key, value in aliases.items()},
        include_comments=bool(jira_raw.get("include_comments", True)),
        max_comments=int(jira_raw.get("max_comments") or 15),
        shapes=_as_shapes(jira_raw.get("shapes"), defaults=DEFAULT_SHAPES, label="jira.shapes"),
        search_fields=(
            _as_list(search_raw) if search_raw is not None else list(DEFAULT_SEARCH_FIELDS)
        ),
        drop_empty=bool(jira_raw.get("drop_empty", True)),
    )

    fallbacks = [workspace.id for workspace in workspaces if workspace.fallback]
    if len(fallbacks) > 1:
        raise GoatError(
            "Only one workspace can be fallback=true; found: " + ", ".join(fallbacks)
        )

    return workspaces, jira, _load_figma(raw.get("figma")), _load_bruno(
        raw.get("bruno"), repo_names
    )


def _load_figma(raw: Any) -> FigmaSettings:
    data = raw or {}
    if not isinstance(data, dict):
        raise GoatError("figma settings must be a mapping")
    image_format = str(data.get("default_format") or FIGMA_DEFAULT_FORMAT).lower()
    if image_format not in FIGMA_ALLOWED_FORMATS:
        raise GoatError(
            f"figma.default_format must be one of: {', '.join(FIGMA_ALLOWED_FORMATS)}"
        )
    try:
        scale = float(data.get("default_scale") if data.get("default_scale") is not None else FIGMA_DEFAULT_SCALE)
    except (TypeError, ValueError) as exc:
        raise GoatError("figma.default_scale must be a number between 0.01 and 4") from exc
    if scale < 0.01 or scale > 4:
        raise GoatError("figma.default_scale must be a number between 0.01 and 4")
    max_ids = _positive_int(data.get("max_ids"), FIGMA_DEFAULT_MAX_IDS, "figma.max_ids")
    max_comments = _positive_int(
        data.get("max_comments"), FIGMA_DEFAULT_MAX_COMMENTS, "figma.max_comments"
    )
    default_depth = _positive_int(
        data.get("default_depth"), FIGMA_DEFAULT_DEPTH, "figma.default_depth"
    )
    max_depth = _positive_int(data.get("max_depth"), FIGMA_DEFAULT_MAX_DEPTH, "figma.max_depth")
    if default_depth > max_depth:
        raise GoatError("figma.default_depth cannot be greater than figma.max_depth")
    configured_fields = _as_list(data.get("fields"))
    configured_comment_fields = _as_list(data.get("comment_fields"))
    return FigmaSettings(
        fields=configured_fields or list(FIGMA_DEFAULT_OUTPUT_FIELDS),
        comment_fields=configured_comment_fields or list(FIGMA_DEFAULT_COMMENT_FIELDS),
        shapes=_as_shapes(
            data.get("shapes"),
            defaults=FIGMA_DEFAULT_SHAPES,
            label="figma.shapes",
        ),
        default_format=image_format,
        default_scale=scale,
        max_ids=max_ids,
        include_comments=bool(data.get("include_comments", True)),
        max_comments=max_comments,
        default_depth=default_depth,
        max_depth=max_depth,
        drop_empty=bool(data.get("drop_empty", True)),
    )


def _load_bruno(raw: Any, repo_names: set[str]) -> BrunoSettings:
    data = raw or {}
    if not isinstance(data, dict):
        raise GoatError("bruno settings must be a mapping")
    repos = _as_list(data.get("repos"))
    unknown = [name for name in repos if name not in repo_names]
    if unknown:
        raise GoatError(
            "bruno.repos references unknown repo name(s): "
            + ", ".join(unknown)
            + f". Add them to {REPOS_RELATIVE}."
        )
    tags = _as_list(data.get("tags"))
    if not tags and data.get("tags") is None:
        tags = list(BRUNO_DEFAULT_TAGS)
    workflows_file = str(data.get("workflows_file") or BRUNO_DEFAULT_WORKFLOWS_FILE)
    services_file = str(data.get("services_file") or BRUNO_DEFAULT_SERVICES_FILE)
    for label, value in (
        ("bruno.workflows_file", workflows_file),
        ("bruno.services_file", services_file),
    ):
        _require_relative_dir(label, value)
    configured_fields = _as_list(data.get("fields"))
    return BrunoSettings(
        repos=repos,
        tags=tags,
        default_env=str(data.get("default_env") or BRUNO_DEFAULT_ENV),
        workflows_file=workflows_file,
        services_file=services_file,
        services=_parse_bruno_services(data.get("services"), repo_names),
        fields=configured_fields or list(BRUNO_DEFAULT_OUTPUT_FIELDS),
        shapes=_as_shapes(
            data.get("shapes"),
            defaults=BRUNO_DEFAULT_SHAPES,
            label="bruno.shapes",
        ),
        drop_empty=bool(data.get("drop_empty", True)),
    )


def _parse_bruno_services(raw: Any, repo_names: set[str]) -> list[BrunoService]:
    if raw is None:
        return []
    items: list[Any]
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = [{"id": key, **value} if isinstance(value, dict) else {"id": key} for key, value in raw.items()]
    else:
        raise GoatError("bruno.services must be a list or a mapping")
    services: list[BrunoService] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise GoatError("Each bruno.services entry must be a mapping")
        service_id = str(item.get("id") or item.get("name") or "").strip()
        if not service_id:
            raise GoatError("Each bruno.services entry needs an id")
        if service_id in seen:
            raise GoatError(f"Duplicate bruno.services id: {service_id}")
        seen.add(service_id)
        repo = str(item.get("repo") or "").strip()
        if repo and repo not in repo_names:
            raise GoatError(
                f"bruno.services {service_id} references unknown repo {repo!r}"
            )
        services.append(
            BrunoService(
                id=service_id,
                collection=str(item.get("collection") or ""),
                env=str(item.get("env") or ""),
                description=str(item.get("description") or ""),
                repo=repo,
            )
        )
    return services



def catalog_to_dict(catalog: Catalog, goat_root: Path) -> dict[str, Any]:
    sibling_root = catalog.sibling_root(goat_root)
    return {
        "source": str(catalog.source),
        "repos_source": str(catalog.repos_source),
        "local_source": str(catalog.local_source) if catalog.local_source else None,
        "local_paths": dict(catalog.local_paths),
        "local_search": list(catalog.local_search),
        "parent_dir": catalog.parent_dir,
        "sibling_root": str(sibling_root),
        "repos": [
            {
                "name": repo.name,
                "url": repo.url,
                "path": repo.path,
                "group": repo.group,
                "expected_path": str(catalog.expected_repo_path(goat_root, repo)),
                "resolved_path": str(catalog.repo_path(goat_root, repo)),
                "mapped": catalog.is_mapped(repo),
                "default_branch": repo.default_branch,
                "description": repo.description,
                "tags": repo.tags,
                "enabled": repo.enabled,
                "placeholder": repo.is_placeholder,
                "graphify": {
                    "out": repo.graphify.out,
                    "enabled": repo.graphify.enabled,
                },
                "knowledge_dirs": list(repo.knowledge_dirs),
            }
            for repo in catalog.repos
        ],
        "workspaces": [
            {
                "id": workspace.id,
                "name": workspace.name,
                "description": workspace.description,
                "folders": catalog.workspace_repo_names(workspace),
                "include_goat": workspace.include_goat,
                "fallback": workspace.fallback,
                "env": workspace.env,
                "file": str(catalog.workspace_file(goat_root, workspace)),
                "start_file": str(catalog.workspace_start_file(goat_root, workspace)),
                "start_plan": catalog.workspace_start_file(
                    goat_root, workspace
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
        "figma": catalog.figma.schema(),
        "bruno": catalog.bruno.schema(),
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

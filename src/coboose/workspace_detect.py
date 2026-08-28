from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from coboose import CobooseError
from coboose.catalog import Catalog, Repo, Workspace

WORKSPACE_ID_ENV = "COBOOSE_WORKSPACE"
WORKSPACE_FILE_ENV = "COBOOSE_WORKSPACE_FILE"

_UNRESOLVED = ("${workspaceFile}", "${workspaceFolder}")


@dataclass(frozen=True)
class WorkspaceScope:
    id: str | None
    source: str
    detected: bool
    scope: str
    repos: list[str]
    file: str | None
    name: str | None
    personal: bool | None
    detail: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "personal": self.personal,
            "detected": self.detected,
            "source": self.source,
            "scope": self.scope,
            "repos": list(self.repos),
            "file": self.file,
            "detail": self.detail,
        }


def resolve_workspace_scope(
    catalog: Catalog,
    coboose_root: Path,
    *,
    workspace_id: str | None = None,
    all_repos: bool = False,
    workspace_file: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> WorkspaceScope:
    """Resolve which feature workspace the CLI should stay inside.

    Precedence: ``--all``, then ``--workspace``, then ``--file``, then
    ``COBOOSE_WORKSPACE`` / ``COBOOSE_WORKSPACE_FILE``. When nothing is
    detected, the scope is every enabled repo so CI and a single-folder
    Coboose window keep working.
    """
    if all_repos and workspace_id:
        raise CobooseError("Do not combine --workspace with --all.")
    env = environ if environ is not None else os.environ
    enabled = [repo.name for repo in catalog.enabled_repos()]

    if all_repos:
        return WorkspaceScope(
            id=None,
            source="all",
            detected=False,
            scope="all",
            repos=enabled,
            file=None,
            name=None,
            personal=None,
            detail=(
                "Including every enabled repositories.yml repo (--all). "
                "Do not use this while a feature workspace is open unless "
                "the user asked for the full catalog."
            ),
        )

    if workspace_id:
        return _scope_for_workspace(
            catalog,
            coboose_root,
            workspace_id,
            source="flag",
            detail=f"Using workspace {workspace_id} from --workspace.",
        )

    if workspace_file:
        return _scope_from_file(
            catalog,
            coboose_root,
            Path(workspace_file),
            source="file",
        )

    env_id = _clean_env(env.get(WORKSPACE_ID_ENV))
    if env_id:
        return _scope_for_workspace(
            catalog,
            coboose_root,
            env_id,
            source="env",
            detail=(
                f"Using workspace {env_id} from {WORKSPACE_ID_ENV}. "
                "Stay inside these repos unless the user asked for --all."
            ),
        )

    env_file = _clean_env(env.get(WORKSPACE_FILE_ENV))
    if env_file and not _is_unresolved(env_file):
        return _scope_from_file(
            catalog,
            coboose_root,
            Path(env_file),
            source="file",
        )

    return WorkspaceScope(
        id=None,
        source="none",
        detected=False,
        scope="all",
        repos=enabled,
        file=None,
        name=None,
        personal=None,
        detail=(
            "No feature workspace is open. "
            f"{WORKSPACE_ID_ENV} is unset. "
            "Pass --workspace <id> or open a generated "
            "workspaces/<id>.code-workspace so Copilot stays on those roots. "
            "Do not treat every clone under parent_dir as in scope."
        ),
    )


def scoped_repos(
    catalog: Catalog,
    scope: WorkspaceScope,
    *,
    only: list[str] | None = None,
) -> list[Repo]:
    """Return enabled repos inside ``scope``, optionally filtered by ``only``."""
    if scope.id:
        allowed = catalog.workspace_repo_names(scope.id)
    else:
        allowed = [repo.name for repo in catalog.enabled_repos()]
    if only:
        unknown = [name for name in only if name not in {repo.name for repo in catalog.repos}]
        if unknown:
            raise CobooseError("Unknown repo name(s): " + ", ".join(sorted(unknown)))
        outside = [name for name in only if name not in allowed]
        if outside and scope.id:
            raise CobooseError(
                ", ".join(outside)
                + f" is not in workspace {scope.id}. "
                "Pass --all to include repos outside this workspace."
            )
        names = [name for name in only if name in allowed]
    else:
        names = allowed
    return [catalog.repo(name) for name in names if catalog.repo(name).enabled]


def current_workspace_payload(
    catalog: Catalog,
    coboose_root: Path,
    *,
    workspace_id: str | None = None,
    all_repos: bool = False,
    workspace_file: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    scope = resolve_workspace_scope(
        catalog,
        coboose_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        workspace_file=workspace_file,
        environ=environ,
    )
    return scope.as_payload()


def _scope_for_workspace(
    catalog: Catalog,
    coboose_root: Path,
    workspace_id: str,
    *,
    source: str,
    detail: str,
) -> WorkspaceScope:
    workspace = catalog.workspace(workspace_id)
    path = catalog.workspace_file(coboose_root, workspace)
    return WorkspaceScope(
        id=workspace.id,
        source=source,
        detected=True,
        scope="workspace",
        repos=catalog.workspace_repo_names(workspace),
        file=str(path),
        name=workspace.name,
        personal=workspace.personal,
        detail=detail,
    )


def _scope_from_file(
    catalog: Catalog,
    coboose_root: Path,
    path: Path,
    *,
    source: str,
) -> WorkspaceScope:
    resolved = path.expanduser()
    if not resolved.exists():
        raise CobooseError(f"Workspace file missing: {resolved}")
    resolved = resolved.resolve()
    matched = _workspace_matching_file(catalog, coboose_root, resolved)
    if matched is None:
        raise CobooseError(
            f"Could not match {resolved} to a catalog workspace. "
            "Pass --workspace <id>."
        )
    return _scope_for_workspace(
        catalog,
        coboose_root,
        matched.id,
        source=source,
        detail=f"Using workspace {matched.id} from {resolved}.",
    )


def _workspace_matching_file(
    catalog: Catalog, coboose_root: Path, path: Path
) -> Workspace | None:
    for workspace in catalog.workspaces:
        candidate = catalog.workspace_file(coboose_root, workspace)
        try:
            if candidate.resolve() == path:
                return workspace
        except OSError:
            continue
    meta_id = _id_from_workspace_file(path)
    if meta_id:
        try:
            return catalog.workspace(meta_id)
        except CobooseError:
            pass
    try:
        return catalog.workspace(path.stem)
    except CobooseError:
        return None


def _id_from_workspace_file(path: Path) -> str | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    meta = raw.get("coboose")
    if isinstance(meta, dict) and meta.get("id"):
        return str(meta["id"]).strip() or None
    return None


def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned or _is_unresolved(cleaned):
        return None
    return cleaned


def _is_unresolved(value: str) -> bool:
    stripped = value.strip()
    return stripped in _UNRESOLVED or (
        stripped.startswith("${") and stripped.endswith("}")
    )

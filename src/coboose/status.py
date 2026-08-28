from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from coboose.catalog import Catalog
from coboose.context import inspect_repo
from coboose.gitinfo import inspect_git
from coboose.workspace_detect import resolve_workspace_scope, scoped_repos


def collect_status(
    catalog: Catalog,
    coboose_root: Path,
    *,
    only: list[str] | None = None,
    cwd: Path | None = None,
    workspace_id: str | None = None,
    all_repos: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    scope = resolve_workspace_scope(
        catalog,
        coboose_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    repos = []
    dirty = []
    behind = []
    for repo in scoped_repos(catalog, scope, only=only):
        snapshot = inspect_repo(catalog, coboose_root, repo)
        git = inspect_git(
            catalog.repo_path(coboose_root, repo),
            default_branch=repo.default_branch,
        )
        snapshot["git"] = git
        repos.append(snapshot)
        if git.get("dirty"):
            dirty.append(repo.name)
        if (git.get("behind") or 0) > 0:
            behind.append(repo.name)

    guidance = [
        "Stay inside workspace.repos. Dirty clones that are not in this "
        "feature workspace are out of scope.",
        "Use this snapshot before planning or handing off. Do not assume siblings are clean.",
        "Create one branch and one pull request per sibling. Do not squash unrelated repos.",
        "If graphify.stale is true, offer a scoped refresh in that repo after the user agrees.",
        "Do not hand-edit files listed under tooling.generated.",
    ]
    if not scope.detected:
        guidance.insert(0, scope.detail)

    return {
        "coboose_root": str(coboose_root),
        "sibling_root": str(catalog.sibling_root(coboose_root)),
        "workspace": scope.id,
        "workspace_scope": scope.as_payload(),
        "cwd_hint": _cwd_hint(catalog, coboose_root, cwd or Path.cwd()),
        "dirty_repos": dirty,
        "behind_repos": behind,
        "repos": repos,
        "guidance": guidance,
    }


def _cwd_hint(catalog: Catalog, coboose_root: Path, cwd: Path) -> dict[str, Any]:
    resolved = cwd.resolve()
    coboose = coboose_root.resolve()
    if resolved == coboose or coboose in resolved.parents:
        return {
            "kind": "coboose",
            "detail": "cwd is the Coboose repo. Open a feature .code-workspace so sibling repos are roots.",
        }
    match = _repo_containing_cwd(catalog, coboose_root, resolved)
    if match is not None:
        return {
            "kind": "sibling",
            "repo": match.name,
            "relpath": match.path,
            "group": match.group or None,
            "detail": (
                f"cwd is the {match.name} clone ({match.path}). Open the matching "
                "workspaces/<id>.code-workspace so the Coboose repo and other "
                "clones are loaded too."
            ),
        }
    sibling_root = catalog.sibling_root(coboose_root).resolve()
    try:
        relative = resolved.relative_to(sibling_root)
    except ValueError:
        relative = None
    if relative is not None and relative.parts:
        return {
            "kind": "parent_dir",
            "relpath": relative.as_posix(),
            "detail": (
                "cwd is under parent_dir but not inside a listed clone "
                "(a group folder such as frontend/ is not a git repo). "
                "cd into the project folder or open a feature .code-workspace."
            ),
        }
    return {
        "kind": "other",
        "detail": "cwd is outside the Coboose repo and its clones.",
    }


def _repo_containing_cwd(catalog: Catalog, coboose_root: Path, cwd: Path):
    """Longest listed clone path that contains cwd (supports frontend/shop-web)."""
    matches = []
    for repo in catalog.enabled_repos():
        path = catalog.repo_path(coboose_root, repo).resolve()
        if cwd == path or path in cwd.parents:
            matches.append((len(Path(repo.path).parts), repo))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]

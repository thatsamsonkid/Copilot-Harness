from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.catalog import Catalog
from harness.context import inspect_repo
from harness.gitinfo import inspect_git


def collect_status(
    catalog: Catalog,
    harness_root: Path,
    *,
    only: list[str] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    repos = []
    dirty = []
    behind = []
    for repo in catalog.enabled_repos(only=only):
        snapshot = inspect_repo(catalog, harness_root, repo)
        git = inspect_git(
            catalog.repo_path(harness_root, repo),
            default_branch=repo.default_branch,
        )
        snapshot["git"] = git
        repos.append(snapshot)
        if git.get("dirty"):
            dirty.append(repo.name)
        if (git.get("behind") or 0) > 0:
            behind.append(repo.name)

    return {
        "harness_root": str(harness_root),
        "sibling_root": str(catalog.sibling_root(harness_root)),
        "cwd_hint": _cwd_hint(catalog, harness_root, cwd or Path.cwd()),
        "dirty_repos": dirty,
        "behind_repos": behind,
        "repos": repos,
        "guidance": [
            "Use this snapshot before planning or handing off. Do not assume siblings are clean.",
            "Create one branch and one pull request per sibling. Do not squash unrelated repos.",
            "If graphify.stale is true, offer a scoped refresh in that repo after the user agrees.",
            "Do not hand-edit files listed under tooling.generated.",
        ],
    }


def _cwd_hint(catalog: Catalog, harness_root: Path, cwd: Path) -> dict[str, Any]:
    resolved = cwd.resolve()
    harness = harness_root.resolve()
    if resolved == harness or harness in resolved.parents:
        return {
            "kind": "harness",
            "detail": "cwd is the harness. Open a feature .code-workspace so sibling repos are roots.",
        }
    sibling_root = catalog.sibling_root(harness_root).resolve()
    try:
        relative = resolved.relative_to(sibling_root)
    except ValueError:
        relative = None
    if relative is not None and relative.parts:
        folder = relative.parts[0]
        for repo in catalog.enabled_repos():
            if repo.name == folder or repo.path == folder:
                return {
                    "kind": "sibling",
                    "repo": repo.name,
                    "detail": (
                        f"cwd is the {repo.name} clone. Open the matching "
                        "workspaces/<id>.code-workspace so the harness and other "
                        "siblings are loaded too."
                    ),
                }
    for repo in catalog.enabled_repos():
        path = catalog.repo_path(harness_root, repo).resolve()
        if resolved == path or path in resolved.parents:
            return {
                "kind": "sibling",
                "repo": repo.name,
                "detail": (
                    f"cwd is the {repo.name} clone. Open the matching "
                    "workspaces/<id>.code-workspace so the harness and other "
                    "siblings are loaded too."
                ),
            }
    return {
        "kind": "other",
        "detail": "cwd is outside the harness and its siblings.",
    }

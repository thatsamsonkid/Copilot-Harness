from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from coboose import CobooseError
from coboose.catalog import Catalog
from coboose.gitinfo import inspect_git
from coboose.jira_client import parse_issue_key
from coboose.workspace_detect import resolve_workspace_scope, scoped_repos

RunFn = Callable[..., subprocess.CompletedProcess[str]]


def suggested_branch(issue: str) -> str:
    return parse_issue_key(issue)


def align_branches(
    catalog: Catalog,
    coboose_root: Path,
    issue: str,
    *,
    only: list[str] | None = None,
    create: bool = False,
    dry_run: bool = False,
    run: RunFn | None = None,
    workspace_id: str | None = None,
    all_repos: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    name = suggested_branch(issue)
    runner = run or _run
    scope = resolve_workspace_scope(
        catalog,
        coboose_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    repos = []
    blocked = []
    for repo in scoped_repos(catalog, scope, only=only):
        path = catalog.repo_path(coboose_root, repo)
        git = inspect_git(path, default_branch=repo.default_branch, run=runner)
        record: dict[str, Any] = {
            "id": repo.name,
            "path": str(path),
            "cloned": path.exists(),
            "current_branch": git.get("branch"),
            "suggested": name,
            "dirty": bool(git.get("dirty")),
            "action": "skip",
        }
        if not path.exists():
            record["action"] = "missing"
            repos.append(record)
            continue
        if not git.get("present"):
            record["action"] = "not_git"
            record["error"] = git.get("detail")
            repos.append(record)
            continue
        if git.get("branch") == name:
            record["action"] = "exists"
            repos.append(record)
            continue
        if not create:
            record["action"] = "suggest"
            repos.append(record)
            continue
        if git.get("dirty"):
            record["action"] = "blocked"
            record["error"] = "Working tree is dirty. Commit or stash before creating a branch."
            blocked.append(repo.name)
            repos.append(record)
            continue
        record["action"] = "create"
        if not dry_run:
            _checkout_branch(path, name, runner)
            record["current_branch"] = name
        repos.append(record)

    payload = {
        "issue": name,
        "branch": name,
        "create": create,
        "dry_run": dry_run,
        "workspace": scope.id,
        "workspace_scope": scope.as_payload(),
        "repos": repos,
    }
    if blocked:
        raise CobooseError(
            "Refusing to create branches in dirty working trees: " + ", ".join(blocked),
            payload=payload,
        )
    return payload


def _checkout_branch(path: Path, name: str, run: RunFn) -> None:
    exists = run(
        ["git", "-C", str(path), "show-ref", "--verify", "--quiet", f"refs/heads/{name}"],
        path,
        check=False,
    )
    command = (
        ["git", "-C", str(path), "checkout", name]
        if exists.returncode == 0
        else ["git", "-C", str(path), "checkout", "-b", name]
    )
    result = run(command, path, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise CobooseError(
            f"Could not checkout {name} in {path}"
            + (f": {detail}" if detail else "")
        )


def _run(
    command: list[str],
    cwd: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=True,
    )

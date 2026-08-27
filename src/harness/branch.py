from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

from harness import HarnessError
from harness.catalog import Catalog
from harness.gitinfo import inspect_git
from harness.jira_client import parse_issue_key

RunFn = Callable[..., subprocess.CompletedProcess[str]]


def suggested_branch(issue: str) -> str:
    return parse_issue_key(issue)


def align_branches(
    catalog: Catalog,
    harness_root: Path,
    issue: str,
    *,
    only: list[str] | None = None,
    create: bool = False,
    dry_run: bool = False,
    run: RunFn | None = None,
) -> dict[str, Any]:
    name = suggested_branch(issue)
    runner = run or _run
    repos = []
    blocked = []
    for repo in catalog.enabled_repos(only=only):
        path = catalog.repo_path(harness_root, repo)
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
        "repos": repos,
    }
    if blocked:
        raise HarnessError(
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
        raise HarnessError(
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

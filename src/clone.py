from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from goat import GoatError
from goat.catalog import Catalog, Repo

RunFn = Callable[..., subprocess.CompletedProcess[str]]


def rewrite_clone_url(url: str, *, https: bool) -> str:
    if not https:
        return url
    if url.startswith("git@github.com:"):
        return "https://github.com/" + url.removeprefix("git@github.com:")
    if url.startswith("ssh://git@github.com/"):
        return "https://github.com/" + url.removeprefix("ssh://git@github.com/")
    return url


def clone_repos(
    catalog: Catalog,
    goat_root: Path,
    *,
    only: list[str] | None = None,
    tags: list[str] | None = None,
    update: bool = False,
    dry_run: bool = False,
    https: bool = False,
    run: RunFn | None = None,
) -> list[dict[str, Any]]:
    runner = run or _run
    if not shutil.which("git") and run is None:
        raise GoatError("git is not installed or not on PATH")

    sibling_root = catalog.require_safe_sibling_root(goat_root)
    if sibling_root == goat_root.resolve():
        raise GoatError(
            "parent_dir resolves to the Goat repo. "
            "Set parent_dir: .. so clones stay outside this repository."
        )

    results: list[dict[str, Any]] = []
    for repo in catalog.enabled_repos(only, tags):
        dest = catalog.repo_path(goat_root, repo)
        _refuse_goat_destination(dest, goat_root)
        record = clone_one(
            repo,
            dest,
            sibling_root=sibling_root,
            update=update,
            dry_run=dry_run,
            https=https,
            run=runner,
        )
        record["mapped"] = catalog.is_mapped(repo)
        record["expected"] = str(catalog.expected_repo_path(goat_root, repo))
        results.append(record)
    return results


def clone_one(
    repo: Repo,
    dest: Path,
    *,
    sibling_root: Path,
    update: bool = False,
    dry_run: bool = False,
    https: bool = False,
    run: RunFn | None = None,
) -> dict[str, Any]:
    run = run or _run
    if dest.exists() and not (dest / ".git").exists():
        raise GoatError(
            f"{dest} exists but is not a git repo. "
            "Move it aside so it is not treated as a nested tree."
        )
    if dest.exists() and dest.resolve() == sibling_root:
        raise GoatError(f"Refusing to clone onto sibling root: {dest}")

    url = rewrite_clone_url(repo.url, https=https)
    record: dict[str, Any] = {
        "id": repo.id,
        "url": url,
        "path": str(dest),
        "branch": repo.default_branch,
        "placeholder": repo.is_placeholder,
        "action": "skip",
        "cloned": dest.exists(),
    }
    if repo.is_placeholder:
        record["action"] = "blocked"
        record["error"] = (
            "URL still contains a placeholder (YOUR_ORG/example). "
            "Update repositories.yml first."
        )
        return record

    if dest.exists():
        if not update:
            record["action"] = "exists"
            return record
        record["action"] = "update"
        if dry_run:
            return record
        run(["git", "-C", str(dest), "fetch", "--prune", "origin"], dest)
        run(
            [
                "git",
                "-C",
                str(dest),
                "pull",
                "--ff-only",
                "origin",
                repo.default_branch,
            ],
            dest,
        )
        record["cloned"] = True
        return record

    record["action"] = "clone"
    if dry_run:
        return record
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "git",
            "clone",
            "--branch",
            repo.default_branch,
            "--single-branch",
            url,
            str(dest),
        ],
        dest.parent,
    )
    record["cloned"] = True
    return record


def _refuse_goat_destination(dest: Path, goat_root: Path) -> None:
    dest_resolved = dest.resolve()
    goat = goat_root.resolve()
    if dest_resolved == goat or goat in dest_resolved.parents:
        raise GoatError(
            f"Refusing to clone into the Goat repo: {dest}. "
            "Keep product clones under parent_dir, not inside this repository."
        )


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise GoatError(
            f"Command failed ({exc.returncode}): {' '.join(command)}"
            + (f"\n{detail}" if detail else "")
        ) from exc

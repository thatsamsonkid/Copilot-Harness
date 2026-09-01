from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from goat import GoatError
from goat.catalog import Catalog, Repo

RunFn = Callable[..., subprocess.CompletedProcess[str]]

# git honours "remote helper" transports like `ext::sh -c ...` and `fd::`, which
# execute arbitrary commands during clone/fetch. We only ever expect real remote
# URLs, so anything using the `<transport>::` form is rejected outright.
_REMOTE_HELPER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+.\-]*::")
# scp-like syntax, e.g. git@github.com:org/repo.git
_SCP_LIKE_RE = re.compile(r"^[A-Za-z0-9][\w.\-]*@[\w.\-]+:")
_ALLOWED_URL_SCHEMES = ("https", "ssh")
# Belt-and-suspenders even after URL validation: never run the ext helper.
_GIT_SAFE_OPTS = ("-c", "protocol.ext.allow=never")


def validate_git_url(url: str) -> str:
    """Return the URL if it is a safe git remote, else raise GoatError.

    Guards against argument injection (values git would read as options) and
    command-execution transports (`ext::`, `fd::`, arbitrary `scheme://`).
    Allowed forms: https://, ssh://, scp-like git@host:path, and plain local
    filesystem paths (used for mirrors and tests).
    """
    cleaned = (url or "").strip()
    if not cleaned:
        raise GoatError("A git URL is required")
    if cleaned.startswith("-"):
        raise GoatError(
            f"Refusing git URL that looks like a command-line option: {cleaned!r}"
        )
    if _REMOTE_HELPER_RE.match(cleaned):
        raise GoatError(
            f"Refusing unsafe git transport (remote-helper syntax): {cleaned!r}"
        )
    if "://" in cleaned:
        scheme = cleaned.split("://", 1)[0].lower()
        if scheme not in _ALLOWED_URL_SCHEMES:
            raise GoatError(
                f"Unsupported git URL scheme {scheme!r} in {cleaned!r}. "
                "Use https://, ssh://, or git@host:org/repo.git."
            )
        return cleaned
    if _SCP_LIKE_RE.match(cleaned):
        return cleaned
    # No scheme and no `::` transport: treat as a local filesystem path.
    return cleaned


def validate_git_ref(ref: str) -> str:
    """Return a branch/ref name if safe to pass to git, else raise GoatError."""
    cleaned = (ref or "").strip()
    if not cleaned:
        raise GoatError("A git branch/ref is required")
    if cleaned.startswith("-"):
        raise GoatError(
            f"Refusing git ref that looks like a command-line option: {cleaned!r}"
        )
    if any(ch.isspace() for ch in cleaned) or any(ord(ch) < 0x20 for ch in cleaned):
        raise GoatError(f"Invalid git ref: {cleaned!r}")
    return cleaned


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
        results.append(
            clone_one(
                repo,
                dest,
                sibling_root=sibling_root,
                update=update,
                dry_run=dry_run,
                https=https,
                run=runner,
            )
        )
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
    branch = validate_git_ref(repo.default_branch)
    validate_git_url(url)
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
        run(["git", "-C", str(dest), *_GIT_SAFE_OPTS, "fetch", "--prune", "origin"], dest)
        run(
            [
                "git",
                "-C",
                str(dest),
                *_GIT_SAFE_OPTS,
                "pull",
                "--ff-only",
                "origin",
                branch,
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
            *_GIT_SAFE_OPTS,
            "clone",
            "--branch",
            branch,
            "--single-branch",
            "--",
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

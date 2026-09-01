from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

RunFn = Callable[..., subprocess.CompletedProcess[str]]


def inspect_git(
    path: Path,
    *,
    default_branch: str = "main",
    run: RunFn | None = None,
) -> dict[str, Any]:
    """Read-only snapshot of a sibling working tree. Never mutates the repo."""
    runner = run or _run
    if not path.exists():
        return _empty_git(default_branch, "path does not exist")
    if not _looks_like_git(path, runner):
        return _empty_git(default_branch, "not a git repo")

    branch = _stdout(runner, path, ["rev-parse", "--abbrev-ref", "HEAD"], check=False) or "HEAD"
    porcelain = _stdout(runner, path, ["status", "--porcelain"], check=False) or ""
    dirty_paths = [line[3:] for line in porcelain.splitlines() if line.strip()]
    head_line = _stdout(
        runner, path, ["log", "-1", "--format=%H%x09%ct%x09%s"], check=False
    )
    sha, committed_at, subject = _parse_head(head_line)
    ahead, behind = _ahead_behind(path, runner)
    return {
        "present": True,
        "branch": branch,
        "default_branch": default_branch,
        "on_default_branch": branch == default_branch,
        "dirty": bool(dirty_paths),
        "dirty_count": len(dirty_paths),
        "ahead": ahead,
        "behind": behind,
        "head": sha,
        "head_subject": subject,
        "committed_at": committed_at,
        "committed_at_unix": _iso_to_unix(committed_at),
        "detail": "ok",
    }


def list_remotes(path: Path, *, run: RunFn | None = None) -> list[str]:
    """Return unique remote URLs for a working tree (origin first)."""
    runner = run or _run
    if not path.exists() or not _looks_like_git(path, runner):
        return []
    raw = _stdout(runner, path, ["remote", "-v"], check=False) or ""
    origin: list[str] = []
    others: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        if url in seen:
            continue
        seen.add(url)
        if name == "origin":
            origin.append(url)
        else:
            others.append(url)
    return [*origin, *others]


def last_commit_unix(path: Path, *, run: RunFn | None = None) -> int | None:
    runner = run or _run
    raw = _stdout(runner, path, ["log", "-1", "--format=%ct"], check=False)
    if not raw:
        return None
    try:
        return int(raw.strip())
    except ValueError:
        return None


def _looks_like_git(path: Path, run: RunFn) -> bool:
    if (path / ".git").exists():
        return True
    result = run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        path,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _ahead_behind(path: Path, run: RunFn) -> tuple[int | None, int | None]:
    raw = _stdout(
        run,
        path,
        ["rev-list", "--left-right", "--count", "@{upstream}...HEAD"],
        check=False,
    )
    if not raw:
        return None, None
    parts = raw.split()
    if len(parts) != 2:
        return None, None
    try:
        behind, ahead = int(parts[0]), int(parts[1])
    except ValueError:
        return None, None
    return ahead, behind


def _parse_head(line: str | None) -> tuple[str | None, str | None, str | None]:
    if not line:
        return None, None, None
    sha, _, rest = line.partition("\t")
    unix, _, subject = rest.partition("\t")
    try:
        committed_at = datetime.fromtimestamp(int(unix), tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        committed_at = None
    return sha or None, committed_at, subject or None


def _iso_to_unix(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(value).timestamp())
    except ValueError:
        return None


def _empty_git(default_branch: str, detail: str) -> dict[str, Any]:
    return {
        "present": False,
        "branch": None,
        "default_branch": default_branch,
        "on_default_branch": False,
        "dirty": False,
        "dirty_count": 0,
        "ahead": None,
        "behind": None,
        "head": None,
        "head_subject": None,
        "committed_at": None,
        "committed_at_unix": None,
        "detail": detail,
    }


def _stdout(
    run: RunFn,
    path: Path,
    args: list[str],
    *,
    check: bool = True,
) -> str | None:
    result = run(["git", "-C", str(path), *args], path, check=check)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


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

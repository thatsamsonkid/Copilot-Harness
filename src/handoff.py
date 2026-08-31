from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from goat import GoatError

HANDOFF_DIR = "handoffs"


def write_handoff(
    goat_root: Path,
    *,
    issue: str | None = None,
    note: str | None = None,
    status: dict[str, Any] | None = None,
    extra: str | None = None,
) -> dict[str, Any]:
    directory = _handoff_dir(goat_root)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = _slug(issue or "session")
    path = directory / f"{stamp}-{slug}.md"
    body = _render(issue=issue, note=note, status=status, extra=extra, written_at=stamp)
    path.write_text(body, encoding="utf-8")
    return {
        "file": str(path),
        "issue": issue,
        "written_at": stamp,
        "relative": str(path.relative_to(goat_root)),
    }


def list_handoffs(goat_root: Path) -> list[dict[str, Any]]:
    directory = _handoff_dir(goat_root)
    if not directory.is_dir():
        return []
    items = []
    for path in sorted(directory.glob("*.md"), reverse=True):
        items.append(_summarize(path, goat_root))
    return items


def latest_handoff(goat_root: Path) -> dict[str, Any]:
    items = list_handoffs(goat_root)
    if not items:
        raise GoatError("No handoff notes yet. Run goat handoff write.")
    latest = items[0]
    path = Path(latest["file"])
    latest["body"] = path.read_text(encoding="utf-8")
    return latest


def _handoff_dir(goat_root: Path) -> Path:
    return goat_root / HANDOFF_DIR


def _slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value.strip())
    cleaned = cleaned.strip("-") or "session"
    return cleaned[:40]


def _summarize(path: Path, goat_root: Path) -> dict[str, Any]:
    issue = None
    title = path.stem
    for line in path.read_text(encoding="utf-8").splitlines()[:8]:
        if line.startswith("# Handoff"):
            title = line.lstrip("# ").strip()
        if line.startswith("- Issue:") or line.startswith("- **Issue:**"):
            issue = line.split(":", 1)[1].strip().strip("*").strip("`") or None
    return {
        "file": str(path),
        "relative": str(path.relative_to(goat_root)),
        "title": title,
        "issue": issue,
    }


def _render(
    *,
    issue: str | None,
    note: str | None,
    status: dict[str, Any] | None,
    extra: str | None,
    written_at: str,
) -> str:
    lines = [
        f"# Handoff{f': {issue}' if issue else ''}",
        "",
        f"- Written at: `{written_at}`",
        f"- Issue: `{issue or 'none'}`",
        "",
        "## Notes",
        "",
        (note or "Resume from the sibling git snapshot below.").strip(),
        "",
    ]
    if extra:
        lines.extend(["## Extra", "", extra.strip(), ""])
    if status:
        lines.extend(["## Sibling snapshot", ""])
        hint = (status.get("cwd_hint") or {}).get("detail")
        if hint:
            lines.append(hint)
            lines.append("")
        dirty = status.get("dirty_repos") or []
        behind = status.get("behind_repos") or []
        if dirty:
            lines.append("Dirty: " + ", ".join(dirty))
        if behind:
            lines.append("Behind origin: " + ", ".join(behind))
        if dirty or behind:
            lines.append("")
        for repo in status.get("repos") or []:
            git = repo.get("git") or {}
            name = repo.get("id") or repo.get("name")
            if not repo.get("cloned"):
                lines.append(f"- `{name}` — not cloned")
                continue
            branch = git.get("branch") or "?"
            flags = []
            if git.get("dirty"):
                flags.append(f"dirty {git.get('dirty_count')}")
            if git.get("behind"):
                flags.append(f"behind {git['behind']}")
            if git.get("ahead"):
                flags.append(f"ahead {git['ahead']}")
            extra_flags = f" ({', '.join(flags)})" if flags else ""
            subject = git.get("head_subject") or "no commits"
            lines.append(f"- `{name}` on `{branch}`{extra_flags} — {subject}")
        lines.append("")
    lines.extend(
        [
            "## Resume",
            "",
            "1. Open the feature `.code-workspace` if this window is a single folder.",
            "2. Run `uv run goat status --format json` to refresh the snapshot.",
            "3. If there is a Jira key, run `uv run goat prepare <KEY> --format json`.",
            "",
        ]
    )
    return "\n".join(lines)

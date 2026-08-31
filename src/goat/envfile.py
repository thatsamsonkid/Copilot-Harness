from __future__ import annotations

import time
from pathlib import Path

TOKEN_WARN_DAYS = 300


def env_file_keys(path: Path) -> dict[str, bool]:
    """Return whether each assignment in an env file has a non-empty value.

    Values are never returned.
    """
    present: dict[str, bool] = {}
    if not path.exists():
        return present
    for raw in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw)
        if parsed is None:
            continue
        key, value = parsed
        present[key] = bool(value)
    return present


def load_env_file(path: Path) -> dict[str, str]:
    """Load KEY=value assignments. Callers must not print the values."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw)
        if parsed is None:
            continue
        key, value = parsed
        values[key] = value
    return values


def _parse_env_line(raw: str) -> tuple[str, str] | None:
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    if line.startswith("export "):
        line = line[7:].strip()
    key, _, value = line.partition("=")
    key = key.strip()
    if not key:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def upsert_env_file(path: Path, updates: dict[str, str]) -> list[str]:
    """Create or update keys in an env file. Returns the keys that were written."""
    if not updates:
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    written: list[str] = []
    next_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                next_lines.append(f"{key}={remaining.pop(key)}")
                written.append(key)
                continue
        next_lines.append(line)
    if remaining and next_lines and next_lines[-1] != "":
        next_lines.append("")
    for key, value in remaining.items():
        next_lines.append(f"{key}={value}")
        written.append(key)
    path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
    return written


def env_file_age(path: Path, *, now: float | None = None, warn_days: int = TOKEN_WARN_DAYS) -> dict:
    """Age of .env based on mtime. Does not read values or Atlassian expiry."""
    if not path.exists():
        return {
            "present": False,
            "age_days": None,
            "stale": False,
            "warn_days": warn_days,
            "detail": ".env is missing",
        }
    age_days = ((now if now is not None else time.time()) - path.stat().st_mtime) / 86400
    stale = age_days >= warn_days
    rounded = round(age_days, 1)
    return {
        "present": True,
        "age_days": rounded,
        "stale": stale,
        "warn_days": warn_days,
        "detail": (
            f".env is {rounded} days old; if JIRA_API_TOKEN still lives there, "
            "rotate it (Atlassian tokens expire in at most 1 year). "
            "Tokens in the OS keychain are not dated by this file."
            if stale
            else f".env is {rounded} days old"
        ),
    }

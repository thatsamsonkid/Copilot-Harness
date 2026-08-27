from __future__ import annotations

from pathlib import Path


def env_file_keys(path: Path) -> dict[str, bool]:
    """Return whether each assignment in an env file has a non-empty value.

    Values are never returned.
    """
    present: dict[str, bool] = {}
    if not path.exists():
        return present
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        present[key] = bool(value.strip().strip("'").strip('"'))
    return present


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

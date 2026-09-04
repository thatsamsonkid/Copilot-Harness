from __future__ import annotations

import os
import time
from pathlib import Path

from goat import GoatError

TOKEN_WARN_DAYS = 300
_ENV_FILE_MODE = 0o600


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


def _line_key(stripped: str) -> tuple[str, bool] | None:
    """Return (key, had_export) for an assignment line, else None.

    Recognizes the optional ``export `` prefix so that ``export FOO=1`` is keyed
    as ``FOO`` (matching what dotenv and load_env_file do).
    """
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    had_export = False
    if stripped.startswith("export "):
        had_export = True
        stripped = stripped[7:].strip()
    key = stripped.split("=", 1)[0].strip()
    if not key:
        return None
    return key, had_export


def _unescape_double_quoted(inner: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner) and inner[i + 1] in ('"', "\\"):
            out.append(inner[i + 1])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


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
        quote = value[0]
        inner = value[1:-1]
        value = _unescape_double_quoted(inner) if quote == '"' else inner
    return key, value


def format_env_value(value: str) -> str:
    """Render a value for a single .env line, quoting/escaping as needed.

    Rejects control characters (a newline in a value would otherwise smuggle a
    second assignment into the file). Quotes values that would not round-trip
    unquoted through both this module's parser and python-dotenv.
    """
    text = "" if value is None else str(value)
    if any(ord(ch) < 0x20 for ch in text):
        raise GoatError(
            "Refusing to write an env value containing control characters "
            "(newline/tab/etc.)."
        )
    needs_quote = bool(text) and (
        text != text.strip() or '"' in text or "'" in text or "#" in text
    )
    if not needs_quote:
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _chmod_env_file(path: Path) -> None:
    try:
        os.chmod(path, _ENV_FILE_MODE)
    except OSError:
        pass


def upsert_env_file(path: Path, updates: dict[str, str]) -> list[str]:
    """Create or update keys in an env file. Returns the keys that were written."""
    if not updates:
        return []
    for value in updates.values():
        format_env_value(value)  # validate before touching the file
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    written: list[str] = []
    updated_keys: set[str] = set()
    next_lines: list[str] = []
    for line in lines:
        parsed = _line_key(line.strip())
        if parsed is not None:
            key, had_export = parsed
            if key in remaining:
                prefix = "export " if had_export else ""
                next_lines.append(f"{prefix}{key}={format_env_value(remaining.pop(key))}")
                written.append(key)
                updated_keys.add(key)
                continue
            if key in updated_keys:
                # Drop a stale duplicate assignment of a key we already updated;
                # otherwise the later (unchanged) line would win on the next read.
                continue
        next_lines.append(line)
    if remaining and next_lines and next_lines[-1] != "":
        next_lines.append("")
    for key, value in remaining.items():
        next_lines.append(f"{key}={format_env_value(value)}")
        written.append(key)
    path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
    _chmod_env_file(path)
    return written


def blank_env_keys(path: Path, names) -> list[str]:
    """Blank every existing assignment for any of ``names`` (including aliases
    and ``export ``-prefixed lines). Returns the keys that were blanked.

    The value is emptied rather than the line removed so the key stays visible
    and existing callers/tests that expect ``KEY=`` keep working.
    """
    targets = {name for name in names}
    if not targets or not path.exists():
        return []
    blanked: list[str] = []
    seen: set[str] = set()
    next_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _line_key(line.strip())
        if parsed is not None and parsed[0] in targets:
            key, had_export = parsed
            if key in seen:
                continue
            prefix = "export " if had_export else ""
            next_lines.append(f"{prefix}{key}=")
            blanked.append(key)
            seen.add(key)
            continue
        next_lines.append(line)
    if blanked:
        path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
        _chmod_env_file(path)
    return blanked


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

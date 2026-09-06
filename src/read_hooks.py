"""PreToolUse guards that send whole-file reads of large files to /bulk-reader."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Mapping

DEFAULT_MAX_LINES = 350
ENV_MAX_LINES = "GOAT_BULK_READ_MAX_LINES"
CONFIG_RELATIVE = Path(".github") / "hooks" / "read-guard.json"

READ_TOOLS = frozenset(
    {
        "read",
        "Read",
        "view",
        "View",
        "NotebookRead",
    }
)
SHELL_TOOLS = frozenset(
    {
        "bash",
        "Bash",
        "shell",
        "Shell",
        "execute",
        "powershell",
        "PowerShell",
        "runCommands",
        "runTerminalCommand",
        "run_in_terminal",
    }
)
WHOLE_FILE_READERS = frozenset({"cat", "head", "tail", "less", "more"})
PATH_KEYS = (
    "file_path",
    "filePath",
    "path",
    "target_file",
    "targetFile",
)
COMMAND_KEYS = ("command", "Command", "commandLine", "cmd")
LIMIT_KEYS = ("limit", "Limit")
OFFSET_KEYS = ("offset", "Offset")
COUNT_FLAGS = frozenset({"-n", "--lines", "-c", "--bytes"})


def allow() -> dict[str, Any]:
    return {"permissionDecision": "allow"}


def deny(reason: str) -> dict[str, Any]:
    return {
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }


def emit(decision: Mapping[str, Any]) -> int:
    sys.stdout.write(json.dumps(decision, separators=(",", ":")))
    sys.stdout.write("\n")
    return 0


def load_payload(raw: str | None = None) -> dict[str, Any]:
    text = sys.stdin.read() if raw is None else raw
    if not text or not text.strip():
        return {}
    data = json.loads(text)
    return data if isinstance(data, dict) else {}


def tool_name(payload: Mapping[str, Any]) -> str:
    value = payload.get("tool_name") or payload.get("toolName") or ""
    return str(value)


def tool_args(payload: Mapping[str, Any]) -> dict[str, Any]:
    args = (
        payload.get("tool_input")
        or payload.get("toolArgs")
        or payload.get("tool_args")
        or {}
    )
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except json.JSONDecodeError:
            return {"command": args}
        return parsed if isinstance(parsed, dict) else {"command": args}
    return args if isinstance(args, dict) else {}


def payload_cwd(payload: Mapping[str, Any]) -> Path:
    raw = payload.get("cwd") or os.getcwd()
    path = Path(str(raw)).expanduser()
    return path if path.is_dir() else Path.cwd()


def max_lines(
    *,
    environ: Mapping[str, str] | None = None,
    goat_root: Path | None = None,
) -> int:
    env = os.environ if environ is None else environ
    raw = env.get(ENV_MAX_LINES, "").strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            value = 0
        if value > 0:
            return value
    root = goat_root or _guess_goat_root()
    config = root / CONFIG_RELATIVE
    if config.is_file():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict):
            try:
                value = int(data.get("max_lines") or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
    return DEFAULT_MAX_LINES


def _guess_goat_root() -> Path:
    here = Path(__file__).resolve()
    if here.parts[-2:] == ("src", "read_hooks.py"):
        return here.parents[1]
    cwd = Path.cwd()
    if (cwd / ".github" / "hooks").is_dir():
        return cwd
    return cwd


def read_path(args: Mapping[str, Any]) -> str:
    for key in PATH_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_targeted_read(args: Mapping[str, Any]) -> bool:
    for key in LIMIT_KEYS:
        if _positive_int(args.get(key)) is not None:
            return True
    return False


def _positive_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def resolve_existing(path: str, cwd: Path) -> Path | None:
    if not path or path.startswith("-"):
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = cwd / candidate
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    if not resolved.is_file():
        return None
    return resolved


def count_lines(path: Path, *, cap: int | None = None) -> int | None:
    try:
        count = 0
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 64)
                if not chunk:
                    break
                if b"\x00" in chunk:
                    return None
                count += chunk.count(b"\n")
                if cap is not None and count > cap:
                    return count
        if path.stat().st_size > 0:
            with path.open("rb") as handle:
                handle.seek(-1, os.SEEK_END)
                if handle.read(1) != b"\n":
                    count += 1
        return count
    except OSError:
        return None


def bulk_reader_reason(path: Path, lines: int, threshold: int) -> str:
    return (
        f"{path} is {lines} lines (threshold {threshold}). "
        "Do not read the whole file. Use the /bulk-reader skill "
        "(or invoke the Bulk Reader agent) with the exact question "
        "and this path. Targeted reads with limit/offset may pass."
    )


def decide_file_size(
    payload: Mapping[str, Any],
    *,
    environ: Mapping[str, str] | None = None,
    goat_root: Path | None = None,
) -> dict[str, Any]:
    if tool_name(payload) not in READ_TOOLS:
        return allow()
    args = tool_args(payload)
    if is_targeted_read(args):
        return allow()
    raw_path = read_path(args)
    if not raw_path:
        return allow()
    path = resolve_existing(raw_path, payload_cwd(payload))
    if path is None:
        return allow()
    threshold = max_lines(environ=environ, goat_root=goat_root)
    lines = count_lines(path, cap=threshold)
    if lines is None or lines <= threshold:
        return allow()
    return deny(bulk_reader_reason(path, lines, threshold))


_QUOTED = re.compile(r"(\'(?:\\.|[^\'])*\'|\"(?:\\.|[^\"])*\")")


def has_unquoted_pipe(command: str) -> bool:
    stripped = _QUOTED.sub("", command)
    return "|" in stripped


def shell_command(args: Mapping[str, Any]) -> str:
    for key in COMMAND_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _strip_env_prefix(tokens: list[str]) -> list[str]:
    index = 0
    while index < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[index]):
        index += 1
    return tokens[index:]


def _numeric_flag_value(tokens: list[str], index: int, token: str) -> int | None:
    if token in COUNT_FLAGS:
        if index + 1 < len(tokens):
            return _positive_int(tokens[index + 1])
        return None
    match = re.fullmatch(r"(?:-n|--lines|-c|--bytes)=?(\d+)", token)
    if match:
        return int(match.group(1))
    match = re.fullmatch(r"-n(\d+)", token)
    if match:
        return int(match.group(1))
    return None


def reader_file_paths(command: str) -> list[str]:
    """Return file operands of cat/head/tail/less/more when the read is not targeted."""
    if not command or has_unquoted_pipe(command):
        return []
    parts = re.split(r"\s*(?:&&|\|\||;)\s*", command)
    found: list[str] = []
    for part in parts:
        if not part or has_unquoted_pipe(part):
            continue
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            continue
        tokens = _strip_env_prefix(tokens)
        if not tokens:
            continue
        reader = Path(tokens[0]).name.lower()
        if reader not in WHOLE_FILE_READERS:
            continue
        skip_next = False
        targeted = False
        files: list[str] = []
        for index, token in enumerate(tokens[1:], start=1):
            if skip_next:
                skip_next = False
                continue
            if token == "--":
                files.extend(tokens[index + 1 :])
                break
            count = _numeric_flag_value(tokens, index, token)
            if count is not None:
                targeted = True
                if token in COUNT_FLAGS:
                    skip_next = True
                continue
            if token.startswith("-"):
                continue
            files.append(token)
        if targeted:
            continue
        found.extend(files)
    return found


def decide_bash_read(
    payload: Mapping[str, Any],
    *,
    environ: Mapping[str, str] | None = None,
    goat_root: Path | None = None,
) -> dict[str, Any]:
    if tool_name(payload) not in SHELL_TOOLS:
        return allow()
    command = shell_command(tool_args(payload))
    paths = reader_file_paths(command)
    if not paths:
        return allow()
    cwd = payload_cwd(payload)
    threshold = max_lines(environ=environ, goat_root=goat_root)
    for raw in paths:
        path = resolve_existing(raw, cwd)
        if path is None:
            continue
        lines = count_lines(path, cap=threshold)
        if lines is None or lines <= threshold:
            continue
        return deny(bulk_reader_reason(path, lines, threshold))
    return allow()


def run_check_file_size() -> int:
    try:
        return emit(decide_file_size(load_payload()))
    except Exception:
        return emit(allow())


def run_check_bash_read() -> int:
    try:
        return emit(decide_bash_read(load_payload()))
    except Exception:
        return emit(allow())

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

GOAT_FOLDER_NAME = "goat"

_SPAWN_NOTE = (
    "Bare `uv run goat` only works when the process cwd is this Goat "
    "repo (it has pyproject.toml). After cd into a sibling clone, uv cannot "
    "spawn `goat`. Set the command cwd to `cwd`, or run `command` / `script` "
    "from any directory. Do not reuse an app terminal for goat commands."
)


def invoke_spec(root: Path) -> dict[str, str]:
    """Cwd-independent ways to spawn the CLI after Copilot cds into a sibling."""
    root = Path(root).resolve()
    return {
        "cwd": str(root),
        "command": f"uv run --project {shlex.quote(str(root))} goat",
        "script": str(root / "scripts" / "goat.sh"),
        "windows_script": str(root / "scripts" / "goat.ps1"),
        "note": _SPAWN_NOTE,
    }


def terminal_env_settings(
    *,
    folder_name: str | None = GOAT_FOLDER_NAME,
    workspace_id: str | None = None,
    include_root: bool = True,
) -> dict[str, Any]:
    """VS Code terminal env so the open workspace survives a cd into a product repo."""
    env: dict[str, str] = {}
    if include_root:
        value = f"${{workspaceFolder:{folder_name}}}" if folder_name else "${workspaceFolder}"
        env["GOAT_ROOT"] = value
    if workspace_id:
        env["GOAT_WORKSPACE"] = workspace_id
        env["GOAT_WORKSPACE_FILE"] = "${workspaceFile}"
    return {
        "terminal.integrated.env.linux": dict(env),
        "terminal.integrated.env.osx": dict(env),
        "terminal.integrated.env.windows": dict(env),
    }

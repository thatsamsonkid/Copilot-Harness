from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

HARNESS_FOLDER_NAME = "harness"

_SPAWN_NOTE = (
    "Bare `uv run harness` only works when the process cwd is this harness "
    "repo (it has pyproject.toml). After cd into a sibling clone, uv cannot "
    "spawn `harness`. Set the command cwd to `cwd`, or run `command` / `script` "
    "from any directory. Do not reuse an app terminal for harness commands."
)


def invoke_spec(root: Path) -> dict[str, str]:
    """Cwd-independent ways to spawn the CLI after Copilot cds into a sibling."""
    root = Path(root).resolve()
    return {
        "cwd": str(root),
        "command": f"uv run --project {shlex.quote(str(root))} harness",
        "script": str(root / "scripts" / "harness.sh"),
        "windows_script": str(root / "scripts" / "harness.ps1"),
        "note": _SPAWN_NOTE,
    }


def terminal_env_settings(*, folder_name: str | None = HARNESS_FOLDER_NAME) -> dict[str, Any]:
    """VS Code terminal env so HARNESS_ROOT survives a cd into a product repo."""
    value = f"${{workspaceFolder:{folder_name}}}" if folder_name else "${workspaceFolder}"
    env = {"HARNESS_ROOT": value}
    return {
        "terminal.integrated.env.linux": dict(env),
        "terminal.integrated.env.osx": dict(env),
        "terminal.integrated.env.windows": dict(env),
    }

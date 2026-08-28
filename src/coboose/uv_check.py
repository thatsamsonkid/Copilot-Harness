from __future__ import annotations

import platform
import shutil
from collections.abc import Callable
from typing import Any

UV_DOC = "docs/install-uv.md"
UV_DOCS_URL = "https://docs.astral.sh/uv/getting-started/installation/"

INSTALL_COMMANDS = {
    "macos": "curl -LsSf https://astral.sh/uv/install.sh | sh",
    "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh",
    "windows": 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
}

SETUP_SCRIPTS = {
    "macos": "./scripts/setup.sh",
    "linux": "./scripts/setup.sh",
    "windows": ".\\scripts\\setup.ps1",
}

ALT_COMMANDS = {
    "macos": "brew install uv",
    "linux": "wget -qO- https://astral.sh/uv/install.sh | sh",
    "windows": "winget install --id=astral-sh.uv -e",
}


def os_family(system: str | None = None) -> str:
    name = (system or platform.system()).lower()
    if name == "darwin":
        return "macos"
    if name.startswith("win"):
        return "windows"
    return "linux"


def detect_uv(
    *,
    which: Callable[[str], str | None] = shutil.which,
    system: str | None = None,
) -> dict[str, Any]:
    family = os_family(system)
    path = which("uv")
    return {
        "present": bool(path),
        "path": path,
        "os": family,
        "docs": UV_DOC,
        "docs_url": UV_DOCS_URL,
        "install_command": INSTALL_COMMANDS[family],
        "alt_command": ALT_COMMANDS[family],
        "setup_script": SETUP_SCRIPTS[family],
        "install": {
            name: {
                "command": INSTALL_COMMANDS[name],
                "alt_command": ALT_COMMANDS[name],
                "setup_script": SETUP_SCRIPTS[name],
            }
            for name in ("macos", "windows", "linux")
        },
    }


def uv_missing_action(info: dict[str, Any] | None = None) -> str:
    info = info or detect_uv()
    family = info["os"]
    label = {"macos": "macOS", "windows": "Windows", "linux": "Linux"}[family]
    return (
        f"Install uv for {label}: {info['install_command']} "
        f"(or {info['setup_script']}). See {UV_DOC}."
    )

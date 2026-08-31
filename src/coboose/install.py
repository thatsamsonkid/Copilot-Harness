from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from typing import Any, Callable, Mapping

from coboose import CobooseError
from coboose.paths import find_coboose_root, is_coboose_root
from coboose.uv_check import os_family

MARKER = "coboose-global-shim"
SHIM_VERSION = "1"

PATH_HINTS = {
    "macos": (
        'Add ~/.local/bin to PATH and open a new terminal '
        '(or: export PATH="$HOME/.local/bin:$PATH"). See docs/install-uv.md.'
    ),
    "linux": (
        'Add ~/.local/bin to PATH and open a new terminal '
        '(or: export PATH="$HOME/.local/bin:$PATH"). See docs/install-uv.md.'
    ),
    "windows": (
        r"Add %USERPROFILE%\.local\bin to PATH and open a new terminal. "
        "The uv installer usually does this. See docs/install-uv.md."
    ),
}


def default_bin_dir() -> Path:
    return Path.home() / ".local" / "bin"


def resolve_install_root(explicit: Path | None = None) -> Path:
    """Prefer an in-cwd kit so `coboose install` can retarget after a move."""
    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
        if not is_coboose_root(root):
            raise CobooseError(
                f"{root} is not a Coboose root (missing repositories.yml "
                "or catalog/stack.yaml)"
            )
        return root
    cwd = Path.cwd().resolve()
    for path in [cwd, *cwd.parents]:
        if is_coboose_root(path):
            return path
    return find_coboose_root()


def shim_names(family: str) -> list[str]:
    if family == "windows":
        return ["coboose.cmd", "coboose"]
    return ["coboose"]


def is_our_shim(path: Path) -> bool:
    try:
        return MARKER in path.read_text(encoding="utf-8")
    except OSError:
        return False


def cli_path_status(
    coboose_root: Path,
    *,
    bin_dir: Path | None = None,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    family = os_family(system)
    dest = Path(bin_dir).expanduser() if bin_dir else default_bin_dir()
    paths = [dest / name for name in shim_names(family)]
    installed = [path for path in paths if path.exists() and is_our_shim(path)]
    which_fn = which or shutil.which
    which_path = which_fn("coboose")
    which_ours = bool(which_path and is_our_shim(Path(which_path)))
    bin_on_path = _bin_dir_on_path(dest, environ)
    on_path = which_ours or (bool(installed) and bin_on_path)
    if on_path:
        shown = which_path or str(installed[0])
        detail = f"coboose is on PATH ({shown})"
    elif installed:
        detail = (
            f"shim is installed at {dest} but that directory is not on PATH"
        )
    else:
        detail = "coboose is not registered on PATH"
    return {
        "os": family,
        "coboose_root": str(Path(coboose_root).resolve()),
        "bin_dir": str(dest),
        "installed": bool(installed),
        "on_path": on_path,
        "bin_dir_on_path": bin_on_path,
        "which": which_path,
        "detail": detail,
        "path_hint": None if on_path else PATH_HINTS[family],
        "shims": [str(path) for path in paths],
    }


def install_cli(
    coboose_root: Path,
    *,
    bin_dir: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    return _apply(
        "install",
        coboose_root,
        bin_dir=bin_dir,
        force=force,
        dry_run=dry_run,
        system=system,
        environ=environ,
        which=which,
    )


def uninstall_cli(
    coboose_root: Path,
    *,
    bin_dir: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    return _apply(
        "uninstall",
        coboose_root,
        bin_dir=bin_dir,
        force=force,
        dry_run=dry_run,
        system=system,
        environ=environ,
        which=which,
    )


def _apply(
    action: str,
    coboose_root: Path,
    *,
    bin_dir: Path | None,
    force: bool,
    dry_run: bool,
    system: str | None,
    environ: Mapping[str, str] | None,
    which: Callable[[str], str | None] | None,
) -> dict[str, Any]:
    root = Path(coboose_root).resolve()
    if not is_coboose_root(root):
        raise CobooseError(
            f"{root} is not a Coboose root (missing repositories.yml "
            "or catalog/stack.yaml)"
        )
    family = os_family(system)
    dest = Path(bin_dir).expanduser() if bin_dir else default_bin_dir()
    if dest.exists() and not dest.is_dir():
        raise CobooseError(f"Bin directory {dest} exists and is not a directory")

    records: list[dict[str, Any]] = []
    for name in shim_names(family):
        path = dest / name
        records.append(
            _apply_one(
                action,
                path,
                root=root,
                family=family,
                force=force,
                dry_run=dry_run,
            )
        )

    status = cli_path_status(
        root,
        bin_dir=dest,
        system=system,
        environ=environ,
        which=which,
    )
    payload = {
        "kind": "cli_install",
        "action": action,
        "coboose_root": str(root),
        "bin_dir": str(dest),
        "os": family,
        "dry_run": dry_run,
        "force": force,
        "shims": records,
        "on_path": status["on_path"],
        "bin_dir_on_path": status["bin_dir_on_path"],
        "which": status["which"],
        "detail": status["detail"],
        "path_hint": status["path_hint"],
        "next": _next_commands(status, dry_run=dry_run, action=action),
    }
    return payload


def _apply_one(
    action: str,
    path: Path,
    *,
    root: Path,
    family: str,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    exists = path.exists()
    ours = exists and is_our_shim(path)
    record: dict[str, Any] = {
        "path": str(path),
        "name": path.name,
        "existed": exists,
        "ours": ours,
        "written": False,
        "removed": False,
    }
    if action == "install":
        if exists and not ours and not force:
            raise CobooseError(
                f"{path} already exists and is not a coboose shim. "
                "Pass --force to overwrite."
            )
        contents = _shim_contents(root, family=family, name=path.name)
        record["would_write"] = True
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8", newline="\n")
            _make_executable(path)
            record["written"] = True
        return record

    if not exists:
        record["would_remove"] = False
        return record
    if not ours and not force:
        raise CobooseError(
            f"{path} is not a coboose shim. Pass --force to remove it."
        )
    record["would_remove"] = True
    if not dry_run:
        path.unlink()
        record["removed"] = True
    return record


def _shim_contents(root: Path, *, family: str, name: str) -> str:
    if name.endswith(".cmd") or (family == "windows" and name == "coboose.cmd"):
        return _windows_cmd_shim(root)
    return _unix_shim(root, posix=family == "windows")


def _unix_shim(root: Path, *, posix: bool) -> str:
    location = root.as_posix() if posix else str(root)
    quoted = _bash_single_quote(location)
    return (
        "#!/usr/bin/env bash\n"
        f"# {MARKER} {SHIM_VERSION}\n"
        "set -euo pipefail\n"
        f"export COBOOSE_ROOT={quoted}\n"
        'if command -v uv >/dev/null 2>&1; then\n'
        '  exec uv run --project "$COBOOSE_ROOT" coboose "$@"\n'
        "fi\n"
        'if [[ -x "$COBOOSE_ROOT/.venv/bin/coboose" ]]; then\n'
        '  exec "$COBOOSE_ROOT/.venv/bin/coboose" "$@"\n'
        "fi\n"
        'echo "uv is required. See docs/install-uv.md" >&2\n'
        "exit 127\n"
    )


def _windows_cmd_shim(root: Path) -> str:
    location = str(root)
    return (
        "@echo off\n"
        f"rem {MARKER} {SHIM_VERSION}\n"
        f'set "COBOOSE_ROOT={location}"\n'
        "where uv >nul 2>&1\n"
        "if %ERRORLEVEL%==0 (\n"
        '  uv run --project "%COBOOSE_ROOT%" coboose %*\n'
        "  exit /b %ERRORLEVEL%\n"
        ")\n"
        'if exist "%COBOOSE_ROOT%\\.venv\\Scripts\\coboose.exe" (\n'
        '  "%COBOOSE_ROOT%\\.venv\\Scripts\\coboose.exe" %*\n'
        "  exit /b %ERRORLEVEL%\n"
        ")\n"
        "echo uv is required. See docs/install-uv.md 1>&2\n"
        "exit /b 127\n"
    )


def _bash_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _make_executable(path: Path) -> None:
    if os.name == "nt":
        return
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _bin_dir_on_path(
    bin_dir: Path, environ: Mapping[str, str] | None = None
) -> bool:
    target = _norm_dir(bin_dir)
    raw = (environ if environ is not None else os.environ).get("PATH", "")
    for part in raw.split(os.pathsep):
        if not part.strip():
            continue
        if _norm_dir(Path(part)) == target:
            return True
    return False


def _norm_dir(path: Path) -> str:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = path.expanduser()
    return os.path.normcase(str(resolved))


def _next_commands(
    status: dict[str, Any], *, dry_run: bool, action: str
) -> list[str]:
    if action == "uninstall":
        return []
    if dry_run:
        return ["uv run coboose install"]
    if status["on_path"]:
        return ["coboose doctor"]
    return [
        status["path_hint"] or "Add the bin directory to PATH",
        "Then open a new terminal and run: coboose doctor",
    ]

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

from goat import GoatError
from goat.cli import main
from goat.install import (
    MARKER,
    cli_path_status,
    install_cli,
    refresh_installed_shims,
    resolve_install_root,
    shim_reinvokes_goat,
    uninstall_cli,
)
from goat.output import to_text

REAL_ROOT = Path(__file__).resolve().parents[1]


def test_install_writes_unix_shim(tmp_path: Path, goat_root: Path):
    bin_dir = tmp_path / "bin"
    payload = install_cli(
        goat_root,
        bin_dir=bin_dir,
        system="Linux",
        environ={"PATH": str(bin_dir)},
        which=lambda _name: str(bin_dir / "goat") if (bin_dir / "goat").exists() else None,
    )
    shim = bin_dir / "goat"
    text = shim.read_text(encoding="utf-8")
    assert payload["action"] == "install"
    assert payload["on_path"] is True
    assert payload["shims"][0]["written"] is True
    assert MARKER in text
    assert str(goat_root.resolve()) in text
    assert "uv run --project" in text
    assert "python -m goat" in text
    assert 'uv run --project "$GOAT_ROOT" goat' not in text
    assert "command -v goat" not in text
    assert shim.stat().st_mode & stat.S_IXUSR


def test_install_writes_windows_shims(tmp_path: Path, goat_root: Path):
    bin_dir = tmp_path / "bin"
    payload = install_cli(goat_root, bin_dir=bin_dir, system="Windows")
    cmd = (bin_dir / "goat.cmd").read_text(encoding="utf-8")
    bash = (bin_dir / "goat").read_text(encoding="utf-8")
    assert [item["name"] for item in payload["shims"]] == ["goat.cmd", "goat"]
    assert MARKER in cmd
    assert "uv run --project" in cmd
    assert "python -m goat" in cmd
    assert 'uv run --project "%GOAT_ROOT%" goat %*' not in cmd
    assert str(goat_root.resolve()) in cmd
    assert MARKER in bash
    assert goat_root.resolve().as_posix() in bash


def test_install_is_idempotent(tmp_path: Path, goat_root: Path):
    bin_dir = tmp_path / "bin"
    first = install_cli(goat_root, bin_dir=bin_dir, system="Linux")
    second = install_cli(goat_root, bin_dir=bin_dir, system="Linux")
    assert first["shims"][0]["written"] is True
    assert second["shims"][0]["written"] is True
    assert second["shims"][0]["ours"] is True


def test_install_refuses_foreign_file(tmp_path: Path, goat_root: Path):
    bin_dir = tmp_path / "bin"
    foreign = bin_dir / "goat"
    foreign.parent.mkdir()
    foreign.write_text("echo other\n", encoding="utf-8")
    try:
        install_cli(goat_root, bin_dir=bin_dir, system="Linux")
        raise AssertionError("expected GoatError")
    except GoatError as exc:
        assert "not a goat shim" in exc.message
    payload = install_cli(goat_root, bin_dir=bin_dir, system="Linux", force=True)
    assert payload["shims"][0]["written"] is True
    assert MARKER in foreign.read_text(encoding="utf-8")


def test_uninstall_removes_only_our_shim(tmp_path: Path, goat_root: Path):
    bin_dir = tmp_path / "bin"
    install_cli(goat_root, bin_dir=bin_dir, system="Linux")
    payload = uninstall_cli(goat_root, bin_dir=bin_dir, system="Linux")
    assert payload["action"] == "uninstall"
    assert payload["shims"][0]["removed"] is True
    assert not (bin_dir / "goat").exists()


def test_uninstall_refuses_foreign_file(tmp_path: Path, goat_root: Path):
    bin_dir = tmp_path / "bin"
    foreign = bin_dir / "goat"
    foreign.parent.mkdir()
    foreign.write_text("echo other\n", encoding="utf-8")
    try:
        uninstall_cli(goat_root, bin_dir=bin_dir, system="Linux")
        raise AssertionError("expected GoatError")
    except GoatError as exc:
        assert "not a goat shim" in exc.message
    uninstall_cli(goat_root, bin_dir=bin_dir, system="Linux", force=True)
    assert not foreign.exists()


def test_dry_run_does_not_write(tmp_path: Path, goat_root: Path):
    bin_dir = tmp_path / "bin"
    payload = install_cli(goat_root, bin_dir=bin_dir, system="Linux", dry_run=True)
    assert payload["dry_run"] is True
    assert payload["shims"][0]["would_write"] is True
    assert payload["shims"][0]["written"] is False
    assert not (bin_dir / "goat").exists()


def test_path_status_prefers_shim_over_venv_which(
    tmp_path: Path, goat_root: Path
):
    bin_dir = tmp_path / "bin"
    install_cli(goat_root, bin_dir=bin_dir, system="Linux")
    venv = tmp_path / "venv" / "goat"
    venv.parent.mkdir()
    venv.write_text("#!/bin/sh\n", encoding="utf-8")
    status = cli_path_status(
        goat_root,
        bin_dir=bin_dir,
        system="Linux",
        environ={"PATH": str(bin_dir)},
        which=lambda _name: str(venv),
    )
    assert status["on_path"] is True
    assert status["which"] == str(bin_dir / "goat")
    assert status["shadowed_by"] == str(venv)
    assert str(bin_dir / "goat") in status["detail"]
    assert str(venv) in status["detail"]


def test_path_status_ignores_kit_venv_shadow(
    tmp_path: Path, goat_root: Path
):
    bin_dir = tmp_path / "bin"
    install_cli(goat_root, bin_dir=bin_dir, system="Linux")
    venv = goat_root / ".venv" / "bin" / "goat"
    venv.parent.mkdir(parents=True)
    venv.write_text("#!/bin/sh\n", encoding="utf-8")
    status = cli_path_status(
        goat_root,
        bin_dir=bin_dir,
        system="Linux",
        environ={"PATH": str(bin_dir)},
        which=lambda _name: str(venv),
    )
    assert status["on_path"] is True
    assert status["which"] == str(bin_dir / "goat")
    assert status["shadowed_by"] is None
    assert ".venv" not in status["detail"]


def test_path_status_reports_missing_bin_dir(tmp_path: Path, goat_root: Path):
    bin_dir = tmp_path / "bin"
    install_cli(goat_root, bin_dir=bin_dir, system="Linux")
    status = cli_path_status(
        goat_root,
        bin_dir=bin_dir,
        system="Linux",
        environ={"PATH": str(tmp_path / "other")},
        which=lambda _name: None,
    )
    assert status["installed"] is True
    assert status["on_path"] is False
    assert status["path_hint"]
    assert "not on PATH" in status["detail"]


def test_resolve_install_root_prefers_cwd(tmp_path: Path, goat_root: Path, monkeypatch):
    monkeypatch.chdir(goat_root)
    monkeypatch.setenv("GOAT_ROOT", str(tmp_path))
    assert resolve_install_root() == goat_root.resolve()


def test_cli_install_and_text_format(
    tmp_path: Path, goat_root: Path, capsys, monkeypatch
):
    bin_dir = tmp_path / "bin"
    monkeypatch.chdir(goat_root)
    assert (
        main(
            [
                "--root",
                str(goat_root),
                "install",
                "--bin-dir",
                str(bin_dir),
                "--format",
                "text",
            ]
        )
        == 0
    )
    printed = capsys.readouterr().out
    assert "Installed goat PATH shim" in printed
    assert str(bin_dir / "goat") in printed
    payload = install_cli(goat_root, bin_dir=bin_dir, system="Linux")
    text = to_text(payload)
    assert "root:" in text
    assert "shim:" in text


def test_cli_install_works_without_catalog_load(
    tmp_path: Path, goat_root: Path, capsys, monkeypatch
):
    (goat_root / "catalog" / "stack.yaml").write_text("not: valid: yaml: [", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    monkeypatch.chdir(goat_root)
    assert main(["--root", str(goat_root), "install", "--bin-dir", str(bin_dir)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "cli_install"
    assert (bin_dir / "goat").exists()


def test_shim_quotes_awkward_root(tmp_path: Path):
    root = tmp_path / "kit's goat"
    root.mkdir()
    (root / "repositories.yml").write_text("parent_dir: ..\nrepositories: []\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    install_cli(root, bin_dir=bin_dir, system="Linux")
    text = (bin_dir / "goat").read_text(encoding="utf-8")
    assert "kit'\\''s goat" in text
    assert "GOAT_ROOT='" in text


def test_refresh_rewrites_shim_that_reinvokes_goat(tmp_path: Path):
    root = tmp_path / "kit's goat"
    root.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "goat"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        f"# {MARKER} 1\n"
        "set -euo pipefail\n"
        "export GOAT_ROOT='" + str(root).replace("'", "'\\''") + "'\n"
        'exec uv run --project "$GOAT_ROOT" goat "$@"\n',
        encoding="utf-8",
    )
    assert shim_reinvokes_goat(shim.read_text(encoding="utf-8"))
    rewritten = refresh_installed_shims(bin_dir)
    assert rewritten == [str(shim)]
    text = shim.read_text(encoding="utf-8")
    assert "python -m goat" in text
    assert not shim_reinvokes_goat(text)
    assert "kit'\\''s goat" in text
    assert refresh_installed_shims(bin_dir) == []


def test_shim_does_not_recurse_when_console_script_is_missing(tmp_path: Path):
    if not shutil.which("uv"):
        raise AssertionError("uv is required to run the installed shim")
    bin_dir = tmp_path / "bin"
    assert install_cli(REAL_ROOT, bin_dir=bin_dir, system="Linux")["action"] == "install"
    script = REAL_ROOT / ".venv" / "bin" / "goat"
    hidden = script.with_name("goat.hidden-by-test")
    if not script.exists():
        raise AssertionError(f"expected console script at {script}")
    script.rename(hidden)
    try:
        env = os.environ.copy()
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
        env.pop("UV_RUN_RECURSION_DEPTH", None)
        result = subprocess.run(
            [str(bin_dir / "goat"), "--version"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    finally:
        if hidden.exists():
            hidden.replace(script)
    assert result.returncode == 0, result.stderr
    assert "recursively invoked" not in result.stderr
    assert "goat" in result.stdout.lower()


def test_installed_shim_runs_commands(tmp_path: Path, monkeypatch):
    if not shutil.which("uv"):
        raise AssertionError("uv is required to run the installed shim")
    bin_dir = tmp_path / "bin"
    monkeypatch.chdir(REAL_ROOT)
    assert (
        main(["--root", str(REAL_ROOT), "install", "--bin-dir", str(bin_dir)]) == 0
    )
    shim = bin_dir / "goat"
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [str(shim), "commands"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "command_reference"
    names = {item["command"] for item in payload["commands"]}
    assert "install" in names
    assert "uninstall" in names

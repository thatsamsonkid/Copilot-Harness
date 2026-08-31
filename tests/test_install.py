from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

from coboose import CobooseError
from coboose.cli import main
from coboose.install import (
    MARKER,
    cli_path_status,
    install_cli,
    resolve_install_root,
    uninstall_cli,
)
from coboose.output import to_text

REAL_ROOT = Path(__file__).resolve().parents[1]


def test_install_writes_unix_shim(tmp_path: Path, coboose_root: Path):
    bin_dir = tmp_path / "bin"
    payload = install_cli(
        coboose_root,
        bin_dir=bin_dir,
        system="Linux",
        environ={"PATH": str(bin_dir)},
        which=lambda _name: str(bin_dir / "coboose") if (bin_dir / "coboose").exists() else None,
    )
    shim = bin_dir / "coboose"
    text = shim.read_text(encoding="utf-8")
    assert payload["action"] == "install"
    assert payload["on_path"] is True
    assert payload["shims"][0]["written"] is True
    assert MARKER in text
    assert str(coboose_root.resolve()) in text
    assert "uv run --project" in text
    assert "command -v coboose" not in text
    assert shim.stat().st_mode & stat.S_IXUSR


def test_install_writes_windows_shims(tmp_path: Path, coboose_root: Path):
    bin_dir = tmp_path / "bin"
    payload = install_cli(coboose_root, bin_dir=bin_dir, system="Windows")
    cmd = (bin_dir / "coboose.cmd").read_text(encoding="utf-8")
    bash = (bin_dir / "coboose").read_text(encoding="utf-8")
    assert [item["name"] for item in payload["shims"]] == ["coboose.cmd", "coboose"]
    assert MARKER in cmd
    assert "uv run --project" in cmd
    assert str(coboose_root.resolve()) in cmd
    assert MARKER in bash
    assert coboose_root.resolve().as_posix() in bash


def test_install_is_idempotent(tmp_path: Path, coboose_root: Path):
    bin_dir = tmp_path / "bin"
    first = install_cli(coboose_root, bin_dir=bin_dir, system="Linux")
    second = install_cli(coboose_root, bin_dir=bin_dir, system="Linux")
    assert first["shims"][0]["written"] is True
    assert second["shims"][0]["written"] is True
    assert second["shims"][0]["ours"] is True


def test_install_refuses_foreign_file(tmp_path: Path, coboose_root: Path):
    bin_dir = tmp_path / "bin"
    foreign = bin_dir / "coboose"
    foreign.parent.mkdir()
    foreign.write_text("echo other\n", encoding="utf-8")
    try:
        install_cli(coboose_root, bin_dir=bin_dir, system="Linux")
        raise AssertionError("expected CobooseError")
    except CobooseError as exc:
        assert "not a coboose shim" in exc.message
    payload = install_cli(coboose_root, bin_dir=bin_dir, system="Linux", force=True)
    assert payload["shims"][0]["written"] is True
    assert MARKER in foreign.read_text(encoding="utf-8")


def test_uninstall_removes_only_our_shim(tmp_path: Path, coboose_root: Path):
    bin_dir = tmp_path / "bin"
    install_cli(coboose_root, bin_dir=bin_dir, system="Linux")
    payload = uninstall_cli(coboose_root, bin_dir=bin_dir, system="Linux")
    assert payload["action"] == "uninstall"
    assert payload["shims"][0]["removed"] is True
    assert not (bin_dir / "coboose").exists()


def test_uninstall_refuses_foreign_file(tmp_path: Path, coboose_root: Path):
    bin_dir = tmp_path / "bin"
    foreign = bin_dir / "coboose"
    foreign.parent.mkdir()
    foreign.write_text("echo other\n", encoding="utf-8")
    try:
        uninstall_cli(coboose_root, bin_dir=bin_dir, system="Linux")
        raise AssertionError("expected CobooseError")
    except CobooseError as exc:
        assert "not a coboose shim" in exc.message
    uninstall_cli(coboose_root, bin_dir=bin_dir, system="Linux", force=True)
    assert not foreign.exists()


def test_dry_run_does_not_write(tmp_path: Path, coboose_root: Path):
    bin_dir = tmp_path / "bin"
    payload = install_cli(coboose_root, bin_dir=bin_dir, system="Linux", dry_run=True)
    assert payload["dry_run"] is True
    assert payload["shims"][0]["would_write"] is True
    assert payload["shims"][0]["written"] is False
    assert not (bin_dir / "coboose").exists()


def test_path_status_reports_missing_bin_dir(tmp_path: Path, coboose_root: Path):
    bin_dir = tmp_path / "bin"
    install_cli(coboose_root, bin_dir=bin_dir, system="Linux")
    status = cli_path_status(
        coboose_root,
        bin_dir=bin_dir,
        system="Linux",
        environ={"PATH": str(tmp_path / "other")},
        which=lambda _name: None,
    )
    assert status["installed"] is True
    assert status["on_path"] is False
    assert status["path_hint"]
    assert "not on PATH" in status["detail"]


def test_resolve_install_root_prefers_cwd(tmp_path: Path, coboose_root: Path, monkeypatch):
    monkeypatch.chdir(coboose_root)
    monkeypatch.setenv("COBOOSE_ROOT", str(tmp_path))
    assert resolve_install_root() == coboose_root.resolve()


def test_cli_install_and_text_format(
    tmp_path: Path, coboose_root: Path, capsys, monkeypatch
):
    bin_dir = tmp_path / "bin"
    monkeypatch.chdir(coboose_root)
    assert (
        main(
            [
                "--root",
                str(coboose_root),
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
    assert "Installed coboose PATH shim" in printed
    assert str(bin_dir / "coboose") in printed
    payload = install_cli(coboose_root, bin_dir=bin_dir, system="Linux")
    text = to_text(payload)
    assert "root:" in text
    assert "shim:" in text


def test_cli_install_works_without_catalog_load(
    tmp_path: Path, coboose_root: Path, capsys, monkeypatch
):
    (coboose_root / "catalog" / "stack.yaml").write_text("not: valid: yaml: [", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    monkeypatch.chdir(coboose_root)
    assert main(["--root", str(coboose_root), "install", "--bin-dir", str(bin_dir)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "cli_install"
    assert (bin_dir / "coboose").exists()


def test_shim_quotes_awkward_root(tmp_path: Path):
    root = tmp_path / "kit's coboose"
    root.mkdir()
    (root / "repositories.yml").write_text("parent_dir: ..\nrepositories: []\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    install_cli(root, bin_dir=bin_dir, system="Linux")
    text = (bin_dir / "coboose").read_text(encoding="utf-8")
    assert "kit'\\''s coboose" in text
    assert "COBOOSE_ROOT='" in text


def test_installed_shim_runs_commands(tmp_path: Path, monkeypatch):
    if not shutil.which("uv"):
        raise AssertionError("uv is required to run the installed shim")
    bin_dir = tmp_path / "bin"
    monkeypatch.chdir(REAL_ROOT)
    assert (
        main(["--root", str(REAL_ROOT), "install", "--bin-dir", str(bin_dir)]) == 0
    )
    shim = bin_dir / "coboose"
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

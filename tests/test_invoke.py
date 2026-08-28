from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from coboose.invoke import invoke_spec, terminal_env_settings


def _clean_uv_env() -> dict[str, str]:
    """Drop the coboose venv that `uv run pytest` injects, so spawn matches Copilot."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"VIRTUAL_ENV", "UV", "UV_PROJECT", "UV_RUN_RECURSION_DEPTH"}
        and not key.startswith("VIRTUAL_ENV_")
    }
    venv_bin = str((Path(__file__).resolve().parents[1] / ".venv" / "bin"))
    path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(
        part for part in path.split(os.pathsep) if part and part != venv_bin
    )
    return env


def test_invoke_spec_points_at_coboose_root(tmp_path: Path):
    root = tmp_path / "Coboose"
    root.mkdir()
    spec = invoke_spec(root)
    assert spec["cwd"] == str(root.resolve())
    assert "--project" in spec["command"]
    assert str(root.resolve()) in spec["command"]
    assert spec["command"].endswith(" coboose")
    assert spec["script"].endswith("scripts/coboose.sh")
    assert spec["windows_script"].endswith("scripts/coboose.ps1")
    assert "spawn" in spec["note"].lower()


def test_terminal_env_uses_named_coboose_folder():
    settings = terminal_env_settings()
    for key in (
        "terminal.integrated.env.linux",
        "terminal.integrated.env.osx",
        "terminal.integrated.env.windows",
    ):
        assert settings[key]["COBOOSE_ROOT"] == "${workspaceFolder:coboose}"
        assert "COBOOSE_WORKSPACE" not in settings[key]
        assert "HARNESS_ROOT" not in settings[key]


def test_terminal_env_single_root_folder():
    settings = terminal_env_settings(folder_name=None)
    assert settings["terminal.integrated.env.linux"]["COBOOSE_ROOT"] == "${workspaceFolder}"
    assert "HARNESS_ROOT" not in settings["terminal.integrated.env.linux"]
    assert "UV_PROJECT" not in settings["terminal.integrated.env.linux"]


def test_terminal_env_stamps_workspace_id():
    settings = terminal_env_settings(workspace_id="frontend")
    env = settings["terminal.integrated.env.linux"]
    assert env["COBOOSE_ROOT"] == "${workspaceFolder:coboose}"
    assert env["COBOOSE_WORKSPACE"] == "frontend"
    assert env["COBOOSE_WORKSPACE_FILE"] == "${workspaceFile}"


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is required for spawn check")
def test_uv_run_coboose_spawns_from_sibling_with_project(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    sibling = tmp_path / "frontend"
    sibling.mkdir()
    env = _clean_uv_env()
    bare = subprocess.run(
        ["uv", "run", "coboose", "--version"],
        cwd=sibling,
        env=env,
        capture_output=True,
        text=True,
    )
    assert bare.returncode != 0
    combined = (bare.stdout + bare.stderr).lower()
    assert "spawn" in combined or "pyproject" in combined or "project" in combined

    pinned = subprocess.run(
        ["uv", "run", "--project", str(repo), "coboose", "--version"],
        cwd=sibling,
        env=env,
        capture_output=True,
        text=True,
    )
    assert pinned.returncode == 0, pinned.stderr
    assert "coboose" in pinned.stdout.lower() or pinned.stdout.strip()

    script = repo / "scripts" / "coboose.sh"
    wrapped = subprocess.run(
        [str(script), "--version"],
        cwd=sibling,
        env=env,
        capture_output=True,
        text=True,
    )
    assert wrapped.returncode == 0, wrapped.stderr

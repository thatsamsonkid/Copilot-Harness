from __future__ import annotations

from pathlib import Path

import pytest

from coboose import CobooseError
from coboose.launch import (
    load_launch_runtime,
    read_jsonc,
    resolve_launch_value,
    select_configuration,
    strip_jsonc,
    summarize_launch,
)


def test_strip_jsonc_keeps_slashes_in_strings():
    text = '{ "url": "https://example.com/path", "n": 1, }'
    assert '"url": "https://example.com/path"' in strip_jsonc(text)
    data = __import__("json").loads(strip_jsonc(text))
    assert data["n"] == 1


def test_read_jsonc_launch_file(tmp_path: Path):
    path = tmp_path / "launch.json"
    path.write_text(
        """// header
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Launch Backend",
      "type": "java",
      "request": "launch",
    },
  ],
}
""",
        encoding="utf-8",
    )
    data = read_jsonc(path)
    assert data["configurations"][0]["name"] == "Launch Backend"


def test_summarize_launch_redacts_values(tmp_path: Path):
    vscode = tmp_path / ".vscode"
    vscode.mkdir()
    (vscode / "launch.json").write_text(
        """{
  "configurations": [
    {
      "name": "Launch Backend",
      "type": "java",
      "request": "launch",
      "mainClass": "com.example.Api",
      "args": "--password=hidden-arg",
      "env": { "DB_PASSWORD": "hidden-env" },
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("EXTRA=hidden-file\n", encoding="utf-8")
    summary = summarize_launch(tmp_path, kind="spring-boot", repo_name="backend")
    assert summary is not None
    assert summary["configuration"] == "Launch Backend"
    assert summary["main_class"] == "com.example.Api"
    assert summary["env_keys"] == ["DB_PASSWORD"]
    assert summary["env_file"] == ".env"
    assert "EXTRA" in summary["env_file_keys"]
    assert summary["secret_risk"] is True
    dumped = str(summary)
    assert "hidden-env" not in dumped
    assert "hidden-arg" not in dumped
    assert "hidden-file" not in dumped


def test_resolve_launch_value_workspace_and_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME_TOKEN", "from-parent")
    sibling = tmp_path.parent / "frontend"
    value = resolve_launch_value(
        "${workspaceFolder}/cfg:${workspaceFolder:frontend}:${env:HOME_TOKEN}",
        tmp_path,
        environ={"HOME_TOKEN": "from-parent"},
        workspace_folders={"frontend": sibling},
    )
    assert value == f"{tmp_path}/cfg:{sibling}:from-parent"


def test_load_launch_runtime_resolves_env_substitutions(tmp_path: Path):
    vscode = tmp_path / ".vscode"
    vscode.mkdir()
    (vscode / "launch.json").write_text(
        """{
  "configurations": [
    {
      "name": "Launch Backend",
      "type": "java",
      "request": "launch",
      "env": {
        "CONFIG_DIR": "${workspaceFolder}/config",
        "COPIED": "${env:PARENT_ONLY}"
      },
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("FILE_KEY=from-file\n", encoding="utf-8")
    runtime = load_launch_runtime(
        tmp_path,
        None,
        environ={"PARENT_ONLY": "parent-value"},
    )
    assert runtime["env"]["CONFIG_DIR"] == f"{tmp_path}/config"
    assert runtime["env"]["COPIED"] == "parent-value"
    assert runtime["env"]["FILE_KEY"] == "from-file"
    dumped = str(runtime)
    assert "parent-value" in dumped
    assert "from-file" in dumped


def test_select_configuration_requires_known_name():
    with pytest.raises(CobooseError, match="no configuration named"):
        select_configuration(
            [{"name": "Launch Backend", "request": "launch"}],
            name="Missing",
            required=True,
        )

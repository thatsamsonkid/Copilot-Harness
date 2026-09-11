from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from goat.read_hooks import (
    DEFAULT_MAX_LINES,
    ROUTING_CONTEXT,
    decide_bash_read,
    decide_file_size,
    has_unquoted_pipe,
    max_lines,
    reader_file_paths,
    routing_hook_output,
)

HOOKS = Path(__file__).resolve().parents[1] / ".github" / "hooks"


def _write_lines(path: Path, count: int) -> Path:
    path.write_text("\n".join(f"line-{i}" for i in range(count)) + "\n", encoding="utf-8")
    return path


def test_default_threshold_is_350():
    assert DEFAULT_MAX_LINES == 350
    assert max_lines(environ={}) == 350


def test_env_overrides_threshold(tmp_path: Path):
    assert max_lines(environ={"GOAT_BULK_READ_MAX_LINES": "12"}, goat_root=tmp_path) == 12


def test_read_guard_json_sets_threshold(tmp_path: Path):
    config = tmp_path / ".github" / "hooks"
    config.mkdir(parents=True)
    config.joinpath("read-guard.json").write_text('{"max_lines": 20}\n', encoding="utf-8")
    assert max_lines(environ={}, goat_root=tmp_path) == 20


def test_small_read_is_allowed(tmp_path: Path):
    path = _write_lines(tmp_path / "small.py", 10)
    decision = decide_file_size(
        {"tool_name": "Read", "tool_input": {"file_path": str(path)}, "cwd": str(tmp_path)},
        environ={"GOAT_BULK_READ_MAX_LINES": "20"},
        goat_root=tmp_path,
    )
    assert decision["permissionDecision"] == "allow"


def test_large_read_is_denied(tmp_path: Path):
    path = _write_lines(tmp_path / "big.py", 40)
    decision = decide_file_size(
        {"toolName": "view", "toolArgs": {"filePath": str(path)}, "cwd": str(tmp_path)},
        environ={"GOAT_BULK_READ_MAX_LINES": "20"},
        goat_root=tmp_path,
    )
    assert decision["permissionDecision"] == "deny"
    reason = decision["permissionDecisionReason"]
    assert "/bulk-reader" in reason
    assert "40 lines" in reason
    assert "debugging" in reason
    assert "architectural decisions" in reason
    assert "safety-critical" in reason
    assert "targeted Read" in reason


def test_targeted_limit_passes(tmp_path: Path):
    path = _write_lines(tmp_path / "big.py", 40)
    decision = decide_file_size(
        {
            "tool_name": "Read",
            "tool_input": {"file_path": str(path), "limit": 15},
            "cwd": str(tmp_path),
        },
        environ={"GOAT_BULK_READ_MAX_LINES": "20"},
        goat_root=tmp_path,
    )
    assert decision["permissionDecision"] == "allow"


def test_missing_file_is_allowed(tmp_path: Path):
    decision = decide_file_size(
        {
            "tool_name": "Read",
            "tool_input": {"file_path": str(tmp_path / "missing.py")},
            "cwd": str(tmp_path),
        },
        environ={"GOAT_BULK_READ_MAX_LINES": "20"},
        goat_root=tmp_path,
    )
    assert decision["permissionDecision"] == "allow"


def test_other_tools_are_ignored(tmp_path: Path):
    path = _write_lines(tmp_path / "big.py", 40)
    decision = decide_file_size(
        {"tool_name": "edit", "tool_input": {"file_path": str(path)}, "cwd": str(tmp_path)},
        environ={"GOAT_BULK_READ_MAX_LINES": "20"},
        goat_root=tmp_path,
    )
    assert decision["permissionDecision"] == "allow"


def test_cat_large_file_is_denied(tmp_path: Path):
    path = _write_lines(tmp_path / "big.py", 40)
    decision = decide_bash_read(
        {"tool_name": "bash", "tool_input": {"command": f"cat {path}"}, "cwd": str(tmp_path)},
        environ={"GOAT_BULK_READ_MAX_LINES": "20"},
        goat_root=tmp_path,
    )
    assert decision["permissionDecision"] == "deny"
    assert "/bulk-reader" in decision["permissionDecisionReason"]


def test_piped_cat_passes(tmp_path: Path):
    path = _write_lines(tmp_path / "big.py", 40)
    decision = decide_bash_read(
        {
            "tool_name": "Bash",
            "tool_input": {"command": f"cat {path} | grep line-1"},
            "cwd": str(tmp_path),
        },
        environ={"GOAT_BULK_READ_MAX_LINES": "20"},
        goat_root=tmp_path,
    )
    assert decision["permissionDecision"] == "allow"


def test_head_with_line_count_is_targeted(tmp_path: Path):
    path = _write_lines(tmp_path / "big.py", 40)
    decision = decide_bash_read(
        {
            "tool_name": "runCommands",
            "tool_input": {"command": f"head -n 5 {path}"},
            "cwd": str(tmp_path),
        },
        environ={"GOAT_BULK_READ_MAX_LINES": "20"},
        goat_root=tmp_path,
    )
    assert decision["permissionDecision"] == "allow"


def test_reader_file_paths_skips_pipes_and_flags():
    assert reader_file_paths("cat foo.py | grep x") == []
    assert reader_file_paths("cat foo.py") == ["foo.py"]
    assert reader_file_paths("head -n 3 foo.py") == []
    assert reader_file_paths("less foo.py") == ["foo.py"]
    assert has_unquoted_pipe('echo "a | b" && cat foo.py') is False
    assert has_unquoted_pipe("cat foo.py | grep x") is True


def test_routing_hook_excludes_reasoning_and_edits():
    output = routing_hook_output()
    text = output["additionalContext"].lower()
    assert "debugging" in text
    assert "architectural decisions" in text
    assert "safety-critical" in text
    assert "do not edit from bulk reader bullets" in text
    assert ROUTING_CONTEXT in output["hookSpecificOutput"]["additionalContext"]


def test_hook_json_files_are_valid():
    for name in (
        "check-file-size.json",
        "check-bash-read.json",
        "read-guard.json",
        "bulk-read-routing.json",
        "implement-gate.json",
    ):
        data = json.loads((HOOKS / name).read_text(encoding="utf-8"))
        assert isinstance(data, dict)
    size = json.loads((HOOKS / "check-file-size.json").read_text(encoding="utf-8"))
    bash = json.loads((HOOKS / "check-bash-read.json").read_text(encoding="utf-8"))
    assert size["version"] == 1
    assert "preToolUse" in size["hooks"]
    assert "preToolUse" in bash["hooks"]
    assert (HOOKS / "check_file_size.py").is_file()
    assert (HOOKS / "check_bash_read.py").is_file()


def test_hook_scripts_emit_json(tmp_path: Path):
    path = _write_lines(tmp_path / "big.py", 40)
    env = {**os.environ, "GOAT_BULK_READ_MAX_LINES": "20"}
    payload = json.dumps(
        {"tool_name": "Read", "tool_input": {"file_path": str(path)}, "cwd": str(tmp_path)}
    )
    import subprocess

    result = subprocess.run(
        [sys.executable, str(HOOKS / "check_file_size.py")],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    body = json.loads(result.stdout)
    assert body["permissionDecision"] == "deny"

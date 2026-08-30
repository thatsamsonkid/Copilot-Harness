from __future__ import annotations

import json
from pathlib import Path

from coboose.cli import build_parser, main
from coboose.commands import collect_commands, command_reference
from coboose.output import to_markdown, to_text

DOCS = Path(__file__).resolve().parents[1] / "docs" / "cli.md"

EXPECTED = {
    "bootstrap",
    "branch",
    "catalog",
    "clone",
    "commands",
    "context",
    "doctor",
    "env list",
    "env set",
    "env unset",
    "figma comments",
    "figma images",
    "figma login",
    "figma logout",
    "figma nodes",
    "figma schema",
    "figma whoami",
    "handoff latest",
    "handoff list",
    "handoff write",
    "init",
    "jira comments",
    "jira context",
    "jira get",
    "jira login",
    "jira logout",
    "jira mine",
    "jira schema",
    "jira search",
    "jira whoami",
    "prepare",
    "repos",
    "skills lift",
    "skills list",
    "skills pull",
    "start",
    "start env",
    "start run",
    "status",
    "templates",
    "workspace create",
    "workspace current",
    "workspace generate",
    "workspace list",
    "workspace match",
    "workspace open",
    "workspace path",
}


def test_parser_catalog_matches_expected_commands():
    names = {item["command"] for item in collect_commands(build_parser())}
    assert names == EXPECTED


def test_commands_does_not_need_catalog(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["commands"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "command_reference"
    assert payload["count"] == len(EXPECTED)
    names = [item["command"] for item in payload["commands"]]
    assert names == sorted(
        EXPECTED,
        key=lambda name: (
            payload["groups"].index(name.split()[0]),
            name,
        ),
    )
    assert {flag["name"] for flag in payload["shared"]} == {
        "--format",
        "--catalog",
        "--repos",
        "--templates",
        "--root",
    }


def test_help_is_alias_for_commands(capsys):
    assert main(["help"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "command_reference"
    assert payload["count"] == len(EXPECTED)


def test_commands_filters_by_group(capsys):
    assert main(["commands", "jira"]) == 0
    payload = json.loads(capsys.readouterr().out)
    names = [item["command"] for item in payload["commands"]]
    assert names == [
        "jira comments",
        "jira context",
        "jira get",
        "jira login",
        "jira logout",
        "jira mine",
        "jira schema",
        "jira search",
        "jira whoami",
    ]
    assert payload["groups"] == ["jira"]


def test_commands_filters_by_command_prefix(capsys):
    assert main(["commands", "start"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [item["command"] for item in payload["commands"]] == [
        "start",
        "start env",
        "start run",
    ]


def test_unknown_group_is_json_error(capsys):
    assert main(["commands", "nope"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert "Unknown command group" in error["error"]
    assert "jira" in error["error"]


def test_usage_includes_positionals():
    payload = command_reference(build_parser())
    by_name = {item["command"]: item for item in payload["commands"]}
    assert by_name["jira get"]["usage"] == "coboose jira get ISSUE"
    assert by_name["prepare"]["usage"] == "coboose prepare ISSUE"
    assert by_name["commands"]["usage"] == "coboose commands [GROUP]"
    assert by_name["workspace create"]["usage"] == "coboose workspace create [ID]"
    assert "--from-env" in {arg["name"] for arg in by_name["jira login"]["arguments"]}


def test_markdown_and_text_are_scannable():
    payload = command_reference(build_parser())
    markdown = to_markdown(payload)
    text = to_text(payload)
    assert markdown.startswith("# Coboose CLI")
    assert "| `coboose jira get ISSUE` | Fetch one issue |" in markdown
    assert "## `start`" in markdown
    assert "Shared flags" in markdown
    assert text.startswith("Coboose CLI (")
    assert "coboose jira get ISSUE" in text
    assert "Fetch one issue" in text


def test_docs_quick_reference_lists_every_command():
    docs = DOCS.read_text(encoding="utf-8")
    missing = [
        name for name in sorted(EXPECTED) if f"`coboose {name}" not in docs
    ]
    assert missing == []
    assert "uv run coboose commands" in docs

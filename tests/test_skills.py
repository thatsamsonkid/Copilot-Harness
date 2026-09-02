from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from goat import GoatError
from goat.cli import main
from goat.onboard import run_init
from goat.prompt import PromptSession
from goat.skills import (
    compact_sync_result,
    format_skill_menu,
    lift_skills,
    list_skills,
    parse_skill_selection,
    pull_skills,
    sync_root_skills,
)


def _write_skill(
    root: Path,
    name: str,
    description: str = "A test skill",
    *,
    location: str = ".github/skills",
    extra: str | None = None,
) -> Path:
    directory = root / location / name if location else root / name
    directory.mkdir(parents=True, exist_ok=True)
    directory.joinpath("SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    if extra:
        directory.joinpath("notes.md").write_text(extra, encoding="utf-8")
    return directory


def _sibling(goat_root: Path, name: str) -> Path:
    path = goat_root.parent / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_list_finds_goat_and_sibling_skills(catalog, goat_root: Path):
    _write_skill(goat_root, "get-started", "First run")
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout flow")
    _write_skill(frontend, "lint", "Lint the UI", location=".agents/skills")

    payload = list_skills(catalog, goat_root, all_repos=True)
    names = {(item["source_id"], item["name"]) for item in payload["available"]}
    assert ("goat", "get-started") in names
    assert ("frontend", "checkout") in names
    assert ("frontend", "lint") in names
    assert payload["dest"].endswith(".github/skills")
    assert payload["dest_kind"] == "workspace"
    assert "sources" in payload


def test_compact_sync_result_is_names_only():
    summary = compact_sync_result(
        {
            "ok": True,
            "copied": [{"name": "checkout", "path": "/tmp/checkout"}],
            "updated": [{"installed_as": "frontend--lint"}],
            "conflicts": [{"name": "jira-cli"}],
            "available": [{"name": "checkout", "body": "huge"}],
            "sources": [{"id": "frontend"}],
            "guidance": ["do not commit"],
            "next_commands": ["uv run goat skills lift"],
        }
    )
    assert summary == {
        "ok": True,
        "copied": ["checkout"],
        "updated": ["frontend--lint"],
        "conflicts": ["jira-cli"],
    }


def test_list_brief_is_name_and_description(catalog, goat_root: Path):
    _write_skill(goat_root, "get-started", "First run")
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout flow")

    payload = list_skills(catalog, goat_root, all_repos=True, brief=True)
    assert payload["brief"] is True
    assert "sources" not in payload
    assert "workspace_scope" not in payload
    assert "guidance" not in payload
    checkout = next(item for item in payload["skills"] if item["name"] == "checkout")
    assert checkout == {
        "name": "checkout",
        "description": "Checkout flow",
        "source_id": "frontend",
        "pick": "frontend:checkout",
    }
    assert set(checkout) == {"name", "description", "source_id", "pick"}


def test_lift_copies_sibling_and_skips_native_goat(catalog, goat_root: Path):
    native = _write_skill(goat_root, "get-started", "First run")
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout flow", extra="keep me")

    payload = lift_skills(catalog, goat_root, all_repos=True)
    assert {item["name"] for item in payload["native"]} == {"get-started"}
    assert {item["name"] for item in payload["copied"]} == {"checkout"}
    dest = goat_root / ".github" / "skills" / "checkout"
    assert dest.joinpath("SKILL.md").is_file()
    assert dest.joinpath("notes.md").read_text(encoding="utf-8") == "keep me"
    marker = json.loads(dest.joinpath(".goat-source.json").read_text(encoding="utf-8"))
    assert marker["source_id"] == "frontend"
    assert native.joinpath("SKILL.md").is_file()
    assert not (native / ".goat-source.json").exists()
    ignore = (goat_root / ".github" / "skills" / ".gitignore").read_text(encoding="utf-8")
    assert "checkout/" in ignore
    assert "get-started/" not in ignore


def test_lift_prefixes_when_name_collides_with_native(catalog, goat_root: Path):
    _write_skill(goat_root, "jira-cli", "Goat Jira")
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "jira-cli", "Frontend Jira helper")

    payload = lift_skills(catalog, goat_root, all_repos=True)
    assert {item["installed_as"] for item in payload["copied"]} == {"frontend--jira-cli"}
    assert (goat_root / ".github" / "skills" / "frontend--jira-cli" / "SKILL.md").is_file()
    assert not (goat_root / ".github" / "skills" / "jira-cli" / ".goat-source.json").exists()


def test_lift_is_idempotent_and_updates(catalog, goat_root: Path):
    frontend = _sibling(goat_root, "frontend")
    skill = _write_skill(frontend, "checkout", "v1")
    first = lift_skills(catalog, goat_root, all_repos=True)
    assert first["copied"]
    skill.joinpath("SKILL.md").write_text(
        "---\nname: checkout\ndescription: v2\n---\n\n# checkout\n",
        encoding="utf-8",
    )
    second = lift_skills(catalog, goat_root, all_repos=True)
    assert not second["copied"]
    assert {item["name"] for item in second["updated"]} == {"checkout"}
    dest = goat_root / ".github" / "skills" / "checkout" / "SKILL.md"
    assert "v2" in dest.read_text(encoding="utf-8")


def test_lift_only_filters_by_pick(catalog, goat_root: Path):
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    _write_skill(frontend, "lint", "Lint")
    payload = lift_skills(
        catalog,
        goat_root,
        all_repos=True,
        names=["frontend:lint"],
    )
    assert {item["name"] for item in payload["copied"]} == {"lint"}
    assert not (goat_root / ".github" / "skills" / "checkout").exists()


def test_lift_dry_run_does_not_write(catalog, goat_root: Path):
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    payload = lift_skills(catalog, goat_root, all_repos=True, dry_run=True)
    assert payload["copied"]
    assert not (goat_root / ".github" / "skills" / "checkout").exists()


def test_lift_to_parent_copies_goat_skills(catalog, goat_root: Path):
    _write_skill(goat_root, "get-started", "First run")
    payload = lift_skills(catalog, goat_root, parent=True, all_repos=True)
    dest = goat_root.parent / ".github" / "skills" / "get-started"
    assert dest.joinpath("SKILL.md").is_file()
    assert dest.joinpath(".goat-source.json").is_file()
    assert payload["dest"] == str(dest.parent)
    assert payload["copied"]


def test_pull_lists_when_no_selection(catalog, goat_root: Path):
    def run(command, cwd):
        dest = Path(command[-1])
        dest.mkdir(parents=True)
        _write_skill(dest, "review", "Review diffs")
        _write_skill(dest, "commit", "Commit help", location="")

    payload = pull_skills(
        catalog,
        goat_root,
        "https://github.com/acme/agent-skills.git",
        run=run,
    )
    assert payload["needs_selection"] is True
    names = {item["name"] for item in payload["available"]}
    assert names == {"review", "commit"}
    assert "skills pull" in payload["install_command"]
    assert not (goat_root / ".github" / "skills" / "review").exists()


def test_pull_installs_selected(catalog, goat_root: Path):
    def run(command, cwd):
        dest = Path(command[-1])
        dest.mkdir(parents=True)
        _write_skill(dest, "review", "Review diffs", extra="prompt")
        _write_skill(dest, "commit", "Commit help")

    payload = pull_skills(
        catalog,
        goat_root,
        "https://github.com/acme/agent-skills.git",
        names=["review"],
        run=run,
    )
    assert payload["needs_selection"] is False
    assert {item["name"] for item in payload["copied"]} == {"review"}
    dest = goat_root / ".github" / "skills" / "review"
    assert dest.joinpath("notes.md").read_text(encoding="utf-8") == "prompt"
    marker = json.loads(dest.joinpath(".goat-source.json").read_text(encoding="utf-8"))
    assert marker["source_kind"] == "remote"
    assert not (goat_root / ".github" / "skills" / "commit").exists()


def test_pull_all_installs_every_skill(catalog, goat_root: Path):
    def run(command, cwd):
        dest = Path(command[-1])
        dest.mkdir(parents=True)
        _write_skill(dest, "one", "One")
        _write_skill(dest, "two", "Two")

    payload = pull_skills(
        catalog,
        goat_root,
        "git@github.com:acme/agent-skills.git",
        all_skills=True,
        https=True,
        run=run,
    )
    assert {item["name"] for item in payload["copied"]} == {"one", "two"}
    assert payload["url"].startswith("https://github.com/")


def test_cli_skills_list_and_lift(catalog, goat_root: Path, capsys, monkeypatch):
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    monkeypatch.chdir(goat_root)
    assert main(["--root", str(goat_root), "skills", "list", "--all"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert any(item["name"] == "checkout" for item in listed["available"])

    assert main(["--root", str(goat_root), "skills", "list", "--all", "--brief"]) == 0
    brief = json.loads(capsys.readouterr().out)
    assert brief["brief"] is True
    assert "sources" not in brief
    checkout = next(item for item in brief["skills"] if item["name"] == "checkout")
    assert set(checkout) == {"name", "description", "source_id", "pick"}

    assert main(["--root", str(goat_root), "skills", "lift", "--all", "--all-skills"]) == 0
    lifted = json.loads(capsys.readouterr().out)
    assert any(item["name"] == "checkout" for item in lifted["copied"])
    assert (goat_root / ".github" / "skills" / "checkout" / "SKILL.md").is_file()


def test_cli_lift_without_selection_asks(catalog, goat_root: Path, capsys, monkeypatch):
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    monkeypatch.chdir(goat_root)
    assert main(["--root", str(goat_root), "skills", "lift", "--all"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["needs_selection"] is True
    assert payload["brief"] is True
    assert any(item["name"] == "checkout" for item in payload["available"])
    assert not (goat_root / ".github" / "skills" / "checkout").exists()


def test_lift_prompts_in_a_terminal(catalog, goat_root: Path):
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout flow")
    _write_skill(frontend, "lint", "Lint the UI")
    stderr = io.StringIO()
    prompt = PromptSession(stdin=io.StringIO("1\n"), stderr=stderr, interactive=True)
    payload = lift_skills(catalog, goat_root, all_repos=True, prompt=prompt)
    assert {item["name"] for item in payload["copied"]} == {"checkout"}
    menu = stderr.getvalue()
    assert "1. checkout (frontend)" in menu
    assert "2. lint (frontend)" in menu
    assert "or all" in menu
    assert not (goat_root / ".github" / "skills" / "lint").exists()


def test_lift_prompt_all_copies_siblings(catalog, goat_root: Path):
    _write_skill(goat_root, "get-started", "First run")
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    _write_skill(frontend, "lint", "Lint")
    prompt = PromptSession(
        stdin=io.StringIO("all\n"),
        stderr=io.StringIO(),
        interactive=True,
    )
    payload = lift_skills(catalog, goat_root, all_repos=True, prompt=prompt)
    assert {item["name"] for item in payload["copied"]} == {"checkout", "lint"}
    assert not (goat_root / ".github" / "skills" / "get-started" / ".goat-source.json").exists()


def test_parse_skill_selection_numbers_ranges_and_all():
    available = [
        {"name": "checkout", "pick": "frontend:checkout", "source_id": "frontend"},
        {"name": "lint", "pick": "frontend:lint", "source_id": "frontend"},
        {"name": "api", "pick": "backend:api", "source_id": "backend"},
    ]
    assert parse_skill_selection("1", available) == ["frontend:checkout"]
    assert parse_skill_selection("1-2", available) == ["frontend:checkout", "frontend:lint"]
    assert parse_skill_selection("lint, backend:api", available) == [
        "frontend:lint",
        "backend:api",
    ]
    assert parse_skill_selection("all", available) == [
        "frontend:checkout",
        "frontend:lint",
        "backend:api",
    ]
    with pytest.raises(GoatError, match="out of range"):
        parse_skill_selection("9", available)
    with pytest.raises(GoatError, match="Unknown skill"):
        parse_skill_selection("missing", available)


def test_format_skill_menu_is_name_and_description():
    menu = format_skill_menu(
        [
            {
                "name": "checkout",
                "source_id": "frontend",
                "description": "Checkout flow. Extra detail that should be clipped.",
            }
        ]
    )
    assert "1. checkout (frontend)" in menu
    assert "Checkout flow." in menu
    assert "Extra detail" not in menu
    assert "or all" in menu


def test_init_lifts_sibling_skills(catalog, goat_root: Path, monkeypatch):
    for name in (
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "JIRA_USERNAME",
        "JIRA_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    payload = run_init(catalog, goat_root)
    ids = {step["id"]: step for step in payload["steps"]}
    assert "skills" in ids
    assert ids["skills"]["optional"] is True
    assert any(item["name"] == "checkout" for item in payload["skills"]["copied"])
    assert "uv run goat skills lift" in payload["next_commands"]


def test_sync_does_not_raise_when_dest_is_a_file(catalog, goat_root: Path):
    dest = goat_root / ".github" / "skills"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("not a directory", encoding="utf-8")
    frontend = _sibling(goat_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    payload = sync_root_skills(catalog, goat_root, all_repos=True)
    assert payload["ok"] is False
    assert payload.get("error")

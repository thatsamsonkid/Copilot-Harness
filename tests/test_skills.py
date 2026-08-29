from __future__ import annotations

import json
from pathlib import Path

from coboose.cli import main
from coboose.onboard import run_init
from coboose.skills import lift_skills, list_skills, pull_skills, sync_root_skills


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


def _sibling(coboose_root: Path, name: str) -> Path:
    path = coboose_root.parent / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_list_finds_coboose_and_sibling_skills(catalog, coboose_root: Path):
    _write_skill(coboose_root, "get-started", "First run")
    frontend = _sibling(coboose_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout flow")
    _write_skill(frontend, "lint", "Lint the UI", location=".agents/skills")

    payload = list_skills(catalog, coboose_root, all_repos=True)
    names = {(item["source_id"], item["name"]) for item in payload["available"]}
    assert ("coboose", "get-started") in names
    assert ("frontend", "checkout") in names
    assert ("frontend", "lint") in names
    assert payload["dest"].endswith(".github/skills")
    assert payload["dest_kind"] == "workspace"


def test_lift_copies_sibling_and_skips_native_coboose(catalog, coboose_root: Path):
    native = _write_skill(coboose_root, "get-started", "First run")
    frontend = _sibling(coboose_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout flow", extra="keep me")

    payload = lift_skills(catalog, coboose_root, all_repos=True)
    assert {item["name"] for item in payload["native"]} == {"get-started"}
    assert {item["name"] for item in payload["copied"]} == {"checkout"}
    dest = coboose_root / ".github" / "skills" / "checkout"
    assert dest.joinpath("SKILL.md").is_file()
    assert dest.joinpath("notes.md").read_text(encoding="utf-8") == "keep me"
    marker = json.loads(dest.joinpath(".coboose-source.json").read_text(encoding="utf-8"))
    assert marker["source_id"] == "frontend"
    assert native.joinpath("SKILL.md").is_file()
    assert not (native / ".coboose-source.json").exists()
    ignore = (coboose_root / ".github" / "skills" / ".gitignore").read_text(encoding="utf-8")
    assert "checkout/" in ignore
    assert "get-started/" not in ignore


def test_lift_prefixes_when_name_collides_with_native(catalog, coboose_root: Path):
    _write_skill(coboose_root, "jira-cli", "Coboose Jira")
    frontend = _sibling(coboose_root, "frontend")
    _write_skill(frontend, "jira-cli", "Frontend Jira helper")

    payload = lift_skills(catalog, coboose_root, all_repos=True)
    assert {item["installed_as"] for item in payload["copied"]} == {"frontend--jira-cli"}
    assert (coboose_root / ".github" / "skills" / "frontend--jira-cli" / "SKILL.md").is_file()
    assert not (coboose_root / ".github" / "skills" / "jira-cli" / ".coboose-source.json").exists()


def test_lift_is_idempotent_and_updates(catalog, coboose_root: Path):
    frontend = _sibling(coboose_root, "frontend")
    skill = _write_skill(frontend, "checkout", "v1")
    first = lift_skills(catalog, coboose_root, all_repos=True)
    assert first["copied"]
    skill.joinpath("SKILL.md").write_text(
        "---\nname: checkout\ndescription: v2\n---\n\n# checkout\n",
        encoding="utf-8",
    )
    second = lift_skills(catalog, coboose_root, all_repos=True)
    assert not second["copied"]
    assert {item["name"] for item in second["updated"]} == {"checkout"}
    dest = coboose_root / ".github" / "skills" / "checkout" / "SKILL.md"
    assert "v2" in dest.read_text(encoding="utf-8")


def test_lift_only_filters_by_pick(catalog, coboose_root: Path):
    frontend = _sibling(coboose_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    _write_skill(frontend, "lint", "Lint")
    payload = lift_skills(
        catalog,
        coboose_root,
        all_repos=True,
        names=["frontend:lint"],
    )
    assert {item["name"] for item in payload["copied"]} == {"lint"}
    assert not (coboose_root / ".github" / "skills" / "checkout").exists()


def test_lift_dry_run_does_not_write(catalog, coboose_root: Path):
    frontend = _sibling(coboose_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    payload = lift_skills(catalog, coboose_root, all_repos=True, dry_run=True)
    assert payload["copied"]
    assert not (coboose_root / ".github" / "skills" / "checkout").exists()


def test_lift_to_parent_copies_coboose_skills(catalog, coboose_root: Path):
    _write_skill(coboose_root, "get-started", "First run")
    payload = lift_skills(catalog, coboose_root, parent=True, all_repos=True)
    dest = coboose_root.parent / ".github" / "skills" / "get-started"
    assert dest.joinpath("SKILL.md").is_file()
    assert dest.joinpath(".coboose-source.json").is_file()
    assert payload["dest"] == str(dest.parent)
    assert payload["copied"]


def test_pull_lists_when_no_selection(catalog, coboose_root: Path):
    def run(command, cwd):
        dest = Path(command[-1])
        dest.mkdir(parents=True)
        _write_skill(dest, "review", "Review diffs")
        _write_skill(dest, "commit", "Commit help", location="")

    payload = pull_skills(
        catalog,
        coboose_root,
        "https://github.com/acme/agent-skills.git",
        run=run,
    )
    assert payload["needs_selection"] is True
    names = {item["name"] for item in payload["available"]}
    assert names == {"review", "commit"}
    assert "skills pull" in payload["install_command"]
    assert not (coboose_root / ".github" / "skills" / "review").exists()


def test_pull_installs_selected(catalog, coboose_root: Path):
    def run(command, cwd):
        dest = Path(command[-1])
        dest.mkdir(parents=True)
        _write_skill(dest, "review", "Review diffs", extra="prompt")
        _write_skill(dest, "commit", "Commit help")

    payload = pull_skills(
        catalog,
        coboose_root,
        "https://github.com/acme/agent-skills.git",
        names=["review"],
        run=run,
    )
    assert payload["needs_selection"] is False
    assert {item["name"] for item in payload["copied"]} == {"review"}
    dest = coboose_root / ".github" / "skills" / "review"
    assert dest.joinpath("notes.md").read_text(encoding="utf-8") == "prompt"
    marker = json.loads(dest.joinpath(".coboose-source.json").read_text(encoding="utf-8"))
    assert marker["source_kind"] == "remote"
    assert not (coboose_root / ".github" / "skills" / "commit").exists()


def test_pull_all_installs_every_skill(catalog, coboose_root: Path):
    def run(command, cwd):
        dest = Path(command[-1])
        dest.mkdir(parents=True)
        _write_skill(dest, "one", "One")
        _write_skill(dest, "two", "Two")

    payload = pull_skills(
        catalog,
        coboose_root,
        "git@github.com:acme/agent-skills.git",
        all_skills=True,
        https=True,
        run=run,
    )
    assert {item["name"] for item in payload["copied"]} == {"one", "two"}
    assert payload["url"].startswith("https://github.com/")


def test_cli_skills_list_and_lift(catalog, coboose_root: Path, capsys, monkeypatch):
    frontend = _sibling(coboose_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    monkeypatch.chdir(coboose_root)
    assert main(["--root", str(coboose_root), "skills", "list", "--all"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert any(item["name"] == "checkout" for item in listed["available"])

    assert main(["--root", str(coboose_root), "skills", "lift", "--all"]) == 0
    lifted = json.loads(capsys.readouterr().out)
    assert any(item["name"] == "checkout" for item in lifted["copied"])
    assert (coboose_root / ".github" / "skills" / "checkout" / "SKILL.md").is_file()


def test_init_lifts_sibling_skills(catalog, coboose_root: Path, monkeypatch):
    for name in (
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "JIRA_USERNAME",
        "JIRA_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    frontend = _sibling(coboose_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    payload = run_init(catalog, coboose_root)
    ids = {step["id"]: step for step in payload["steps"]}
    assert "skills" in ids
    assert ids["skills"]["optional"] is True
    assert any(item["name"] == "checkout" for item in payload["skills"]["copied"])
    assert "uv run coboose skills lift" in payload["next_commands"]


def test_sync_does_not_raise_when_dest_is_a_file(catalog, coboose_root: Path):
    dest = coboose_root / ".github" / "skills"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("not a directory", encoding="utf-8")
    frontend = _sibling(coboose_root, "frontend")
    _write_skill(frontend, "checkout", "Checkout")
    payload = sync_root_skills(catalog, coboose_root, all_repos=True)
    assert payload["ok"] is False
    assert payload.get("error")

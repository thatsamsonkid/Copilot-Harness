from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parents[1] / ".github" / "skills" / "prepare-jira" / "SKILL.md"
GITIGNORE = Path(__file__).resolve().parents[1] / ".gitignore"
KEEP = Path(__file__).resolve().parents[1] / "jira-tickets" / ".gitkeep"


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} must start with YAML frontmatter"
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def test_skill_name_matches_directory():
    meta, _ = _frontmatter_and_body(SKILL)
    assert meta["name"] == SKILL.parent.name


def test_skill_description_covers_triggers():
    meta, _ = _frontmatter_and_body(SKILL)
    description = meta["description"]
    assert 1 <= len(description) <= 1024
    lowered = description.lower()
    for token in ("jira-tickets/", "templates/jira-ticket.md", "prepare-jira", ".env"):
        assert token in lowered


def test_skill_is_a_draft_walkthrough_not_jira_write():
    _, body = _frontmatter_and_body(SKILL)
    lowered = body.lower()
    for token in (
        "jira-tickets/",
        "templates/jira-ticket.md",
        "gitignored",
        "acceptance criteria",
        "out of scope",
        "role",
        "copy-paste",
        "not** `goat prepare`",
        "read-only",
        "do not invent",
        "catalog/stack.yaml",
        "no secrets",
    ):
        assert token in lowered


def test_slash_skill_is_user_triggered_draft():
    meta, body = _frontmatter_and_body(SKILL)
    assert meta["name"] == "prepare-jira"
    assert meta.get("disable-model-invocation") is True
    assert "tools" not in meta
    assert "agent" not in meta
    lowered = body.lower()
    for token in (
        "templates/jira-ticket.md",
        "jira-tickets/",
        "goat prepare",
        "copy-paste",
    ):
        assert token in lowered


def test_jira_tickets_dir_is_gitignored_with_keep():
    text = GITIGNORE.read_text(encoding="utf-8")
    assert "jira-tickets/*.md" in text
    assert "!jira-tickets/.gitkeep" in text
    assert KEEP.exists()


def test_skill_resolves_typed_templates_before_fallback():
    _, body = _frontmatter_and_body(SKILL)
    assert "templates/jira/" in body
    assert "templates/jira/local/" in body
    lowered = body.lower()
    for stem in ("story", "bug", "spike"):
        assert stem in lowered
    order = (
        "templates/jira/local/<type>.md",
        "templates/jira/<type>.md",
        "templates/jira-ticket.md",
    )
    positions = [body.index(token) for token in order]
    assert positions == sorted(positions)
    assert positions[0] < positions[1] < positions[2]


def test_skill_records_type_and_warns_on_bad_acceptance_shape():
    _, body = _frontmatter_and_body(SKILL)
    assert "- Type:" in body
    assert "- Template:" in body
    assert "uv run goat jira get <KEY> --format json" in body
    assert "issue_type" in body
    lowered = body.lower()
    assert "warn" in lowered
    for heading in ("acceptance criteria", "definition of done", "done when"):
        assert heading in lowered
    assert "never list issue types from jira" in lowered
    assert "**one** batched" in lowered


def test_arbitrary_type_names_stay_inside_the_template_dir():
    _, body = _frontmatter_and_body(SKILL)
    assert "lowercase `[a-z0-9-]` only" in body
    assert "Spaces become hyphens" in body
    assert "Drop everything else" in body
    assert "Reject an empty result and fall back" in body
    assert "templates/jira-ticket.md" in body
    assert "`/` or `..`" in body
    assert "templates/jira/local/" in body


def test_local_jira_templates_are_gitignored_except_keep():
    root = GITIGNORE.parent
    keep = root / "templates" / "jira" / "local" / ".gitkeep"
    assert keep.is_file()
    text = GITIGNORE.read_text(encoding="utf-8")
    assert "templates/jira/local/*" in text
    assert "!templates/jira/local/.gitkeep" in text

    def check_ignore(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "check-ignore", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

    # --no-index checks the rule itself. A tracked .gitkeep is otherwise
    # skipped, so check-ignore would not show the negation after commit.
    ignored = check_ignore("-v", "--no-index", "templates/jira/local/example.md")
    assert ignored.returncode == 0, ignored.stderr
    assert "templates/jira/local/*" in ignored.stdout
    assert "!templates/jira/local/*" not in ignored.stdout
    assert "templates/jira/local/example.md" in ignored.stdout

    # -v prints the last matching pattern and exits 0 even when that pattern
    # is a negation. -q exits 1 when the path is not ignored.
    kept = check_ignore("-v", "--no-index", "templates/jira/local/.gitkeep")
    assert "!templates/jira/local/.gitkeep" in kept.stdout
    quiet = check_ignore("-q", "--no-index", "templates/jira/local/.gitkeep")
    assert quiet.returncode == 1, quiet.stdout

    team = check_ignore("-q", "--no-index", "templates/jira/story.md")
    assert team.returncode == 1, team.stdout

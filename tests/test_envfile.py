from __future__ import annotations

from pathlib import Path

from harness.envfile import env_file_keys, load_env_file, upsert_env_file


def test_upsert_preserves_comments_and_other_keys(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text(
        "# keep me\nJIRA_BASE_URL=https://old.example\nUNRELATED=1\n",
        encoding="utf-8",
    )
    written = upsert_env_file(
        path,
        {"JIRA_BASE_URL": "https://new.example", "JIRA_EMAIL": "a@b.com"},
    )
    text = path.read_text(encoding="utf-8")
    assert written == ["JIRA_BASE_URL", "JIRA_EMAIL"]
    assert text.startswith("# keep me\n")
    assert "JIRA_BASE_URL=https://new.example" in text
    assert "UNRELATED=1" in text
    assert env_file_keys(path)["JIRA_EMAIL"] is True


def test_empty_assignment_is_not_present(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text("JIRA_API_TOKEN=\n", encoding="utf-8")
    assert env_file_keys(path)["JIRA_API_TOKEN"] is False


def test_load_env_file_supports_export_and_quotes(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text(
        "export DB_PASSWORD=s3cret\nAPI_TOKEN=\"tok 'x'\"\n# skip\nNOPE\n",
        encoding="utf-8",
    )
    values = load_env_file(path)
    assert values["DB_PASSWORD"] == "s3cret"
    assert values["API_TOKEN"] == "tok 'x'"
    assert "NOPE" not in values

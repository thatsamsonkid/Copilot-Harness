from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from goat import GoatError
from goat.envfile import (
    blank_env_keys,
    env_file_keys,
    format_env_value,
    load_env_file,
    upsert_env_file,
)


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


def test_upsert_rejects_newline_smuggling(tmp_path: Path):
    path = tmp_path / ".env"
    with pytest.raises(GoatError, match="control characters"):
        upsert_env_file(path, {"FOO": "x\nJIRA_BASE_URL=https://evil"})
    assert not path.exists()


def test_value_with_specials_round_trips(tmp_path: Path):
    path = tmp_path / ".env"
    upsert_env_file(path, {"MSG": 'a "quote" # and hash'})
    # The raw file must not contain a bare, unquoted value.
    assert 'MSG="a \\"quote\\" # and hash"' in path.read_text(encoding="utf-8")
    assert load_env_file(path)["MSG"] == 'a "quote" # and hash'


def test_upsert_dedupes_stale_duplicate_keys(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text("FOO=one\nBAR=keep\nFOO=two\n", encoding="utf-8")
    upsert_env_file(path, {"FOO": "new"})
    text = path.read_text(encoding="utf-8")
    assert text.count("FOO=") == 1
    assert "FOO=new" in text
    assert load_env_file(path)["FOO"] == "new"
    assert "BAR=keep" in text


def test_upsert_sets_owner_only_permissions(tmp_path: Path):
    path = tmp_path / ".env"
    upsert_env_file(path, {"FOO": "bar"})
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if os.name != "nt":
        assert mode == 0o600


def test_blank_env_keys_handles_aliases_and_export(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text(
        "export JIRA_TOKEN=secret\nJIRA_API_TOKEN=other\nKEEP=1\n",
        encoding="utf-8",
    )
    blanked = blank_env_keys(path, ("JIRA_API_TOKEN", "JIRA_TOKEN"))
    assert set(blanked) == {"JIRA_API_TOKEN", "JIRA_TOKEN"}
    text = path.read_text(encoding="utf-8")
    assert "secret" not in text
    assert "other" not in text
    assert "KEEP=1" in text
    keys = env_file_keys(path)
    assert keys["JIRA_TOKEN"] is False
    assert keys["JIRA_API_TOKEN"] is False


def test_format_env_value_leaves_plain_values_unquoted():
    assert format_env_value("https://acme.atlassian.net") == "https://acme.atlassian.net"
    assert format_env_value("you@company.com") == "you@company.com"

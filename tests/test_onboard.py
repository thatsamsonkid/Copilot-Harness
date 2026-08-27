from __future__ import annotations

import json
from pathlib import Path

from harness.cli import main
from harness.onboard import run_init


def _clear_jira_env(monkeypatch) -> None:
    for name in (
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_USERNAME",
        "JIRA_API_TOKEN",
        "JIRA_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def test_init_lists_missing_jira_keys_without_reading_secrets(
    harness_root: Path, catalog, monkeypatch, capsys
):
    _clear_jira_env(monkeypatch)
    example = harness_root / ".env.example"
    example.write_text(
        "JIRA_BASE_URL=\nJIRA_EMAIL=\nJIRA_API_TOKEN=\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(harness_root)
    assert main(["--root", str(harness_root), "init"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["created_env"] is True
    assert payload["ready"] is False
    assert payload["token_docs"] == "docs/jira-api-token.md"
    ids = {step["id"]: step for step in payload["steps"]}
    assert ids["jira_api_token"]["ok"] is False
    assert "docs/jira-api-token.md" in ids["jira_api_token"]["action"]
    dumped = json.dumps(payload)
    assert "ATLASSIAN-SECRET" not in dumped


def test_interactive_init_writes_env_and_omits_token_from_json(
    harness_root: Path, catalog, monkeypatch
):
    _clear_jira_env(monkeypatch)
    answers = iter(
        [
            "https://acme.atlassian.net",
            "ada@acme.test",
        ]
    )
    payload = run_init(
        catalog,
        harness_root,
        interactive=True,
        prompt_fn=lambda _msg: next(answers),
        secret_fn=lambda _msg: "ATLASSIAN-SECRET",
    )
    env_text = (harness_root / ".env").read_text(encoding="utf-8")
    assert "JIRA_EMAIL=ada@acme.test" in env_text
    assert "JIRA_API_TOKEN=ATLASSIAN-SECRET" in env_text
    assert "ATLASSIAN-SECRET" not in json.dumps(payload)
    assert "ATLASSIAN-SECRET" not in payload["wrote_keys"]
    assert set(payload["wrote_keys"]) == {
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
    }


def test_init_treats_env_file_values_as_present(
    harness_root: Path, catalog, monkeypatch
):
    _clear_jira_env(monkeypatch)
    (harness_root / ".env").write_text(
        "JIRA_BASE_URL=https://acme.atlassian.net\n"
        "JIRA_EMAIL=ada@acme.test\n"
        "JIRA_API_TOKEN=hidden\n",
        encoding="utf-8",
    )
    payload = run_init(catalog, harness_root)
    ids = {step["id"]: step for step in payload["steps"]}
    assert ids["jira_base_url"]["ok"] is True
    assert ids["jira_email"]["ok"] is True
    assert ids["jira_api_token"]["ok"] is True
    assert "hidden" not in json.dumps(payload)

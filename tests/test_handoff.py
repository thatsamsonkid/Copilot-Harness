from __future__ import annotations

import json
from pathlib import Path

from coboose.cli import main
from coboose.handoff import latest_handoff, write_handoff


def test_handoff_write_and_latest(coboose_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(coboose_root)
    assert (
        main(
            [
                "--root",
                str(coboose_root),
                "handoff",
                "write",
                "--issue",
                "WEB-42",
                "--note",
                "Stopped after planning checkout.",
            ]
        )
        == 0
    )
    written = json.loads(capsys.readouterr().out)
    path = Path(written["file"])
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "WEB-42" in text
    assert "Stopped after planning checkout." in text
    assert "ATLASSIAN" not in text

    assert main(["--root", str(coboose_root), "handoff", "latest"]) == 0
    latest = json.loads(capsys.readouterr().out)
    assert latest["issue"] == "WEB-42"
    assert "Stopped after planning checkout." in latest["body"]


def test_write_handoff_omits_secrets(coboose_root: Path):
    payload = write_handoff(
        coboose_root,
        issue="API-1",
        note="Need to rotate nothing",
        status={"repos": [], "dirty_repos": [], "behind_repos": []},
    )
    body = Path(payload["file"]).read_text(encoding="utf-8")
    assert "JIRA_API_TOKEN" not in body
    latest = latest_handoff(coboose_root)
    assert latest["issue"] == "API-1"

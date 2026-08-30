from __future__ import annotations

from pathlib import Path

from coboose.jira_client import JiraClient
from coboose.prepare import prepare_issue
from tests.helpers import FakeHttp, json_response as _json


def _issue_payload() -> dict:
    return {
        "id": "100",
        "key": "WEB-42",
        "self": "https://acme.atlassian.net/rest/api/3/issue/100",
        "names": {},
        "fields": {
            "summary": "Fix checkout button",
            "description": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "The button is wrong"}],
                    }
                ],
            },
            "status": {"name": "To Do"},
            "issuetype": {"name": "Bug"},
            "priority": {"name": "High"},
            "project": {"key": "WEB", "name": "Web"},
            "assignee": {"displayName": "Ada"},
            "reporter": {"displayName": "Al"},
            "labels": ["ui"],
            "components": [{"name": "Frontend"}],
            "fixVersions": [],
            "issuelinks": [],
        },
    }


def test_prepare_recommends_frontend_and_lists_missing(catalog, coboose_root: Path):
    http = FakeHttp(
        {
            ("GET", "https://acme.atlassian.net/rest/api/3/issue/WEB-42"): _json(
                _issue_payload()
            ),
            ("GET", "https://acme.atlassian.net/rest/api/3/issue/WEB-42/comment"): _json(
                {
                    "comments": [
                        {
                            "id": "1",
                            "author": {"displayName": "Ada"},
                            "created": "2026-01-01T00:00:00.000+0000",
                            "updated": "2026-01-01T00:00:00.000+0000",
                            "body": {
                                "type": "doc",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {"type": "text", "text": "Please ship"}
                                        ],
                                    }
                                ],
                            },
                        }
                    ]
                }
            ),
        }
    )
    client = JiraClient("https://acme.atlassian.net", "a@b.com", "token", http=http)
    payload = prepare_issue(catalog, coboose_root, client, "WEB-42")
    assert payload["issue"]["key"] == "WEB-42"
    assert payload["issue"]["comments"][0]["body"] == "Please ship"
    assert payload["routing"]["workspace_id"] == "frontend"
    assert {repo["id"] for repo in payload["routing"]["missing_repos"]} == {
        "frontend",
        "backend",
    }
    assert payload["routing"]["open_command"].endswith(
        "workspaces/frontend.code-workspace"
    )
    assert (coboose_root / "workspaces" / "frontend.code-workspace").exists()
    frontend = next(repo for repo in payload["routing"]["repos"] if repo["id"] == "frontend")
    assert frontend["graphify"]["present"] is False
    assert frontend["instructions"] == []
    assert frontend["knowledge"]["files"] == []
    assert "Read the issue summary" in payload["next_steps"][0]
    assert payload["routing"]["suggested_branch"] == "WEB-42"
    assert any(item["source"] == "coboose" for item in payload["done_when"])
    assert any("WEB-42" in step for step in payload["next_steps"])
    assert "skills" in payload


def test_prepare_lifts_sibling_skills(catalog, coboose_root: Path):
    frontend = coboose_root.parent / "frontend"
    skill = frontend / ".github" / "skills" / "checkout"
    skill.mkdir(parents=True)
    skill.joinpath("SKILL.md").write_text(
        "---\nname: checkout\ndescription: Checkout flow\n---\n\n# checkout\n",
        encoding="utf-8",
    )
    http = FakeHttp(
        {
            ("GET", "https://acme.atlassian.net/rest/api/3/issue/WEB-42"): _json(
                _issue_payload()
            ),
            ("GET", "https://acme.atlassian.net/rest/api/3/issue/WEB-42/comment"): _json(
                {"comments": []}
            ),
        }
    )
    client = JiraClient("https://acme.atlassian.net", "a@b.com", "token", http=http)
    payload = prepare_issue(catalog, coboose_root, client, "WEB-42")
    assert any(item["name"] == "checkout" for item in payload["skills"]["copied"])
    assert (coboose_root / ".github" / "skills" / "checkout" / "SKILL.md").is_file()
    assert any("skills" in step.lower() for step in payload["next_steps"])

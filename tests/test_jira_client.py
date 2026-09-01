from __future__ import annotations

import json

import pytest

from goat import GoatError
from goat.http import HttpResponse
from goat.jira_client import JiraClient, parse_issue_key
from goat.jira_fields import DEFAULT_OUTPUT_FIELDS, JiraSettings


class FakeHttp:
    def __init__(self, routes: dict[tuple[str, str], HttpResponse]):
        self.routes = routes
        self.calls: list[tuple[str, str]] = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        key = (method.upper(), url.split("?", 1)[0])
        if key not in self.routes:
            raise AssertionError(f"Unexpected request {key}")
        return self.routes[key]


def _json(payload, status=200) -> HttpResponse:
    return HttpResponse(status=status, body=json.dumps(payload), headers={})


def test_parse_issue_key_from_url_and_plain():
    assert parse_issue_key("WEB-42") == "WEB-42"
    assert parse_issue_key("https://acme.atlassian.net/browse/WEB-42") == "WEB-42"
    with pytest.raises(GoatError):
        parse_issue_key("not-a-ticket")


def test_get_issue_normalizes_adf_and_links():
    issue = {
        "id": "100",
        "key": "WEB-42",
        "self": "https://acme.atlassian.net/rest/api/3/issue/100",
        "names": {"customfield_10016": "Story Points"},
        "fields": {
            "summary": "Fix button",
            "description": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Broken css"}],
                    }
                ],
            },
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Bug"},
            "priority": {"name": "High"},
            "project": {"key": "WEB", "name": "Web"},
            "assignee": {"displayName": "Ada"},
            "reporter": {"displayName": "Al"},
            "labels": ["ui"],
            "components": [{"name": "Frontend"}],
            "fixVersions": [{"name": "1.2"}],
            "parent": {
                "key": "WEB-1",
                "fields": {
                    "summary": "Checkout",
                    "status": {"name": "To Do"},
                    "issuetype": {"name": "Epic"},
                },
            },
            "issuelinks": [
                {
                    "type": {"name": "Blocks", "outward": "blocks"},
                    "outwardIssue": {
                        "key": "API-9",
                        "fields": {
                            "summary": "Price API",
                            "status": {"name": "Done"},
                        },
                    },
                }
            ],
            "customfield_10016": 3,
        },
    }
    http = FakeHttp(
        {("GET", "https://acme.atlassian.net/rest/api/3/issue/WEB-42"): _json(issue)}
    )
    client = JiraClient("https://acme.atlassian.net", "a@b.com", "token", http=http)
    settings = JiraSettings(
        fields=[*DEFAULT_OUTPUT_FIELDS, "story_points"],
        extra_fields=["customfield_10016"],
        field_aliases={"customfield_10016": "story_points"},
        include_comments=False,
    )
    payload = client.get_issue(
        "https://acme.atlassian.net/browse/WEB-42", settings=settings
    )
    assert payload["key"] == "WEB-42"
    assert payload["url"] == "https://acme.atlassian.net/browse/WEB-42"
    assert payload["description"] == "Broken css"
    assert payload["components"] == ["Frontend"]
    assert payload["parent"]["key"] == "WEB-1"
    assert payload["issuelinks"][0]["key"] == "API-9"
    assert payload["story_points"] == 3
    assert payload["parent"] == {
        "key": "WEB-1",
        "summary": "Checkout",
        "status": "To Do",
    }
    assert payload["issuelinks"][0] == {
        "type": "Blocks",
        "direction": "blocks",
        "key": "API-9",
        "summary": "Price API",
    }
    assert "reporter" not in payload
    assert "id" not in payload
    assert "custom" not in payload
    assert "created" not in payload
    assert "watchers" not in payload


def test_search_falls_back_to_legacy_endpoint():
    search_result = {
        "issues": [
            {
                "key": "API-1",
                "fields": {
                    "summary": "Add endpoint",
                    "status": {"name": "To Do"},
                    "issuetype": {"name": "Story"},
                    "priority": {"name": "Low"},
                    "assignee": None,
                    "project": {"key": "API"},
                    "labels": [],
                    "components": [],
                },
            }
        ]
    }
    http = FakeHttp(
        {
            ("POST", "https://acme.atlassian.net/rest/api/3/search/jql"): HttpResponse(
                404, "", {}
            ),
            ("GET", "https://acme.atlassian.net/rest/api/3/search"): _json(search_result),
        }
    )
    client = JiraClient("https://acme.atlassian.net", "a@b.com", "token", http=http)
    issues = client.search("project = API")
    assert issues[0]["key"] == "API-1"
    assert issues[0]["summary"] == "Add endpoint"
    assert "labels" not in issues[0]
    assert "components" not in issues[0]


def test_get_comments_uses_configured_shape():
    http = FakeHttp(
        {
            ("GET", "https://acme.atlassian.net/rest/api/3/issue/WEB-42/comment"): _json(
                {
                    "comments": [
                        {
                            "id": "9",
                            "author": {"displayName": "Ada"},
                            "created": "2026-01-01T00:00:00.000+0000",
                            "updated": "2026-01-02T00:00:00.000+0000",
                            "body": {
                                "type": "doc",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "Ship it"}],
                                    }
                                ],
                            },
                        }
                    ]
                }
            )
        }
    )
    client = JiraClient("https://acme.atlassian.net", "a@b.com", "token", http=http)
    comments = client.get_comments("WEB-42")
    assert comments == [
        {"author": "Ada", "created": "2026-01-01T00:00:00.000+0000", "body": "Ship it"}
    ]


def test_get_comments_requests_newest_first_and_returns_chronological():
    def _comment(comment_id: str, author: str, created: str, text: str) -> dict:
        return {
            "id": comment_id,
            "author": {"displayName": author},
            "created": created,
            "body": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": text}],
                    }
                ],
            },
        }

    http = FakeHttp(
        {
            ("GET", "https://acme.atlassian.net/rest/api/3/issue/WEB-42/comment"): _json(
                {
                    # The API returns newest-first when orderBy=-created.
                    "comments": [
                        _comment("2", "Bea", "2026-02-01T00:00:00.000+0000", "second"),
                        _comment("1", "Ada", "2026-01-01T00:00:00.000+0000", "first"),
                    ]
                }
            )
        }
    )
    client = JiraClient("https://acme.atlassian.net", "a@b.com", "token", http=http)
    comments = client.get_comments("WEB-42", max_results=2)
    assert [item["body"] for item in comments] == ["first", "second"]
    assert any("orderBy=-created" in url for _, url in http.calls)


def test_yaml_toggle_exposes_known_optional_field():
    issue = {
        "id": "100",
        "key": "WEB-42",
        "self": "https://acme.atlassian.net/rest/api/3/issue/100",
        "fields": {
            "summary": "Fix button",
            "created": "2026-01-01T00:00:00.000+0000",
            "status": {"name": "To Do"},
            "issuetype": {"name": "Bug"},
            "project": {"key": "WEB", "name": "Web"},
        },
    }
    http = FakeHttp(
        {("GET", "https://acme.atlassian.net/rest/api/3/issue/WEB-42"): _json(issue)}
    )
    client = JiraClient("https://acme.atlassian.net", "a@b.com", "token", http=http)
    settings = JiraSettings(
        fields=["key", "summary", "created"],
        include_comments=False,
    )
    payload = client.get_issue("WEB-42", settings=settings)
    assert payload == {
        "key": "WEB-42",
        "summary": "Fix button",
        "created": "2026-01-01T00:00:00.000+0000",
    }
    assert "fields=" in http.calls[0][1]
    assert "created" in http.calls[0][1]


def test_auth_error_mentions_keychain_or_env():
    http = FakeHttp(
        {
            ("GET", "https://acme.atlassian.net/rest/api/3/myself"): HttpResponse(
                401, "{}", {}
            )
        }
    )
    client = JiraClient("https://acme.atlassian.net", "a@b.com", "bad", http=http)
    with pytest.raises(GoatError, match="authentication") as exc:
        client.myself()
    assert "keychain" in exc.value.message.lower()
    assert ".env" in exc.value.message

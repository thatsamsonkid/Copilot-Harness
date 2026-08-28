from __future__ import annotations

import json

import pytest

from coboose import CobooseError
from coboose.http import HttpResponse
from coboose.jira_client import JiraClient, parse_issue_key
from coboose.jira_fields import DEFAULT_OUTPUT_FIELDS, JiraSettings


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
    with pytest.raises(CobooseError):
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
    assert "reporter" not in payload
    assert "id" not in payload
    assert "custom" not in payload


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


def test_auth_error_mentions_keychain_or_env():
    http = FakeHttp(
        {
            ("GET", "https://acme.atlassian.net/rest/api/3/myself"): HttpResponse(
                401, "{}", {}
            )
        }
    )
    client = JiraClient("https://acme.atlassian.net", "a@b.com", "bad", http=http)
    with pytest.raises(CobooseError, match="authentication") as exc:
        client.myself()
    assert "keychain" in exc.value.message.lower()
    assert ".env" in exc.value.message

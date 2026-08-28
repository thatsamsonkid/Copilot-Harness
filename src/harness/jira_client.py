from __future__ import annotations

import base64
import os
import re
from typing import Any
from urllib.parse import quote

from harness import HarnessError
from harness.adf import adf_to_markdown
from harness.http import HttpClient, HttpResponse
from harness.jira_fields import JiraSettings, project_issue
from harness.keychain import resolve_token

ISSUE_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def parse_issue_key(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise HarnessError("Issue key is required")
    if re.fullmatch(r"[A-Z][A-Z0-9]+-\d+", text):
        return text
    match = ISSUE_KEY_RE.search(text)
    if match:
        return match.group(1)
    raise HarnessError(f"Could not parse a Jira issue key from: {value}")


def jira_settings_from_env() -> tuple[str, str, str]:
    base_url = (os.environ.get("JIRA_BASE_URL") or "").rstrip("/")
    email = os.environ.get("JIRA_EMAIL") or os.environ.get("JIRA_USERNAME") or ""
    token, _source = resolve_token()
    missing = [
        name
        for name, value in (
            ("JIRA_BASE_URL", base_url),
            ("JIRA_EMAIL", email),
            ("JIRA_API_TOKEN", token),
        )
        if not value
    ]
    if missing:
        raise HarnessError(_missing_settings_message(missing))
    return base_url, email, token


def _missing_settings_message(missing: list[str]) -> str:
    parts = ["Missing Jira settings: " + ", ".join(missing) + "."]
    if "JIRA_BASE_URL" in missing or "JIRA_EMAIL" in missing:
        parts.append("Set the site URL and email in .env.")
    if "JIRA_API_TOKEN" in missing:
        parts.append(
            "Store the API token with `uv run harness jira login` "
            "(macOS Keychain or Windows Credential Manager), or set "
            "JIRA_API_TOKEN in .env as a fallback."
        )
    else:
        parts.append("Copy .env.example to .env or export the variables.")
    parts.append("See docs/jira-api-token.md. Do not paste the token into chat.")
    return " ".join(parts)


class JiraClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        token: str,
        http: HttpClient | None = None,
        timeout: float = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self._http = http or HttpClient()
        self._timeout = timeout
        raw = f"{email}:{token}".encode("utf-8")
        self._auth = "Basic " + base64.b64encode(raw).decode("ascii")

    def myself(self) -> dict[str, Any]:
        payload = self._json("GET", "/rest/api/3/myself")
        return {
            "authenticated": True,
            "display_name": payload.get("displayName"),
        }

    def get_issue(
        self,
        key: str,
        settings: JiraSettings | None = None,
        extra_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        settings = settings or JiraSettings(extra_fields=extra_fields or [])
        key = parse_issue_key(key)
        params = {"fields": ",".join(settings.request_field_ids())}
        if settings.extra_fields:
            params["expand"] = "names"
        payload = self._json(
            "GET",
            f"/rest/api/3/issue/{quote(key)}",
            params=params,
        )
        return project_issue(
            normalize_issue(payload, settings=settings),
            settings,
        )

    def get_comments(self, key: str, max_results: int = 50) -> list[dict[str, Any]]:
        key = parse_issue_key(key)
        payload = self._json(
            "GET",
            f"/rest/api/3/issue/{quote(key)}/comment",
            params={"maxResults": str(max_results), "orderBy": "created"},
        )
        return [normalize_comment(comment) for comment in payload.get("comments") or []]

    def search(self, jql: str, max_results: int = 25) -> list[dict[str, Any]]:
        if not jql.strip():
            raise HarnessError("JQL is required")
        fields = [
            "summary",
            "status",
            "issuetype",
            "priority",
            "assignee",
            "labels",
            "components",
            "project",
        ]
        response = self._request(
            "POST",
            "/rest/api/3/search/jql",
            json_body={"jql": jql, "maxResults": max_results, "fields": fields},
        )
        if response.status == 404:
            response = self._request(
                "GET",
                "/rest/api/3/search",
                params={
                    "jql": jql,
                    "maxResults": str(max_results),
                    "fields": ",".join(fields),
                },
            )
        payload = self._decode(response, "GET" if response.status != 200 else "POST")
        issues = payload.get("issues") or payload.get("values") or []
        return [normalize_issue_summary(issue) for issue in issues]

    def get_context(
        self,
        key: str,
        settings: JiraSettings | None = None,
        extra_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        settings = settings or JiraSettings(extra_fields=extra_fields or [])
        issue = self.get_issue(key, settings=settings)
        if settings.wants("comments"):
            issue["comments"] = self.get_comments(
                issue["key"], max_results=settings.max_comments
            )
        return issue

    def _json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: Any = None,
    ) -> Any:
        return self._decode(self._request(method, path, params=params, json_body=json_body), method)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: Any = None,
    ) -> HttpResponse:
        url = self.base_url + path
        if params:
            query = "&".join(
                f"{quote(key)}={quote(value)}" for key, value in params.items()
            )
            url = f"{url}?{query}"
        return self._http.request(
            method,
            url,
            headers={
                "Authorization": self._auth,
                "Accept": "application/json",
            },
            json_body=json_body,
            timeout=self._timeout,
        )

    def _decode(self, response: HttpResponse, method: str) -> Any:
        if response.status == 401:
            raise HarnessError(
                "Jira authentication failed. Check the token in the OS keychain "
                "(`harness jira login`) or .env; do not print them."
            )
        if response.status == 403:
            raise HarnessError("Jira denied access to this resource.")
        if response.status == 404:
            raise HarnessError("Jira resource not found.")
        if response.status >= 400:
            detail = _error_message(response)
            raise HarnessError(f"Jira API {method} failed ({response.status}): {detail}")
        try:
            return response.json()
        except ValueError as exc:
            raise HarnessError("Jira returned a non-JSON response") from exc


def _error_message(response: HttpResponse) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.body[:300] or "no body"
    if isinstance(payload, dict):
        if payload.get("errorMessages"):
            return "; ".join(str(item) for item in payload["errorMessages"])
        if payload.get("message"):
            return str(payload["message"])
    return response.body[:300] or "no body"


def _user(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    return value.get("displayName") or value.get("emailAddress") or value.get("accountId")


def _status(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("name")
    return None


def normalize_issue_summary(payload: dict[str, Any]) -> dict[str, Any]:
    fields = payload.get("fields") or {}
    key = payload.get("key")
    return {
        "key": key,
        "summary": fields.get("summary"),
        "status": _status(fields.get("status")),
        "issue_type": (fields.get("issuetype") or {}).get("name"),
        "priority": (fields.get("priority") or {}).get("name"),
        "assignee": _user(fields.get("assignee")),
        "project": (fields.get("project") or {}).get("key"),
        "labels": list(fields.get("labels") or []),
        "components": [
            item.get("name")
            for item in fields.get("components") or []
            if isinstance(item, dict)
        ],
    }


def normalize_comment(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": payload.get("id"),
        "author": _user(payload.get("author")),
        "created": payload.get("created"),
        "updated": payload.get("updated"),
        "body": adf_to_markdown(payload.get("body")),
    }


def normalize_issue(
    payload: dict[str, Any],
    extra_fields: list[str] | None = None,
    settings: JiraSettings | None = None,
) -> dict[str, Any]:
    fields = payload.get("fields") or {}
    names = payload.get("names") or {}
    key = payload.get("key")
    project = fields.get("project") or {}
    parent = fields.get("parent") or {}
    parent_fields = parent.get("fields") or {}
    issue: dict[str, Any] = {
        "key": key,
        "id": payload.get("id"),
        "url": f"{_browse_base(payload, fields)}/browse/{key}" if key else None,
        "summary": fields.get("summary"),
        "description": adf_to_markdown(fields.get("description")),
        "status": _status(fields.get("status")),
        "issue_type": (fields.get("issuetype") or {}).get("name"),
        "priority": (fields.get("priority") or {}).get("name"),
        "project": {
            "key": project.get("key"),
            "name": project.get("name"),
        },
        "assignee": _user(fields.get("assignee")),
        "reporter": _user(fields.get("reporter")),
        "labels": list(fields.get("labels") or []),
        "components": [
            item.get("name")
            for item in fields.get("components") or []
            if isinstance(item, dict)
        ],
        "fix_versions": [
            item.get("name")
            for item in fields.get("fixVersions") or []
            if isinstance(item, dict)
        ],
        "parent": None,
        "issuelinks": _normalize_links(fields.get("issuelinks") or []),
        "custom": {},
    }
    if parent.get("key"):
        issue["parent"] = {
            "key": parent.get("key"),
            "summary": parent_fields.get("summary"),
            "status": _status(parent_fields.get("status")),
            "issue_type": (parent_fields.get("issuetype") or {}).get("name"),
        }
    extract_ids = list(extra_fields or [])
    aliases: dict[str, str] = {}
    if settings is not None:
        extract_ids = list(settings.extra_fields)
        aliases = settings.field_aliases
    issue["custom"] = _extract_custom_fields(fields, names, extract_ids, aliases)
    return issue


def _browse_base(payload: dict[str, Any], fields: dict[str, Any]) -> str:
    self_url = payload.get("self") or ""
    match = re.match(r"(https?://[^/]+)", self_url)
    if match:
        return match.group(1)
    return ""


def _normalize_links(links: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        link_type = (link.get("type") or {}).get("name")
        if "outwardIssue" in link:
            issue = link["outwardIssue"]
            direction = (link.get("type") or {}).get("outward") or "outward"
        elif "inwardIssue" in link:
            issue = link["inwardIssue"]
            direction = (link.get("type") or {}).get("inward") or "inward"
        else:
            continue
        issue_fields = issue.get("fields") or {}
        result.append(
            {
                "type": link_type,
                "direction": direction,
                "key": issue.get("key"),
                "summary": issue_fields.get("summary"),
                "status": _status(issue_fields.get("status")),
            }
        )
    return result


def _extract_custom_fields(
    fields: dict[str, Any],
    names: dict[str, Any],
    extra_fields: list[str],
    aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    aliases = aliases or {}
    wanted = set(extra_fields)
    custom: dict[str, Any] = {}
    for field_id in wanted:
        value = fields.get(field_id)
        if value in (None, "", [], {}):
            continue
        name = aliases.get(field_id) or names.get(field_id) or field_id
        custom[str(name)] = _simplify_custom_value(value)
        custom[field_id] = custom[str(name)]
    return custom


def _simplify_custom_value(value: Any) -> Any:
    if isinstance(value, dict):
        if "type" in value and (value.get("content") is not None or value.get("type") == "doc"):
            return adf_to_markdown(value)
        for key in ("value", "name", "displayName", "key"):
            if key in value and not isinstance(value[key], (dict, list)):
                return value[key]
        return {k: _simplify_custom_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_simplify_custom_value(item) for item in value]
    return value

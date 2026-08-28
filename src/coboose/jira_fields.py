from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_OUTPUT_FIELDS = [
    "key",
    "url",
    "summary",
    "description",
    "status",
    "issue_type",
    "priority",
    "project",
    "assignee",
    "labels",
    "components",
    "parent",
    "issuelinks",
    "comments",
]

# Output name -> Jira Cloud field id for the issue fetch.
JIRA_API_FIELDS = {
    "summary": "summary",
    "description": "description",
    "status": "status",
    "issue_type": "issuetype",
    "priority": "priority",
    "project": "project",
    "assignee": "assignee",
    "reporter": "reporter",
    "labels": "labels",
    "components": "components",
    "fix_versions": "fixVersions",
    "parent": "parent",
    "issuelinks": "issuelinks",
}


@dataclass(frozen=True)
class JiraSettings:
    fields: list[str] = field(default_factory=lambda: list(DEFAULT_OUTPUT_FIELDS))
    extra_fields: list[str] = field(default_factory=list)
    field_aliases: dict[str, str] = field(default_factory=dict)
    include_comments: bool = True
    max_comments: int = 15

    def output_fields(self) -> list[str]:
        names = list(self.fields or DEFAULT_OUTPUT_FIELDS)
        if "key" not in names:
            names.insert(0, "key")
        if not self.include_comments:
            names = [name for name in names if name != "comments"]
        return names

    def wants(self, name: str) -> bool:
        return name in set(self.output_fields())

    def request_field_ids(self) -> list[str]:
        ids: list[str] = []
        for name in self.output_fields():
            field_id = JIRA_API_FIELDS.get(name)
            if field_id and field_id not in ids:
                ids.append(field_id)
        for field_id in self.extra_fields:
            if field_id not in ids:
                ids.append(field_id)
        return ids

    def schema(self) -> dict[str, Any]:
        return {
            "fields": self.output_fields(),
            "extra_fields": self.extra_fields,
            "field_aliases": self.field_aliases,
            "include_comments": self.include_comments and self.wants("comments"),
            "max_comments": self.max_comments,
        }


def project_issue(issue: dict[str, Any], settings: JiraSettings) -> dict[str, Any]:
    """Keep only configured output fields. Never pass through a raw Jira payload."""
    allowed = set(settings.output_fields())
    custom = dict(issue.get("custom") or {})
    projected: dict[str, Any] = {}
    for name in settings.output_fields():
        if name in {"custom", "comments"}:
            continue
        if name in issue:
            projected[name] = issue[name]
    if settings.wants("comments"):
        projected["comments"] = issue.get("comments") or []
    for field_id, alias in settings.field_aliases.items():
        value = custom.get(alias) or custom.get(field_id)
        if value is not None and (alias in allowed or field_id in allowed):
            projected[alias] = value
    if settings.wants("custom") and custom:
        projected["custom"] = {
            key: value
            for key, value in custom.items()
            if key not in projected
        }
    return projected

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from goat.projection import ProjectionSpec, project

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

DEFAULT_SEARCH_FIELDS = [
    "key",
    "summary",
    "status",
    "issue_type",
    "priority",
    "assignee",
    "project",
    "labels",
    "components",
]

# Nested allowlists for objects the CLI already normalizes.
# Override one key under jira.shapes in catalog/stack.yaml without code changes.
DEFAULT_SHAPES: dict[str, tuple[str, ...]] = {
    "project": ("key", "name"),
    "parent": ("key", "summary", "status"),
    "issuelinks": ("type", "direction", "key", "summary"),
    "comments": ("author", "created", "body"),
}


@dataclass(frozen=True)
class OutputField:
    """Known Copilot-facing field. Add a row here to make a Jira field YAML-toggleable."""

    name: str
    api_id: str | None = None
    kind: str = "raw"  # raw, adf, user, status, name, list_name


# Simple fields extracted from Jira `fields`. Compound ones (project, parent,
# issuelinks, url) stay in the client. Custom fields use extra_fields + aliases.
KNOWN_OUTPUT_FIELDS = (
    OutputField("summary", "summary"),
    OutputField("description", "description", "adf"),
    OutputField("status", "status", "status"),
    OutputField("issue_type", "issuetype", "name"),
    OutputField("priority", "priority", "name"),
    OutputField("assignee", "assignee", "user"),
    OutputField("reporter", "reporter", "user"),
    OutputField("labels", "labels"),
    OutputField("components", "components", "list_name"),
    OutputField("fix_versions", "fixVersions", "list_name"),
    OutputField("created", "created"),
    OutputField("updated", "updated"),
    OutputField("resolution", "resolution", "name"),
)

# Output name -> Jira Cloud field id for the issue fetch.
JIRA_API_FIELDS = {
    **{item.name: item.api_id for item in KNOWN_OUTPUT_FIELDS if item.api_id},
    "project": "project",
    "parent": "parent",
    "issuelinks": "issuelinks",
}


def _copy_shapes(source: dict[str, tuple[str, ...] | list[str]] | None = None) -> dict[str, list[str]]:
    items = source if source is not None else DEFAULT_SHAPES
    return {key: list(value) for key, value in items.items()}


@dataclass(frozen=True)
class JiraSettings:
    fields: list[str] = field(default_factory=lambda: list(DEFAULT_OUTPUT_FIELDS))
    extra_fields: list[str] = field(default_factory=list)
    field_aliases: dict[str, str] = field(default_factory=dict)
    include_comments: bool = True
    max_comments: int = 15
    shapes: dict[str, list[str]] = field(default_factory=_copy_shapes)
    search_fields: list[str] = field(default_factory=lambda: list(DEFAULT_SEARCH_FIELDS))
    drop_empty: bool = True

    def output_fields(self) -> list[str]:
        names = list(self.fields or DEFAULT_OUTPUT_FIELDS)
        if "key" not in names:
            names.insert(0, "key")
        if not self.include_comments:
            names = [name for name in names if name != "comments"]
        return names

    def wants(self, name: str) -> bool:
        return name in set(self.output_fields())

    def request_field_ids(self, names: list[str] | None = None) -> list[str]:
        ids: list[str] = []
        for name in names if names is not None else self.output_fields():
            field_id = JIRA_API_FIELDS.get(name)
            if field_id and field_id not in ids:
                ids.append(field_id)
        if names is None:
            for field_id in self.extra_fields:
                if field_id not in ids:
                    ids.append(field_id)
        return ids

    def issue_projection(self) -> ProjectionSpec:
        return ProjectionSpec(
            name="jira.issue",
            fields=tuple(self.output_fields()),
            shapes={key: tuple(value) for key, value in self.shapes.items()},
            drop_empty=self.drop_empty,
        )

    def search_projection(self) -> ProjectionSpec:
        names = list(self.search_fields or DEFAULT_SEARCH_FIELDS)
        if "key" not in names:
            names.insert(0, "key")
        return ProjectionSpec(
            name="jira.search",
            fields=tuple(names),
            shapes={
                key: tuple(value)
                for key, value in self.shapes.items()
                if key in names
            },
            drop_empty=self.drop_empty,
        )

    def comments_projection(self) -> ProjectionSpec:
        return self.issue_projection().nested("comments", DEFAULT_SHAPES["comments"])

    def schema(self) -> dict[str, Any]:
        return {
            "fields": self.output_fields(),
            "search_fields": list(self.search_projection().fields),
            "extra_fields": self.extra_fields,
            "field_aliases": self.field_aliases,
            "shapes": {key: list(value) for key, value in self.shapes.items()},
            "include_comments": self.include_comments and self.wants("comments"),
            "max_comments": self.max_comments,
            "drop_empty": self.drop_empty,
        }


def project_issue(issue: dict[str, Any], settings: JiraSettings) -> dict[str, Any]:
    """Keep only configured output fields. Never pass through a raw Jira payload."""
    allowed = set(settings.output_fields())
    prepared = {key: value for key, value in issue.items() if key != "custom"}
    custom = dict(issue.get("custom") or {})
    for field_id, alias in settings.field_aliases.items():
        value = custom.get(alias) or custom.get(field_id)
        if value is not None and (alias in allowed or field_id in allowed):
            prepared[alias] = value
    if settings.wants("custom") and custom:
        prepared["custom"] = {
            key: value
            for key, value in custom.items()
            if key not in prepared
        }
    if settings.wants("comments") and "comments" not in prepared:
        prepared["comments"] = []
    projected = project(prepared, settings.issue_projection())
    if settings.wants("comments") and "comments" not in projected:
        projected["comments"] = []
    return projected

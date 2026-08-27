from __future__ import annotations

import json
from typing import Any


def render(payload: Any, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False)
    if fmt == "markdown":
        return to_markdown(payload)
    return to_text(payload)


def to_text(payload: Any) -> str:
    if isinstance(payload, dict) and "key" in payload and "summary" in payload:
        return _issue_text(payload)
    if isinstance(payload, dict) and "issue" in payload and "routing" in payload:
        return _prepare_text(payload)
    return json.dumps(payload, indent=2, ensure_ascii=False)


def to_markdown(payload: Any) -> str:
    if isinstance(payload, dict) and "issue" in payload and "routing" in payload:
        return _prepare_markdown(payload)
    if isinstance(payload, dict) and "key" in payload and "summary" in payload:
        return _issue_markdown(payload)
    return "```json\n" + json.dumps(payload, indent=2, ensure_ascii=False) + "\n```"


def _issue_text(issue: dict[str, Any]) -> str:
    lines = [
        f"{issue.get('key')}: {issue.get('summary')}",
        f"Status: {issue.get('status')}  Type: {issue.get('issue_type')}  "
        f"Priority: {issue.get('priority')}",
        f"URL: {issue.get('url')}",
        "",
        issue.get("description") or "(no description)",
    ]
    return "\n".join(lines).strip() + "\n"


def _issue_markdown(issue: dict[str, Any]) -> str:
    lines = [
        f"# {issue.get('key')}: {issue.get('summary')}",
        "",
        f"- **Status:** {issue.get('status')}",
        f"- **Type:** {issue.get('issue_type')}",
        f"- **Priority:** {issue.get('priority')}",
        f"- **Assignee:** {issue.get('assignee')}",
        f"- **URL:** {issue.get('url')}",
        "",
        "## Description",
        "",
        issue.get("description") or "_No description_",
        "",
    ]
    comments = issue.get("comments") or []
    if comments:
        lines.extend(["## Comments", ""])
        for comment in comments:
            lines.append(
                f"### {comment.get('author') or 'unknown'} ({comment.get('created')})"
            )
            lines.append("")
            lines.append(comment.get("body") or "")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def _prepare_text(payload: dict[str, Any]) -> str:
    issue = payload.get("issue") or {}
    routing = payload.get("routing") or {}
    lines = [
        _issue_text(issue).rstrip(),
        "",
        f"Workspace: {routing.get('workspace_id')} (score {routing.get('score')})",
        f"Open: {routing.get('open_command')}",
    ]
    missing = routing.get("missing_repos") or []
    if missing:
        lines.append(
            "Missing repos: " + ", ".join(item["id"] for item in missing)
        )
    return "\n".join(lines).strip() + "\n"


def _prepare_markdown(payload: dict[str, Any]) -> str:
    issue = payload.get("issue") or {}
    routing = payload.get("routing") or {}
    lines = [_issue_markdown(issue).rstrip(), "", "## Routing", ""]
    if not routing:
        lines.append("_No workspace matched._")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            f"- **Workspace:** `{routing.get('workspace_id')}` "
            f"({routing.get('workspace_name')})",
            f"- **Score:** {routing.get('score')}",
            f"- **Reasons:** {', '.join(routing.get('reasons') or []) or 'none'}",
            f"- **Open:** `{routing.get('open_command')}`",
            "",
            "### Repos",
            "",
        ]
    )
    for repo in routing.get("repos") or []:
        state = "cloned" if repo.get("cloned") else "missing"
        lines.append(f"- `{repo['id']}` ({state}) — `{repo['path']}`")
    next_steps = payload.get("next_steps") or []
    if next_steps:
        lines.extend(["", "### Next steps", ""])
        for index, step in enumerate(next_steps, start=1):
            lines.append(f"{index}. {step}")
    return "\n".join(lines).strip() + "\n"

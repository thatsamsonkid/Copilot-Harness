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
    if isinstance(payload, dict) and "templates" in payload and "manifest" in payload:
        return _templates_text(payload)
    if isinstance(payload, dict) and "template" in payload and "manifest" in payload:
        return _templates_text(
            {
                "manifest": payload.get("manifest"),
                "count": 1,
                "templates": [payload["template"]],
            }
        )
    if isinstance(payload, dict) and "template" in payload and "project" in payload:
        return _bootstrap_text(payload)
    if isinstance(payload, dict) and "services" in payload and "order" in payload:
        return _start_text(payload)
    return json.dumps(payload, indent=2, ensure_ascii=False)


def to_markdown(payload: Any) -> str:
    if isinstance(payload, dict) and "issue" in payload and "routing" in payload:
        return _prepare_markdown(payload)
    if isinstance(payload, dict) and "key" in payload and "summary" in payload:
        return _issue_markdown(payload)
    if isinstance(payload, dict) and "templates" in payload and "manifest" in payload:
        return _templates_markdown(payload)
    if isinstance(payload, dict) and "template" in payload and "manifest" in payload:
        return _templates_markdown(
            {
                "manifest": payload.get("manifest"),
                "count": 1,
                "templates": [payload["template"]],
            }
        )
    if isinstance(payload, dict) and "template" in payload and "project" in payload:
        return _bootstrap_markdown(payload)
    if isinstance(payload, dict) and "services" in payload and "order" in payload:
        return _start_markdown(payload)
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


def _templates_text(payload: dict[str, Any]) -> str:
    lines = [f"Templates ({payload.get('count', 0)}) from {payload.get('manifest')}", ""]
    templates = payload.get("templates") or []
    if not templates:
        lines.append("No templates listed. Add entries to templates.yml.")
        return "\n".join(lines).strip() + "\n"
    for item in templates:
        kind = item.get("kind") or item.get("language") or "template"
        lines.append(
            f"- {item.get('name')} [{kind}] {item.get('description') or ''}".rstrip()
        )
        lines.append(f"  {item.get('url')}")
        tags = item.get("tags") or []
        if tags:
            lines.append("  tags: " + ", ".join(tags))
    lines.append("")
    lines.append("Bootstrap: harness bootstrap --template <name> --name <folder>")
    return "\n".join(lines).strip() + "\n"


def _templates_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Project templates",
        "",
        f"Source: `{payload.get('manifest')}`",
        "",
    ]
    templates = payload.get("templates") or []
    if not templates:
        lines.append("_No templates listed. Add entries to `templates.yml`._")
        return "\n".join(lines).strip() + "\n"
    for item in templates:
        lines.append(f"## `{item.get('name')}`")
        lines.append("")
        if item.get("description"):
            lines.append(item["description"])
            lines.append("")
        lines.extend(
            [
                f"- **URL:** `{item.get('url')}`",
                f"- **Kind:** {item.get('kind') or 'n/a'}",
                f"- **Language:** {item.get('language') or 'n/a'}",
                f"- **Tags:** {', '.join(item.get('tags') or []) or 'none'}",
                f"- **Bootstrap:** `harness bootstrap --template {item.get('name')} --name <folder>`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _start_text(payload: dict[str, Any]) -> str:
    workspace = payload.get("workspace") or "all enabled repos"
    lines = [f"Start plan ({workspace})", ""]
    source = payload.get("plan_source")
    plan_file = payload.get("plan_file")
    if source == "saved" and plan_file:
        lines.append(f"Saved sequence: {plan_file}")
        lines.append("")
    elif payload.get("workspace") and plan_file and not payload.get("plan_exists"):
        lines.append(f"No saved sequence yet. Pin with --save → {plan_file}")
        lines.append("")
    services = payload.get("services") or []
    if not services:
        lines.append("No services in this plan.")
        return "\n".join(lines).strip() + "\n"
    for index, item in enumerate(services, start=1):
        port = item.get("port_hint")
        port_label = f"port {port}" if port else "port unknown"
        blocked = f" BLOCKED: {item['blocked']}" if item.get("blocked") else ""
        lines.append(
            f"{index}. {item.get('name')} [{item.get('kind')}/{item.get('role')}] "
            f"{item.get('command') or '(no command)'} ({port_label}){blocked}"
        )
        for proxy in item.get("proxies") or []:
            targets = ", ".join(
                str(target.get("target"))
                for target in (proxy.get("targets") or [])
                if target.get("target")
            )
            suffix = f" -> {targets}" if targets else ""
            lines.append(f"   proxy {proxy.get('relative')}{suffix}")
    return "\n".join(lines).strip() + "\n"


def _start_markdown(payload: dict[str, Any]) -> str:
    workspace = payload.get("workspace") or "all enabled repos"
    lines = [f"# Start plan (`{workspace}`)", ""]
    source = payload.get("plan_source")
    plan_file = payload.get("plan_file")
    if source == "saved" and plan_file:
        lines.append(f"Saved sequence: `{plan_file}`")
        lines.append("")
    elif payload.get("workspace") and plan_file and not payload.get("plan_exists"):
        lines.append(f"No saved sequence yet. Pin with `--save` → `{plan_file}`")
        lines.append("")
    services = payload.get("services") or []
    if not services:
        lines.append("_No services in this plan._")
        return "\n".join(lines).strip() + "\n"
    for index, item in enumerate(services, start=1):
        port = item.get("port_hint")
        port_label = f"port `{port}`" if port else "port unknown until start"
        command = f"`{item['command']}`" if item.get("command") else "_no command_"
        lines.append(
            f"{index}. **{item.get('name')}** ({item.get('kind')} / {item.get('role')}) "
            f"— {command} — {port_label}"
        )
        if item.get("blocked"):
            lines.append(f"   - Blocked: {item['blocked']}")
        for proxy in item.get("proxies") or []:
            targets = ", ".join(
                f"`{target.get('target')}`"
                for target in (proxy.get("targets") or [])
                if target.get("target")
            )
            detail = f" → {targets}" if targets else ""
            lines.append(f"   - Proxy `{proxy.get('relative')}`{detail}")
        for note in item.get("notes") or []:
            lines.append(f"   - {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _bootstrap_text(payload: dict[str, Any]) -> str:
    template = payload.get("template") or {}
    project = payload.get("project") or {}
    lines = [
        f"Bootstrap {project.get('name')} from {template.get('name')}",
        f"Path: {project.get('path')}",
        f"Remote: {project.get('remote')}",
    ]
    if payload.get("registered"):
        lines.append("Registered in repositories.yml")
    for step in payload.get("next_steps") or []:
        lines.append(f"- {step}")
    return "\n".join(lines).strip() + "\n"


def _bootstrap_markdown(payload: dict[str, Any]) -> str:
    template = payload.get("template") or {}
    project = payload.get("project") or {}
    lines = [
        f"# Bootstrap `{project.get('name')}`",
        "",
        f"- **Template:** `{template.get('name')}`",
        f"- **Path:** `{project.get('path')}`",
        f"- **Remote:** {project.get('remote')}",
        f"- **Registered:** {'yes' if payload.get('registered') else 'no'}",
        "",
    ]
    steps = payload.get("next_steps") or []
    if steps:
        lines.extend(["## Next steps", ""])
        for index, step in enumerate(steps, start=1):
            lines.append(f"{index}. {step}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"

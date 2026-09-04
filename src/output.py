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
    if isinstance(payload, dict) and "dirty_repos" in payload and "repos" in payload:
        return _status_text(payload)
    if isinstance(payload, dict) and "steps" in payload and "token_docs" in payload:
        return _init_text(payload)
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
    if _is_start_run_preview(payload):
        return _start_run_text(payload)
    if _is_figma_images(payload):
        return _figma_images_text(payload)
    if _is_figma_comments(payload):
        return _figma_comments_text(payload)
    if _is_figma_nodes(payload):
        return _figma_nodes_text(payload)
    if _is_skills(payload):
        return _skills_text(payload)
    if _is_commands(payload):
        return _commands_text(payload)
    if _is_bruno(payload):
        return _bruno_text(payload)
    if _is_cli_install(payload):
        return _cli_install_text(payload)
    if _is_workspace_graph(payload):
        return _workspace_graph_text(payload)
    if _is_workspace_create_menu(payload):
        return _workspace_create_menu_text(payload)
    if _is_glossary(payload):
        return _glossary_text(payload)
    return json.dumps(payload, indent=2, ensure_ascii=False)


def to_markdown(payload: Any) -> str:
    if isinstance(payload, dict) and "issue" in payload and "routing" in payload:
        return _prepare_markdown(payload)
    if isinstance(payload, dict) and "dirty_repos" in payload and "repos" in payload:
        return _status_markdown(payload)
    if isinstance(payload, dict) and "steps" in payload and "token_docs" in payload:
        return _init_text(payload)
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
    if _is_start_run_preview(payload):
        return _start_run_markdown(payload)
    if _is_figma_images(payload):
        return _figma_images_markdown(payload)
    if _is_figma_comments(payload):
        return _figma_comments_markdown(payload)
    if _is_figma_nodes(payload):
        return _figma_nodes_markdown(payload)
    if _is_skills(payload):
        return _skills_markdown(payload)
    if _is_commands(payload):
        return _commands_markdown(payload)
    if _is_bruno(payload):
        return _bruno_markdown(payload)
    if _is_cli_install(payload):
        return _cli_install_markdown(payload)
    if _is_workspace_graph(payload):
        return _workspace_graph_markdown(payload)
    if _is_workspace_create_menu(payload):
        return _workspace_create_menu_markdown(payload)
    if _is_glossary(payload):
        return _glossary_markdown(payload)
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
    if routing.get("suggested_branch"):
        lines.append(f"Branch: {routing['suggested_branch']}")
    done_when = payload.get("done_when") or []
    if done_when:
        lines.append("Done when:")
        for item in done_when:
            lines.append(f"- {item.get('text')}")
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
    if routing.get("suggested_branch"):
        lines.append(f"- **Branch:** `{routing['suggested_branch']}`")
    done_when = payload.get("done_when") or []
    if done_when:
        lines.extend(["", "### Done when", ""])
        for item in done_when:
            lines.append(f"- {item.get('text')}")
    next_steps = payload.get("next_steps") or []
    if next_steps:
        lines.extend(["", "### Next steps", ""])
        for index, step in enumerate(next_steps, start=1):
            lines.append(f"{index}. {step}")
    return "\n".join(lines).strip() + "\n"


def _status_text(payload: dict[str, Any]) -> str:
    lines = ["Sibling status", ""]
    workspace = payload.get("workspace")
    scope = payload.get("workspace_scope") or {}
    if workspace:
        lines.append(f"Workspace: {workspace}")
        lines.append("")
    elif scope.get("detail"):
        lines.append(str(scope["detail"]))
        lines.append("")
    hint = (payload.get("cwd_hint") or {}).get("detail")
    if hint:
        lines.append(hint)
        lines.append("")
    for repo in payload.get("repos") or []:
        name = repo.get("id") or repo.get("name")
        git = repo.get("git") or {}
        if not repo.get("cloned"):
            loc = f" ({repo['relpath']})" if repo.get("relpath") and repo.get("relpath") != name else ""
            lines.append(f"- {name}{loc}: not cloned")
            continue
        flags = []
        if git.get("dirty"):
            flags.append("dirty")
        if git.get("behind"):
            flags.append(f"behind {git['behind']}")
        if git.get("ahead"):
            flags.append(f"ahead {git['ahead']}")
        if (repo.get("graphify") or {}).get("stale"):
            flags.append("graph stale")
        extra = f" ({', '.join(flags)})" if flags else ""
        loc = f" [{repo['relpath']}]" if repo.get("relpath") and repo.get("relpath") != name else ""
        lines.append(f"- {name}{loc}: {git.get('branch') or '?'}{extra}")
    return "\n".join(lines).strip() + "\n"


def _status_markdown(payload: dict[str, Any]) -> str:
    return "```text\n" + _status_text(payload) + "```\n"


def _init_text(payload: dict[str, Any]) -> str:
    lines = ["Harness init", ""]
    for step in payload.get("steps") or []:
        mark = "x" if step.get("ok") else " "
        extra = f" — {step.get('action')}" if step.get("action") and not step.get("ok") else ""
        lines.append(f"- [{mark}] {step.get('detail')}{extra}")
    starters = payload.get("workspaces") or []
    if starters:
        lines.extend(["", "Starter workspaces (catalog/stack.yaml):"])
        for item in starters:
            detail = f" — {item.get('description')}" if item.get("description") else ""
            lines.append(f"- {item.get('id')}: {item.get('name')}{detail}")
            if item.get("open_command"):
                lines.append(f"  {item['open_command']}")
        hint = payload.get("workspace_hint")
        if hint:
            lines.append(hint)
    commands = payload.get("next_commands") or []
    if commands:
        lines.extend(["", "Next:"])
        for command in commands:
            lines.append(f"  {command}")
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
    lines.append("Bootstrap: goat bootstrap --template <name> --name <folder>")
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
                f"- **Bootstrap:** `goat bootstrap --template {item.get('name')} --name <folder>`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _start_text(payload: dict[str, Any]) -> str:
    workspace = payload.get("workspace") or "all enabled repos"
    lines = [f"Start plan ({workspace})", ""]
    scope = payload.get("workspace_scope") or {}
    if scope.get("detected") is False and scope.get("source") == "none":
        lines.append(str(scope.get("detail") or ""))
        lines.append("")
    source = payload.get("plan_source")
    plan_file = payload.get("plan_file")
    if source == "saved" and plan_file:
        lines.append(f"Saved sequence: {plan_file}")
        lines.append("")
    elif payload.get("workspace") and plan_file and not payload.get("plan_exists"):
        lines.append(f"No saved sequence yet. Pin with --save → {plan_file}")
        lines.append("")
    invoke = payload.get("invoke") or {}
    if invoke.get("command"):
        lines.append(f"CLI: {invoke['command']}")
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
        if item.get("run_via") and item.get("run_via") != "terminal":
            lines.append(f"   run_via {item['run_via']}")
        if item.get("copilot_command"):
            lines.append(f"   copilot {item['copilot_command']}")
        launch = item.get("launch") or {}
        if launch.get("configuration"):
            keys = ",".join(launch.get("env_keys") or [])
            extra = f" env_keys={keys}" if keys else ""
            lines.append(
                f"   launch {launch['configuration']}{extra}"
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
    invoke = payload.get("invoke") or {}
    if invoke.get("command"):
        lines.extend(
            [
                f"CLI (any cwd): `{invoke['command']}`",
                "",
            ]
        )
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
        if item.get("run_via") and item.get("run_via") != "terminal":
            lines.append(f"   - Run via: `{item['run_via']}`")
        if item.get("copilot_command"):
            lines.append(f"   - Copilot command: `{item['copilot_command']}`")
        launch = item.get("launch") or {}
        if launch.get("configuration") or launch.get("secret_risk"):
            config = launch.get("configuration") or "launch.json"
            keys = ", ".join(f"`{key}`" for key in (launch.get("env_keys") or []))
            detail = f" (env keys: {keys})" if keys else ""
            lines.append(f"   - Launch `{config}`{detail}")
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


def _is_figma_images(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and "file_key" in payload
        and "images" in payload
        and "services" not in payload
        and "issue" not in payload
    )


def _is_figma_comments(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and "file_key" in payload
        and "comments" in payload
        and "images" not in payload
        and "nodes" not in payload
        and "issue" not in payload
    )


def _is_figma_nodes(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and "file_key" in payload
        and "nodes" in payload
        and "images" not in payload
        and "issue" not in payload
    )


def _figma_images_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Figma {payload.get('file_key')} ({payload.get('format')} @ {payload.get('scale')}x)",
        f"File: {payload.get('url')}",
        "",
    ]
    images = payload.get("images") or []
    if not images:
        lines.append("No rendered image URLs.")
    for item in images:
        lines.append(f"- {item.get('id')}: {item.get('url')}")
    missing = payload.get("missing") or []
    if missing:
        lines.append("")
        lines.append("Missing: " + ", ".join(str(item) for item in missing))
    return "\n".join(lines).strip() + "\n"


def _figma_images_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Figma `{payload.get('file_key')}`",
        "",
        f"- **File:** {payload.get('url')}",
        f"- **Format:** {payload.get('format')} @ {payload.get('scale')}x",
        "",
        "## Images",
        "",
    ]
    images = payload.get("images") or []
    if not images:
        lines.append("_No rendered image URLs._")
    for item in images:
        lines.append(f"- `{item.get('id')}` — {item.get('url')}")
    missing = payload.get("missing") or []
    if missing:
        lines.extend(
            [
                "",
                "## Missing",
                "",
                ", ".join(f"`{item}`" for item in missing),
            ]
        )
    lines.append("")
    lines.append("Open each image URL in VS Code Simple Browser to look at the frame.")
    return "\n".join(lines).strip() + "\n"


def _figma_comments_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Figma comments {payload.get('file_key')}",
        f"File: {payload.get('url')}",
        "",
    ]
    comments = payload.get("comments") or []
    if not comments:
        lines.append("No comments.")
    for comment in comments:
        node = f" on {comment.get('node_id')}" if comment.get("node_id") else ""
        resolved = " (resolved)" if comment.get("resolved") else ""
        lines.append(
            f"- {comment.get('author') or 'unknown'} ({comment.get('created')})"
            f"{node}{resolved}: {comment.get('message') or ''}"
        )
    return "\n".join(lines).strip() + "\n"


def _figma_comments_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Figma comments `{payload.get('file_key')}`",
        "",
        f"- **File:** {payload.get('url')}",
        "",
        "## Comments",
        "",
    ]
    comments = payload.get("comments") or []
    if not comments:
        lines.append("_No comments._")
    for comment in comments:
        heading = comment.get("author") or "unknown"
        created = comment.get("created")
        if created:
            heading = f"{heading} ({created})"
        extras = []
        if comment.get("node_id"):
            extras.append(f"node `{comment['node_id']}`")
        if comment.get("resolved"):
            extras.append("resolved")
        lines.append(f"### {heading}")
        lines.append("")
        if extras:
            lines.append("- " + ", ".join(extras))
            lines.append("")
        lines.append(comment.get("message") or "")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _figma_nodes_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Figma nodes {payload.get('file_key')} (depth {payload.get('depth')})",
        f"File: {payload.get('url')}",
        "",
        payload.get("note")
        or "Raw Figma node JSON. Use only on a small targeted frame.",
        "",
        json.dumps(payload.get("nodes") or {}, indent=2, ensure_ascii=False),
    ]
    missing = payload.get("missing") or []
    if missing:
        lines.extend(["", "Missing: " + ", ".join(str(item) for item in missing)])
    return "\n".join(lines).strip() + "\n"


def _figma_nodes_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Figma nodes `{payload.get('file_key')}`",
        "",
        f"- **File:** {payload.get('url')}",
        f"- **Depth:** {payload.get('depth')}",
        "",
        payload.get("note")
        or "Raw Figma node JSON. Use only on a small targeted frame so the tree does not overwhelm Copilot context.",
        "",
        "```json",
        json.dumps(payload.get("nodes") or {}, indent=2, ensure_ascii=False),
        "```",
    ]
    missing = payload.get("missing") or []
    if missing:
        lines.extend(
            [
                "",
                "## Missing",
                "",
                ", ".join(f"`{item}`" for item in missing),
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _is_start_run_preview(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and "name" in payload
        and "command" in payload
        and "applied_args" in payload
        and "env_keys" in payload
        and "services" not in payload
    )


def _start_run_text(payload: dict[str, Any]) -> str:
    mode = "dry-run" if payload.get("dry_run") else "run"
    lines = [f"Start {mode} ({payload.get('name')})", ""]
    if payload.get("launch_configuration"):
        lines.append(f"Launch: {payload['launch_configuration']}")
    lines.append(f"cwd: {payload.get('cwd')}")
    lines.append(f"command: {payload.get('command')}")
    if payload.get("exec_command"):
        lines.append(f"exec_command: {payload['exec_command']}")
    if payload.get("applied_args") or payload.get("arg_count"):
        lines.append(f"arg_count: {payload.get('arg_count', 0)}")
    if payload.get("applied_vm_args") or payload.get("vm_arg_count"):
        lines.append(f"vm_arg_count: {payload.get('vm_arg_count', 0)}")
    if payload.get("java_tool_options"):
        lines.append("java_tool_options: applied")
    keys = payload.get("env_keys") or []
    if keys:
        lines.append(f"env_keys: {','.join(keys)}")
    overwritten = payload.get("overwritten_keys") or []
    if overwritten:
        lines.append(f"overwritten: {','.join(overwritten)}")
    return "\n".join(lines).strip() + "\n"


def _start_run_markdown(payload: dict[str, Any]) -> str:
    mode = "dry-run" if payload.get("dry_run") else "run"
    lines = [f"# Start {mode} (`{payload.get('name')}`)", ""]
    if payload.get("launch_configuration"):
        lines.append(f"- **Launch:** `{payload['launch_configuration']}`")
    lines.append(f"- **cwd:** `{payload.get('cwd')}`")
    lines.append(f"- **command:** `{payload.get('command')}`")
    if payload.get("exec_command"):
        lines.append(f"- **exec_command:** `{payload['exec_command']}`")
    if payload.get("applied_args") or payload.get("arg_count"):
        lines.append(f"- **arg_count:** {payload.get('arg_count', 0)}")
    if payload.get("applied_vm_args") or payload.get("vm_arg_count"):
        lines.append(f"- **vm_arg_count:** {payload.get('vm_arg_count', 0)}")
    if payload.get("java_tool_options"):
        lines.append("- **java_tool_options:** applied")
    keys = payload.get("env_keys") or []
    if keys:
        lines.append("- **env_keys:** " + ", ".join(f"`{key}`" for key in keys))
    return "\n".join(lines).strip() + "\n"


def _is_skills(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and "dest" in payload
        and "available" in payload
        and ("copied" in payload or "installed" in payload)
        and "issue" not in payload
        and "services" not in payload
    )


def _is_cli_install(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("kind") == "cli_install"


def _is_workspace_graph(payload: Any) -> bool:
    return isinstance(payload, dict) and str(payload.get("kind") or "").startswith(
        "workspace_graph"
    )


def _workspace_graph_text(payload: dict[str, Any]) -> str:
    kind = payload.get("kind")
    if kind == "workspace_graph_scan":
        lines = ["Workspace graph scan", ""]
        for row in payload.get("extractors") or []:
            lines.append(
                f"{row.get('name')}: {row.get('nodes')} nodes, "
                f"{row.get('candidates')} candidates"
            )
        return "\n".join(lines).strip() + "\n"
    if kind == "workspace_graph_build":
        return (
            f"Wrote {payload.get('file')}\n"
            f"nodes: {payload.get('nodes')}  edges: {payload.get('edges')}\n"
        )
    if kind == "workspace_graph_explain":
        lines = []
        for edge in payload.get("edges") or []:
            lines.append(
                f"{edge.get('source')} {edge.get('relationship')} {edge.get('target')}"
            )
            lines.append(f"Classification: {edge.get('classification')}")
            lines.append(f"Confidence: {edge.get('confidence')}")
            lines.append("Evidence:")
            for index, item in enumerate(edge.get("evidence") or [], start=1):
                label = item.get("key") or item.get("value") or item.get("type")
                where = item.get("file") or item.get("extractor")
                lines.append(f"{index}. {label} ({where})")
            lines.append("")
        return "\n".join(lines).strip() + "\n"
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _workspace_graph_markdown(payload: dict[str, Any]) -> str:
    return _workspace_graph_text(payload)


def _cli_install_text(payload: dict[str, Any]) -> str:
    action = payload.get("action") or "install"
    verb = "Uninstalled" if action == "uninstall" else "Installed"
    if payload.get("dry_run"):
        verb = f"Would {action}"
    lines = [
        f"{verb} goat PATH shim",
        "",
        f"root: {payload.get('goat_root')}",
        f"bin:  {payload.get('bin_dir')}",
    ]
    for shim in payload.get("shims") or []:
        state = []
        if shim.get("written"):
            state.append("written")
        if shim.get("removed"):
            state.append("removed")
        if shim.get("would_write"):
            state.append("would write")
        if shim.get("would_remove"):
            state.append("would remove")
        if not state and shim.get("existed"):
            state.append("present")
        extra = f" ({', '.join(state)})" if state else ""
        lines.append(f"shim: {shim.get('path')}{extra}")
    if payload.get("on_path"):
        lines.append(f"on PATH: yes ({payload.get('which') or 'bin dir'})")
        if payload.get("shadowed_by"):
            lines.append(f"shadowed by: {payload['shadowed_by']}")
    else:
        lines.append("on PATH: no")
        hint = payload.get("path_hint")
        if hint:
            lines.append(hint)
    next_commands = payload.get("next") or []
    if next_commands:
        lines.append("")
        lines.append("Next:")
        for command in next_commands:
            lines.append(f"  {command}")
    return "\n".join(lines).strip() + "\n"


def _cli_install_markdown(payload: dict[str, Any]) -> str:
    return "```text\n" + _cli_install_text(payload) + "```\n"


def _is_commands(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("kind") == "command_reference"


def _commands_text(payload: dict[str, Any]) -> str:
    commands = payload.get("commands") or []
    width = max((len(item.get("usage") or "") for item in commands), default=0)
    lines = [
        f"Goat CLI ({payload.get('count', len(commands))} commands)",
        "",
    ]
    shared = payload.get("shared") or []
    if shared:
        names = ", ".join(item.get("name") or "" for item in shared)
        lines.append(f"Shared flags: {names}")
        lines.append("")
    current_group = None
    for item in commands:
        group = item.get("group")
        if group != current_group:
            if current_group is not None:
                lines.append("")
            lines.append(f"{group}")
            current_group = group
        usage = item.get("usage") or f"goat {item.get('command')}"
        help_text = item.get("help") or ""
        lines.append(f"  {usage.ljust(width)}  {help_text}".rstrip())
    lines.append("")
    lines.append("More detail: goat <command> --help")
    return "\n".join(lines).strip() + "\n"


def _commands_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goat CLI",
        "",
        "Run from this repo: `uv run goat <command>`. After `cd` into a sibling, "
        "use `uv run --project \"$GOAT_ROOT\" goat …` or `./scripts/goat.sh`.",
        "",
        "Stdout is JSON by default. Use `--format markdown` or `text` for a human view.",
        "",
    ]
    shared = payload.get("shared") or []
    if shared:
        names = ", ".join(f"`{item.get('name')}`" for item in shared)
        lines.extend([f"Shared flags (every command): {names}", ""])
    current_group = None
    for item in payload.get("commands") or []:
        group = item.get("group")
        if group != current_group:
            if current_group is not None:
                lines.append("")
            lines.extend(
                [
                    f"## `{group}`",
                    "",
                    "| Command | What it does |",
                    "| --- | --- |",
                ]
            )
            current_group = group
        usage = item.get("usage") or f"goat {item.get('command')}"
        help_text = (item.get("help") or "").replace("|", "\\|")
        lines.append(f"| `{usage}` | {help_text} |")
    lines.extend(["", "For flags, run `goat <command> --help`.", ""])
    return "\n".join(lines).strip() + "\n"


def _skills_text(payload: dict[str, Any]) -> str:
    brief = bool(payload.get("brief") or payload.get("needs_selection"))
    skills = payload.get("skills") or payload.get("available") or []
    if brief and not payload.get("copied") and not payload.get("updated"):
        lines = []
        if payload.get("needs_selection"):
            lines.append(payload.get("detail") or "Pick skills, then rerun with --only.")
            if payload.get("install_command"):
                lines.append(payload["install_command"])
            lines.append("")
        if not skills:
            lines.append("No skills found.")
        for skill in skills:
            lines.append(_skill_brief_line(skill))
        return "\n".join(lines).strip() + "\n"

    lines = [
        f"Agent skills ({payload.get('dest_kind') or 'workspace'})",
        f"Dest: {payload.get('dest')}",
        "",
    ]
    if payload.get("url"):
        lines.append(f"Remote: {payload['url']}")
    if payload.get("needs_selection"):
        lines.append(payload.get("detail") or "Pick skills, then rerun with --only.")
        if payload.get("install_command"):
            lines.append(payload["install_command"])
        lines.append("")
    if skills:
        lines.append("Available:")
        for skill in skills:
            lines.append(f"- {_skill_brief_line(skill)}")
        lines.append("")
    for label, key in (
        ("Copied", "copied"),
        ("Updated", "updated"),
        ("Native", "native"),
        ("Conflicts", "conflicts"),
    ):
        items = payload.get(key) or []
        if not items:
            continue
        lines.append(f"{label}:")
        for item in items:
            name = item.get("installed_as") or item.get("name")
            lines.append(f"- {name} ({item.get('source_id')})")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _skill_brief_line(skill: dict[str, Any]) -> str:
    name = skill.get("name") or skill.get("pick") or "?"
    source = skill.get("source_id")
    label = f"{name} ({source})" if source else name
    description = skill.get("description") or ""
    return f"{label} — {description}" if description else label


def _skills_markdown(payload: dict[str, Any]) -> str:
    brief = bool(payload.get("brief") or payload.get("needs_selection"))
    skills = payload.get("skills") or payload.get("available") or []
    if brief and not payload.get("copied") and not payload.get("updated"):
        lines = ["# Agent skills", ""]
        if payload.get("needs_selection"):
            lines.append(payload.get("detail") or "Pick skills, then rerun with `--only`.")
            lines.append("")
        for skill in skills:
            name = skill.get("name") or skill.get("pick")
            source = skill.get("source_id")
            desc = skill.get("description") or ""
            title = f"`{name}` ({source})" if source else f"`{name}`"
            lines.append(f"- {title}" + (f" — {desc}" if desc else ""))
        return "\n".join(lines).strip() + "\n"

    lines = [
        "# Agent skills",
        "",
        f"- **Dest:** `{payload.get('dest')}`",
        f"- **Kind:** {payload.get('dest_kind') or 'workspace'}",
        "",
    ]
    if payload.get("url"):
        lines.append(f"- **Remote:** {payload['url']}")
        lines.append("")
    if payload.get("needs_selection"):
        lines.append(payload.get("detail") or "Pick skills, then rerun with `--only`.")
        lines.append("")
        if payload.get("install_command"):
            lines.append(f"`{payload['install_command']}`")
            lines.append("")
    if skills:
        lines.extend(["## Available", ""])
        for skill in skills:
            name = skill.get("name") or skill.get("pick")
            source = skill.get("source_id")
            desc = f" — {skill['description']}" if skill.get("description") else ""
            title = f"`{name}` ({source})" if source else f"`{name}`"
            lines.append(f"- {title}{desc}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


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


def _is_bruno(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and str(payload.get("kind") or "").startswith("bruno_")
    )


def _bruno_text(payload: dict[str, Any]) -> str:
    kind = payload.get("kind")
    if kind == "bruno_run":
        lines = [
            f"Bruno run ({'dry-run' if payload.get('dry_run') else 'execute'})",
            f"cwd: {payload.get('cwd')}",
            f"env: {payload.get('env')}",
            "command: " + " ".join(str(part) for part in (payload.get("bru_command") or [])),
        ]
        if payload.get("exit_code") is not None:
            lines.append(f"exit: {payload.get('exit_code')}")
        return "\n".join(lines).strip() + "\n"
    collections = payload.get("collections") or []
    requests = payload.get("requests") or []
    workflows = payload.get("workflows") or []
    environments = payload.get("environments") or []
    lines = [f"Bruno {kind or 'inventory'}"]
    if payload.get("default_env"):
        lines.append(f"default env: {payload['default_env']}")
    for item in collections:
        envs = ",".join(item.get("environments") or []) or "-"
        lines.append(
            f"- {item.get('id')} ({item.get('request_count')} requests, envs {envs})"
        )
    for item in requests:
        lines.append(
            f"- {item.get('method') or '?'} {item.get('id')} {item.get('url') or ''}"
        )
    for item in environments:
        lines.append(
            f"- env {item.get('name')} vars={','.join(item.get('vars') or []) or '-'}"
        )
    for item in workflows:
        lines.append(f"- workflow {item.get('id')}: {item.get('description') or ''}")
    if payload.get("clone_command"):
        lines.append(f"clone: {payload['clone_command']}")
    return "\n".join(lines).strip() + "\n"


def _bruno_markdown(payload: dict[str, Any]) -> str:
    kind = payload.get("kind")
    if kind == "bruno_run":
        command = " ".join(f"`{part}`" if " " in str(part) else str(part) for part in (payload.get("bru_command") or []))
        lines = [
            "# Bruno run",
            "",
            f"- **cwd:** `{payload.get('cwd')}`",
            f"- **env:** `{payload.get('env')}`",
            f"- **dry-run:** {'yes' if payload.get('dry_run') else 'no'}",
            f"- **command:** `{command}`",
            "",
        ]
        return "\n".join(lines).strip() + "\n"
    lines = [f"# Bruno `{kind or 'inventory'}`", ""]
    if payload.get("default_env"):
        lines.append(f"- **Default env:** `{payload['default_env']}`")
        lines.append("")
    for item in payload.get("collections") or []:
        envs = ", ".join(f"`{name}`" for name in (item.get("environments") or [])) or "_none_"
        lines.append(
            f"- **{item.get('id')}** — {item.get('request_count')} requests, envs {envs}"
        )
    for item in payload.get("requests") or []:
        lines.append(
            f"- `{item.get('method') or '?'}` `{item.get('id')}` {item.get('url') or ''}"
        )
    for item in payload.get("environments") or []:
        lines.append(f"- env `{item.get('name')}` (names only)")
    for item in payload.get("workflows") or []:
        lines.append(f"- workflow `{item.get('id')}` — {item.get('description') or ''}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def _is_glossary(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("kind") == "glossary"


def _glossary_text(payload: dict[str, Any]) -> str:
    lines = [f"Glossary ({payload.get('count', 0)} terms)"]
    query = payload.get("query")
    if query:
        status = "matched" if payload.get("matched") else "unmatched"
        lines.append(f"{payload.get('action') or 'lookup'} {query} ({status})")
    if payload.get("file"):
        lines.append(f"file: {payload.get('relative') or payload['file']}")
    for item in payload.get("terms") or []:
        aliases = ", ".join(item.get("also") or [])
        extra = f" ({aliases})" if aliases else ""
        source = item.get("source") or "goat"
        visibility = item.get("visibility") or "public"
        lines.append(
            f"- {item.get('term')}{extra} [{item.get('kind')}/{visibility}/{source}]"
        )
        meaning = (item.get("meaning") or "").strip()
        if meaning:
            lines.append(f"    {meaning}")
    suggestions = payload.get("suggestions") or []
    if suggestions:
        lines.append("Suggestions:")
        for item in suggestions:
            lines.append(f"- {item.get('term')} ({item.get('source')})")
    for hint in payload.get("guidance") or []:
        lines.append(hint)
    return "\n".join(lines).strip() + "\n"


def _glossary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Glossary",
        "",
        f"- **Count:** {payload.get('count', 0)}",
    ]
    if payload.get("query"):
        lines.append(f"- **Query:** `{payload['query']}`")
        lines.append(f"- **Matched:** {'yes' if payload.get('matched') else 'no'}")
    if payload.get("relative") or payload.get("file"):
        lines.append(f"- **File:** `{payload.get('relative') or payload.get('file')}`")
    lines.append("")
    terms = payload.get("terms") or []
    if terms:
        lines.extend(
            [
                "| Term | Also | Kind | Visibility | Source | Meaning |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in terms:
            also = ", ".join(f"`{alias}`" for alias in (item.get("also") or [])) or "—"
            meaning = (item.get("meaning") or "").replace("|", "\\|")
            lines.append(
                f"| `{item.get('term')}` | {also} | {item.get('kind')} | "
                f"{item.get('visibility') or 'public'} | {item.get('source')} | {meaning} |"
            )
        lines.append("")
    suggestions = payload.get("suggestions") or []
    if suggestions:
        lines.extend(["## Suggestions", ""])
        for item in suggestions:
            lines.append(f"- `{item.get('term')}` ({item.get('source')})")
        lines.append("")
    guidance = payload.get("guidance") or []
    if guidance:
        lines.extend(["## Guidance", ""])
        for hint in guidance:
            lines.append(f"- {hint}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _is_workspace_create_menu(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("kind") == "workspace_create_menu"


def _workspace_create_menu_text(payload: dict[str, Any]) -> str:
    lines = ["Repositories from repositories.yml:", ""]
    for item in payload.get("projects") or []:
        tags = ", ".join(item.get("tags") or []) or "(no tags)"
        extra = []
        if item.get("path"):
            extra.append(f"path: {item['path']}")
        extra.append(f"tags: {tags}")
        if item.get("description"):
            extra.append(str(item["description"]))
        extra.append("cloned" if item.get("cloned") else "not cloned")
        lines.append(f"  {item.get('n')}. {item.get('name')}")
        lines.append(f"     {'  ·  '.join(extra)}")
    disabled = payload.get("disabled") or []
    if disabled:
        lines.append("")
        lines.append("Disabled: " + ", ".join(disabled))
    workspaces = payload.get("workspaces") or []
    if workspaces:
        lines.append("")
        lines.append(
            "Existing workspaces: "
            + ", ".join(item.get("id") or "" for item in workspaces)
        )
    lines.append("")
    lines.append(
        payload.get("select")
        or "Enter numbers, names, ranges (1-3), all, or tag:<tag>."
    )
    return "\n".join(lines).strip() + "\n"


def _workspace_create_menu_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# New workspace",
        "",
        "| # | Repo | Tags | Cloned |",
        "| --- | --- | --- | --- |",
    ]
    for item in payload.get("projects") or []:
        tags = ", ".join(f"`{tag}`" for tag in (item.get("tags") or [])) or "—"
        cloned = "yes" if item.get("cloned") else "no"
        lines.append(
            f"| {item.get('n')} | `{item.get('name')}` | {tags} | {cloned} |"
        )
    workspaces = payload.get("workspaces") or []
    if workspaces:
        ids = ", ".join(f"`{item.get('id')}`" for item in workspaces)
        lines.extend(["", f"Existing workspaces: {ids}"])
    lines.extend(["", payload.get("select") or "", ""])
    return "\n".join(lines).strip() + "\n"

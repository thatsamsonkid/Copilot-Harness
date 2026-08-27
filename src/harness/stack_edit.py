from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from harness import HarnessError
from harness.catalog import Workspace

_WORKSPACES_KEY = re.compile(r"^workspaces\s*:(.*)$")
_TOP_LEVEL_KEY = re.compile(r"^[A-Za-z_][\w-]*\s*:")
_LIST_ITEM = re.compile(r"^([ \t]*)- (.*)$")
_ID_INLINE = re.compile(r"^id:\s*(.+?)\s*$")
_ID_NESTED = re.compile(r"^([ \t]+)id:\s*(.+?)\s*$")


def upsert_workspace_in_stack(
    path: Path,
    workspace: Workspace,
    *,
    replace: bool = False,
) -> None:
    """Insert or replace a workspace entry in catalog/stack.yaml, keeping comments."""
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    try:
        updated = upsert_workspace_text(original, workspace, replace=replace)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        items = raw.get("workspaces") or []
        ids = [str(item.get("id")) for item in items if isinstance(item, dict)]
        if workspace.id not in ids:
            raise HarnessError("Failed to persist workspace to catalog/stack.yaml")
        if ids.count(workspace.id) > 1:
            raise HarnessError(f"Duplicate workspace id after write: {workspace.id}")
    except Exception:
        if original:
            path.write_text(original, encoding="utf-8")
        elif path.exists():
            path.unlink()
        raise


def upsert_workspace_text(
    text: str, workspace: Workspace, *, replace: bool = False
) -> str:
    entry = format_workspace_yaml(workspace)
    if not text.strip():
        return "workspaces:\n" + entry
    if not text.endswith("\n"):
        text += "\n"

    lines = text.splitlines(keepends=True)
    span = _workspaces_section(lines)
    if span is None:
        if not text.endswith("\n"):
            text += "\n"
        if not text.endswith("\n\n"):
            text += "\n"
        return text + "workspaces:\n" + entry

    start, end = span
    header = lines[start]
    match = _WORKSPACES_KEY.match(header.rstrip("\n"))
    inline = (match.group(1) or "").strip() if match else ""
    item_indent, items = _workspace_items(lines, start, end)

    existing = next((item for item in items if item[0] == workspace.id), None)
    if existing and not replace:
        raise HarnessError(
            f"Workspace {workspace.id} already exists. Pass --force to replace it."
        )

    new_lines = list(lines)
    formatted = _indent_entry(entry, item_indent if items else 2)
    if existing:
        item_start, item_end = existing[1], existing[2]
        new_lines[item_start:item_end] = [formatted]
    elif inline in {"", "|", ">"} or inline == "[]":
        header_line = "workspaces:\n" if inline == "[]" else header
        body = list(lines[start + 1 : end])
        if body and items and body[-1].strip():
            body.append("\n")
        new_lines[start:end] = [header_line, *body, formatted]
    else:
        # Flow-style list or other inline value — rewrite the section as a block.
        raw = yaml.safe_load(text) or {}
        others = [
            item
            for item in (raw.get("workspaces") or [])
            if isinstance(item, dict) and str(item.get("id")) != workspace.id
        ]
        rebuilt = ["workspaces:\n"]
        for item in others:
            rebuilt.append(_indent_entry(_format_raw_workspace(item), 2))
        rebuilt.append(formatted)
        new_lines[start:end] = rebuilt

    result = "".join(new_lines)
    if not result.endswith("\n"):
        result += "\n"
    return result


def format_workspace_yaml(workspace: Workspace) -> str:
    lines = [
        f"  - id: {workspace.id}",
        f"    name: {_yaml_scalar(workspace.name)}",
    ]
    if workspace.description:
        lines.append(f"    description: {_yaml_scalar(workspace.description)}")
    if workspace.folders:
        lines.append(f"    folders: [{', '.join(workspace.folders)}]")
    if workspace.tags:
        lines.append(f"    tags: [{', '.join(workspace.tags)}]")
    if not workspace.include_harness:
        lines.append("    include_harness: false")
    if workspace.fallback:
        lines.append("    fallback: true")
    match = workspace.match
    if any(
        (
            match.projects,
            match.components,
            match.labels,
            match.issue_types,
            match.keywords,
        )
    ):
        lines.append("    match:")
        if match.projects:
            lines.append(f"      projects: [{', '.join(match.projects)}]")
        if match.components:
            lines.append(f"      components: [{', '.join(match.components)}]")
        if match.labels:
            lines.append(f"      labels: [{', '.join(match.labels)}]")
        if match.issue_types:
            lines.append(f"      issue_types: [{', '.join(match.issue_types)}]")
        if match.keywords:
            lines.append(f"      keywords: [{', '.join(match.keywords)}]")
    return "\n".join(lines) + "\n"


def _format_raw_workspace(item: dict) -> str:
    from harness.catalog import Workspace, WorkspaceMatch

    match_raw = item.get("match") or {}
    workspace = Workspace(
        id=str(item["id"]),
        name=str(item.get("name") or item["id"]),
        description=str(item.get("description") or ""),
        folders=[str(v) for v in (item.get("folders") or [])],
        tags=[str(v) for v in (item.get("tags") or [])],
        include_harness=bool(item.get("include_harness", True)),
        fallback=bool(item.get("fallback", False)),
        match=WorkspaceMatch(
            projects=[str(v) for v in (match_raw.get("projects") or [])],
            components=[str(v) for v in (match_raw.get("components") or [])],
            labels=[str(v) for v in (match_raw.get("labels") or [])],
            issue_types=[str(v) for v in (match_raw.get("issue_types") or [])],
            keywords=[str(v) for v in (match_raw.get("keywords") or [])],
        ),
    )
    return format_workspace_yaml(workspace)


def _yaml_scalar(value: str) -> str:
    if value == "" or value.strip() != value:
        return json.dumps(value)
    special = set(":#{}[]&*?|>'!%@`,\\\"\n\t")
    if any(char in special for char in value):
        return json.dumps(value)
    if value.lower() in {"true", "false", "null", "yes", "no", "on", "off"}:
        return json.dumps(value)
    if value[:1] in "-?":
        return json.dumps(value)
    return value


def _indent_entry(entry: str, item_indent: int) -> str:
    """Re-indent a 2-space workspace entry to the detected list indent."""
    if item_indent == 2:
        return entry if entry.endswith("\n") else entry + "\n"
    shift = item_indent - 2
    lines = []
    for line in entry.splitlines():
        if not line.strip():
            lines.append("\n")
            continue
        if shift > 0:
            lines.append((" " * shift) + line + "\n")
        else:
            lines.append(line[-shift:] + "\n" if line.startswith("  ") else line + "\n")
    if not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return "".join(lines)


def _workspaces_section(lines: list[str]) -> tuple[int, int] | None:
    start = None
    for index, line in enumerate(lines):
        if _WORKSPACES_KEY.match(line.rstrip("\n")):
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].rstrip("\n")
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if _TOP_LEVEL_KEY.match(stripped) and not stripped.startswith(" "):
            end = index
            break
    return start, end


def _workspace_items(
    lines: list[str], start: int, end: int
) -> tuple[int, list[tuple[str, int, int]]]:
    """Return (item_indent, [(id, start, end), ...]) within the workspaces section."""
    items: list[tuple[str, int, int]] = []
    item_indent: int | None = None
    index = start + 1
    while index < end:
        stripped = lines[index].rstrip("\n")
        match = _LIST_ITEM.match(stripped)
        if match and (item_indent is None or len(match.group(1)) == item_indent):
            item_indent = len(match.group(1))
            item_start = index
            rest = match.group(2)
            workspace_id = _id_from_rest(rest)
            index += 1
            while index < end:
                nxt = lines[index].rstrip("\n")
                nxt_item = _LIST_ITEM.match(nxt)
                if nxt_item and len(nxt_item.group(1)) == item_indent:
                    break
                if workspace_id is None:
                    nested = _ID_NESTED.match(nxt)
                    if nested:
                        workspace_id = _unquote(nested.group(2))
                index += 1
            if workspace_id:
                items.append((workspace_id, item_start, index))
            continue
        index += 1
    return (item_indent if item_indent is not None else 2), items


def _id_from_rest(rest: str) -> str | None:
    match = _ID_INLINE.match(rest.strip())
    if not match:
        return None
    return _unquote(match.group(1))


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value

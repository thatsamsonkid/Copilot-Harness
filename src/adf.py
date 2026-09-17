from __future__ import annotations

from typing import Any


def adf_to_markdown(node: Any) -> str:
    """Convert Jira Cloud Atlassian Document Format to compact Markdown."""
    return _render(node).strip()


def _render(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_render(item) for item in node)
    if not isinstance(node, dict):
        return str(node)

    node_type = node.get("type")
    content = node.get("content") or []
    attrs = node.get("attrs") or {}

    if node_type in {None, "doc"}:
        return _join_blocks(content)
    if node_type == "paragraph":
        return _render_inline(content) + "\n\n"
    if node_type == "heading":
        level = max(1, min(int(attrs.get("level") or 1), 6))
        return f"{'#' * level} {_render_inline(content)}\n\n"
    if node_type == "bulletList":
        return _render_list(content, ordered=False)
    if node_type == "orderedList":
        return _render_list(content, ordered=True, start=int(attrs.get("order") or 1))
    if node_type == "listItem":
        return _render_list_item_body(content)
    if node_type == "codeBlock":
        language = attrs.get("language") or ""
        code = _plain_text(content).rstrip("\n")
        return f"```{language}\n{code}\n```\n\n"
    if node_type == "blockquote":
        inner = _join_blocks(content).strip().splitlines()
        quoted = "\n".join(f"> {line}" if line else ">" for line in inner)
        return quoted + "\n\n"
    if node_type == "rule":
        return "---\n\n"
    if node_type == "panel":
        panel = attrs.get("panelType") or "info"
        body = _join_blocks(content).strip()
        return f"> **{panel}**\n>\n" + "\n".join(
            f"> {line}" if line else ">" for line in body.splitlines()
        ) + "\n\n"
    if node_type == "table":
        return _render_table(content)
    if node_type == "mediaSingle":
        return _render(content)
    if node_type == "media":
        alt = attrs.get("alt") or attrs.get("id") or "attachment"
        return f"[attachment: {alt}]\n\n"
    if node_type == "expand":
        title = attrs.get("title") or "Details"
        return f"**{title}**\n\n{_join_blocks(content)}"
    if node_type == "hardBreak":
        return "\n"
    if node_type == "text":
        return _apply_marks(node.get("text") or "", node.get("marks") or [])
    if node_type == "mention":
        return f"@{attrs.get('text') or attrs.get('id') or 'user'}"
    if node_type == "emoji":
        return str(attrs.get("shortName") or attrs.get("text") or "")
    if node_type == "inlineCard":
        return attrs.get("url") or ""
    if node_type == "status":
        return f"[{attrs.get('text') or 'status'}]"
    if node_type == "date":
        return str(attrs.get("timestamp") or "")
    if node_type == "placeholder":
        return ""
    return _join_blocks(content) or _render_inline(content)


def _join_blocks(content: list[Any]) -> str:
    return "".join(_render(child) for child in content)


def _render_inline(content: list[Any]) -> str:
    parts: list[str] = []
    for child in content:
        rendered = _render(child)
        # Preserve hardBreak newlines; only strip trailing block separators that
        # a (malformed) nested block child might contribute.
        if isinstance(child, dict) and child.get("type") == "hardBreak":
            parts.append(rendered)
        else:
            parts.append(rendered.rstrip("\n"))
    return "".join(parts)


def _plain_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_plain_text(item) for item in node)
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text") or ""
        if node.get("type") == "hardBreak":
            return "\n"
        return _plain_text(node.get("content"))
    return ""


def _apply_marks(text: str, marks: list[Any]) -> str:
    href = None
    kinds = set()
    for mark in marks:
        if not isinstance(mark, dict):
            continue
        kinds.add(mark.get("type"))
        if mark.get("type") == "link":
            href = (mark.get("attrs") or {}).get("href")
    if "code" in kinds:
        text = f"`{text}`"
    if "strong" in kinds:
        text = f"**{text}**"
    if "em" in kinds:
        text = f"*{text}*"
    if "strike" in kinds:
        text = f"~~{text}~~"
    if href:
        text = f"[{text}]({href})"
    return text


def _render_list(items: list[Any], *, ordered: bool, start: int = 1) -> str:
    lines: list[str] = []
    index = start
    for item in items:
        body = _render(item).strip("\n")
        if not body:
            continue
        chunks = body.split("\n")
        marker = f"{index}. " if ordered else "- "
        lines.append(f"{marker}{chunks[0]}")
        indent = " " * len(marker)
        for extra in chunks[1:]:
            lines.append(f"{indent}{extra}" if extra else "")
        index += 1
    return "\n".join(lines) + ("\n\n" if lines else "")


def _render_list_item_body(content: list[Any]) -> str:
    blocks: list[str] = []
    for child in content:
        rendered = _render(child).strip("\n")
        if rendered:
            blocks.append(rendered)
    return "\n".join(blocks) + "\n"


def _render_table(rows: list[Any]) -> str:
    parsed: list[list[str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cells = []
        for cell in row.get("content") or []:
            if not isinstance(cell, dict):
                continue
            cells.append(_plain_text(cell).replace("\n", " ").strip())
        if cells:
            parsed.append(cells)
    if not parsed:
        return ""
    width = max(len(row) for row in parsed)
    for row in parsed:
        row.extend([""] * (width - len(row)))
    header = parsed[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in parsed[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n\n"

from __future__ import annotations

import re
from typing import Any

ACCEPTANCE_FIELD_KEYS = (
    "acceptance_criteria",
    "acceptance",
    "ac",
    "definition_of_done",
)

ACCEPTANCE_HEADING_RE = re.compile(
    r"^(#{1,6}\s*)?(acceptance criteria|definition of done|done when|ac)\s*:?\s*$",
    re.IGNORECASE,
)
CHECKBOX_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[ xX]\]\s+(.*\S)\s*$")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")
NEXT_HEADING_RE = re.compile(r"^#{1,6}\s+\S")

HARNESS_INVARIANTS = (
    "Keep the Jira key in each sibling branch name.",
    "Open one pull request per sibling repo. Do not squash unrelated repos.",
    "Do not commit .env or print secrets.",
    "Run each touched repo's tooling.suggested_verify and fix or report failures.",
    "If the change is user-visible or non-obvious, update docs/features (or an ADR) in that sibling.",
)


def build_done_when(
    issue: dict[str, Any] | None,
    repos: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for text in extract_acceptance(issue or {}):
        _append(items, seen, source="ticket", text=text)
    for repo in repos or []:
        repo_id = repo.get("id") or repo.get("name")
        for command in (repo.get("tooling") or {}).get("suggested_verify") or []:
            _append(
                items,
                seen,
                source="verify",
                text=f"In {repo_id}: {command}",
                repo=str(repo_id) if repo_id else None,
            )
    for text in HARNESS_INVARIANTS:
        _append(items, seen, source="harness", text=text)
    return items


def extract_acceptance(issue: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for key in ACCEPTANCE_FIELD_KEYS:
        found.extend(_values_from_field(issue.get(key)))
    found.extend(_from_description(issue.get("description") or ""))
    return _dedupe(found)


def _values_from_field(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            texts.extend(_values_from_field(item))
        return texts
    if isinstance(value, dict):
        for key in ("value", "text", "content"):
            if key in value:
                return _values_from_field(value[key])
        return []
    text = str(value).strip()
    if not text:
        return []
    parsed = _from_description(text)
    return parsed or [text]


def _from_description(description: str) -> list[str]:
    if not description.strip():
        return []
    lines = description.replace("\r\n", "\n").splitlines()
    found: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if ACCEPTANCE_HEADING_RE.match(stripped):
            in_section = True
            continue
        if in_section and NEXT_HEADING_RE.match(stripped):
            in_section = False
        checkbox = CHECKBOX_RE.match(line)
        if checkbox:
            found.append(checkbox.group(1).strip())
            continue
        if in_section:
            bullet = BULLET_RE.match(line)
            if bullet:
                found.append(bullet.group(1).strip())
            elif stripped:
                found.append(stripped)
    return found


def _append(
    items: list[dict[str, Any]],
    seen: set[str],
    *,
    source: str,
    text: str,
    repo: str | None = None,
) -> None:
    key = text.strip().lower()
    if not key or key in seen:
        return
    seen.add(key)
    item: dict[str, Any] = {"source": source, "text": text.strip()}
    if repo:
        item["repo"] = repo
    items.append(item)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value.strip())
    return result

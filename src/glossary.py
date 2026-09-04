from __future__ import annotations

import json
import re
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Mapping

import yaml

from goat import GoatError
from goat.catalog import Catalog, as_list, read_yaml
from goat.paths import GLOSSARY_LOCAL_RELATIVE, GLOSSARY_RELATIVE
from goat.prompt import PromptSession
from goat.workspace_detect import resolve_workspace_scope, scoped_repos

SIBLING_GLOSSARY_PATHS = (
    Path("docs") / "glossary.yml",
    Path("glossary.yml"),
)
KINDS = ("acronym", "term")
VISIBILITY_PUBLIC = "public"
VISIBILITY_PRIVATE = "private"
VISIBILITIES = (VISIBILITY_PUBLIC, VISIBILITY_PRIVATE)
SOURCE_GOAT = "goat"
SOURCE_PERSONAL = "personal"
SUGGESTION_LIMIT = 5
ACRONYM_RE = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")
_LIST_ITEM = re.compile(r"^([ \t]*)- (.*)$")
_TERM_INLINE = re.compile(r"^term:\s*(.+?)\s*$")
_TERM_NESTED = re.compile(r"^([ \t]+)term:\s*(.+?)\s*$")
_TOP_LEVEL_KEY = re.compile(r"^[A-Za-z_][\w-]*\s*:")
_TERMS_KEY = re.compile(r"^terms\s*:(.*)$")

GLOSSARY_HEADER = """# Workplace vocabulary — how people talk here, not how the product works.
# Short definitions only. Product feature notes and ADRs still live in sibling
# repos (docs/features, docs/adr). See docs/knowledge.md.
#
# Org-wide public terms belong in this file (committed). Personal nicknames
# go in catalog/glossary.local.yml (gitignored). Product-specific acronyms
# can live in a sibling docs/glossary.yml. `goat glossary` merges all three.
#
# Add a term (always say public or private):
#   uv run goat glossary add SOW --meaning "Statement of Work" --visibility public
# Look one up:
#   uv run goat glossary get SOW --format json

terms:
"""

PERSONAL_HEADER = """# Personal workplace vocabulary — gitignored, not shared with the team.
# Lookups merge this file with catalog/glossary.yml. Do not commit it.
#
# Add a private term:
#   uv run goat glossary add NICK --meaning "My shorthand" --visibility private

terms:
"""


def collect_glossary(
    catalog: Catalog,
    goat_root: Path,
    *,
    query: str | None = None,
    action: str = "list",
    kind: str | None = None,
    visibility: str | None = None,
    only: list[str] | None = None,
    workspace_id: str | None = None,
    all_repos: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    files, terms = _load_terms(
        catalog,
        goat_root,
        only=only,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    if kind:
        terms = [item for item in terms if item["kind"] == kind]
    if visibility:
        wanted = _normalize_visibility(visibility)
        terms = [item for item in terms if item["visibility"] == wanted]
    matched = True
    suggestions: list[dict[str, Any]] = []
    if action == "get":
        needle = _normalize(query or "")
        if not needle:
            raise GoatError("Pass a term to look up: goat glossary get TERM")
        hits = [item for item in terms if needle in _names(item)]
        if hits:
            terms = hits
        else:
            matched = False
            suggestions = _suggest(query or "", terms)
            terms = []
    elif action == "search":
        needle = _normalize(query or "")
        if not needle:
            raise GoatError("Pass a query: goat glossary search QUERY")
        terms = [item for item in terms if _matches_search(item, needle)]
        matched = bool(terms)
        if not terms:
            suggestions = _suggest(query or "", _load_all_terms_unfiltered(files))
    terms = _sort_terms(terms)
    guidance = _guidance(action, query, matched, terms)
    return {
        "kind": "glossary",
        "action": action,
        "query": query,
        "matched": matched,
        "count": len(terms),
        "terms": terms,
        "suggestions": suggestions,
        "files": files,
        "guidance": guidance,
    }


def glossary_summary(
    catalog: Catalog,
    goat_root: Path,
    *,
    only: list[str] | None = None,
    workspace_id: str | None = None,
    all_repos: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    payload = collect_glossary(
        catalog,
        goat_root,
        action="list",
        only=only,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    goat_file = goat_root / GLOSSARY_RELATIVE
    personal_file = goat_root / GLOSSARY_LOCAL_RELATIVE
    return {
        "file": str(goat_file) if goat_file.is_file() else None,
        "relative": str(GLOSSARY_RELATIVE),
        "personal_file": str(personal_file) if personal_file.is_file() else None,
        "personal_relative": str(GLOSSARY_LOCAL_RELATIVE),
        "count": payload["count"],
        "sources": len(payload["files"]),
        "command": "uv run goat glossary list --format json",
        "get_command": "uv run goat glossary get TERM --format json",
        "detail": (
            "Workplace terms and acronyms for Copilot. "
            "Look up unknown language with goat glossary get. "
            "Public terms are committed; private terms stay in "
            "catalog/glossary.local.yml (gitignored). "
            "Do not treat this as product architecture."
        ),
    }


def add_term(
    catalog: Catalog,
    goat_root: Path,
    term: str,
    *,
    meaning: str | None = None,
    also: list[str] | None = None,
    kind: str | None = None,
    see: list[str] | None = None,
    repo: str | None = None,
    visibility: str | None = None,
    replace: bool = False,
    dry_run: bool = False,
    prompt: PromptSession | None = None,
) -> dict[str, Any]:
    label = term.strip()
    if not label:
        raise GoatError("Pass a term to add: goat glossary add TERM --meaning \"...\"")
    session = prompt or PromptSession()
    definition = (meaning or "").strip()
    if not definition:
        if session.can_prompt():
            definition = session.ask("Meaning (one or two sentences)").strip()
        if not definition:
            raise GoatError(
                "Pass --meaning \"...\" (or run add in a local terminal to be prompted)"
            )
    resolved_visibility = _resolve_visibility(visibility, session)
    aliases = _unique_names(also or [], skip={label})
    related = _unique_names(see or [], skip={label, *aliases})
    resolved_kind = kind or _guess_kind(label)
    if resolved_kind not in KINDS:
        raise GoatError(f"kind must be one of {', '.join(KINDS)}")
    path, source = _write_path(
        catalog, goat_root, repo, visibility=resolved_visibility
    )
    existing = _parse_file(path, source, visibility=resolved_visibility)
    conflict = _find_conflict(existing, label, aliases)
    if conflict and not replace:
        existing_names = [conflict["term"], *list(conflict.get("also") or [])]
        names = " / ".join(existing_names)
        raise GoatError(
            f"{label!r} already exists as {names!r} in {path}. "
            "Pass --replace to update it."
        )
    keep_aliases = bool(conflict and replace and not also)
    keep_related = bool(conflict and replace and not see)
    record = {
        "term": conflict["term"] if conflict and replace else label,
        "also": list(conflict.get("also") or []) if keep_aliases else aliases,
        "kind": resolved_kind,
        "meaning": definition,
        "see": list(conflict.get("see") or []) if keep_related else related,
        "source": source,
        "visibility": resolved_visibility,
        "file": str(path),
    }
    created = not path.is_file()
    if not dry_run:
        _write_term(
            path,
            record,
            replace=replace,
            header=PERSONAL_HEADER if resolved_visibility == VISIBILITY_PRIVATE else GLOSSARY_HEADER,
        )
    payload = collect_glossary(
        catalog,
        goat_root,
        query=record["term"],
        action="get",
        all_repos=True,
    )
    written = next(
        (
            item
            for item in payload["terms"]
            if item["source"] == source and _normalize(item["term"]) == _normalize(record["term"])
        ),
        record,
    )
    return {
        "kind": "glossary",
        "action": "add",
        "query": record["term"],
        "matched": True,
        "count": 1,
        "terms": [written],
        "suggestions": [],
        "files": payload["files"],
        "file": str(path),
        "relative": _relative_to_goat(path, goat_root),
        "source": source,
        "visibility": resolved_visibility,
        "created": created,
        "replaced": bool(conflict),
        "dry_run": dry_run,
        "guidance": _add_guidance(resolved_visibility),
    }


def _load_terms(
    catalog: Catalog,
    goat_root: Path,
    *,
    only: list[str] | None,
    workspace_id: str | None,
    all_repos: bool,
    environ: Mapping[str, str] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    files: list[dict[str, Any]] = []
    terms: list[dict[str, Any]] = []
    goat_path = goat_root / GLOSSARY_RELATIVE
    goat_terms = _parse_file(goat_path, SOURCE_GOAT, visibility=VISIBILITY_PUBLIC)
    files.append(
        _file_payload(
            goat_path,
            SOURCE_GOAT,
            goat_terms,
            present=goat_path.is_file(),
            visibility=VISIBILITY_PUBLIC,
        )
    )
    terms.extend(goat_terms)
    personal_path = goat_root / GLOSSARY_LOCAL_RELATIVE
    personal_terms = _parse_file(
        personal_path, SOURCE_PERSONAL, visibility=VISIBILITY_PRIVATE
    )
    files.append(
        _file_payload(
            personal_path,
            SOURCE_PERSONAL,
            personal_terms,
            present=personal_path.is_file(),
            visibility=VISIBILITY_PRIVATE,
        )
    )
    terms.extend(personal_terms)
    scope = resolve_workspace_scope(
        catalog,
        goat_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    for repo in scoped_repos(catalog, scope, only=only):
        repo_path = catalog.repo_path(goat_root, repo)
        if not repo_path.is_dir():
            continue
        found = _sibling_glossary_path(repo_path)
        if found is None:
            continue
        sibling_terms = _parse_file(found, repo.name, visibility=VISIBILITY_PUBLIC)
        files.append(
            _file_payload(
                found,
                repo.name,
                sibling_terms,
                present=True,
                visibility=VISIBILITY_PUBLIC,
            )
        )
        terms.extend(sibling_terms)
    return files, terms


def _load_all_terms_unfiltered(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for item in files:
        path = Path(item["path"])
        if path.is_file():
            loaded.extend(
                _parse_file(
                    path,
                    item["source"],
                    visibility=str(item.get("visibility") or VISIBILITY_PUBLIC),
                )
            )
    return loaded


def _parse_file(
    path: Path, source: str, *, visibility: str = VISIBILITY_PUBLIC
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    raw = read_yaml(path)
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise GoatError(f"Glossary {path} must be a mapping with a terms list")
    items = raw.get("terms")
    if items is None:
        return []
    if not isinstance(items, list):
        raise GoatError(f"Glossary {path} terms must be a list")
    parsed: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise GoatError(f"Glossary {path} terms[{index}] must be a mapping")
        label = str(item.get("term") or "").strip()
        if not label:
            raise GoatError(f"Glossary {path} terms[{index}] is missing term")
        meaning = str(item.get("meaning") or "").strip()
        kind = str(item.get("kind") or _guess_kind(label)).strip()
        if kind not in KINDS:
            raise GoatError(
                f"Glossary {path} term {label!r} has unknown kind {kind!r}"
            )
        parsed.append(
            {
                "term": label,
                "also": _unique_names(as_list(item.get("also")), skip={label}),
                "kind": kind,
                "meaning": meaning,
                "see": _unique_names(as_list(item.get("see")), skip={label}),
                "source": source,
                "visibility": visibility,
                "file": str(path),
            }
        )
    return parsed


def _sibling_glossary_path(repo_path: Path) -> Path | None:
    for relative in SIBLING_GLOSSARY_PATHS:
        path = repo_path / relative
        if path.is_file():
            return path
    return None


def _write_path(
    catalog: Catalog,
    goat_root: Path,
    repo: str | None,
    *,
    visibility: str,
) -> tuple[Path, str]:
    if visibility == VISIBILITY_PRIVATE:
        if repo:
            raise GoatError(
                "Private terms stay in catalog/glossary.local.yml. "
                "Do not pass --repo with --visibility private."
            )
        return goat_root / GLOSSARY_LOCAL_RELATIVE, SOURCE_PERSONAL
    if not repo:
        return goat_root / GLOSSARY_RELATIVE, SOURCE_GOAT
    entry = catalog.repo(repo)
    path = catalog.repo_path(goat_root, entry)
    if not path.is_dir():
        raise GoatError(
            f"Repository {entry.name} is not cloned at {path}. "
            "Clone it before adding a product glossary."
        )
    existing = _sibling_glossary_path(path)
    if existing is not None:
        return existing, entry.name
    return path / SIBLING_GLOSSARY_PATHS[0], entry.name


def _find_conflict(
    existing: list[dict[str, Any]], term: str, aliases: list[str]
) -> dict[str, Any] | None:
    needles = {_normalize(term), *(_normalize(alias) for alias in aliases)}
    for item in existing:
        names = _names(item)
        if needles & names:
            return item
    return None


def _write_term(
    path: Path,
    record: dict[str, Any],
    *,
    replace: bool,
    header: str = GLOSSARY_HEADER,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = _format_term_yaml(record)
    if not path.exists():
        path.write_text(header + entry, encoding="utf-8")
        return
    original = path.read_text(encoding="utf-8")
    try:
        updated = _upsert_term_text(
            original, record, entry, replace=replace, header=header
        )
        path.write_text(updated, encoding="utf-8")
        written = _parse_file(
            path,
            record["source"],
            visibility=str(record.get("visibility") or VISIBILITY_PUBLIC),
        )
        if not any(_normalize(item["term"]) == _normalize(record["term"]) for item in written):
            raise GoatError(f"Failed to persist glossary term {record['term']!r}")
    except Exception:
        path.write_text(original, encoding="utf-8")
        raise


def _upsert_term_text(
    text: str,
    record: dict[str, Any],
    entry: str,
    *,
    replace: bool,
    header: str = GLOSSARY_HEADER,
) -> str:
    if not text.strip():
        return header + entry
    if not text.endswith("\n"):
        text += "\n"
    lines = text.splitlines(keepends=True)
    span = _terms_section(lines)
    if span is None:
        if not text.endswith("\n\n"):
            text += "\n"
        return text + "terms:\n" + entry
    start, end = span
    header = lines[start]
    match = _TERMS_KEY.match(header.rstrip("\n"))
    inline = (match.group(1) or "").strip() if match else ""
    item_indent, items = _term_items(lines, start, end)
    needle = _normalize(record["term"])
    existing = next(
        (item for item in items if _normalize(item[0]) == needle),
        None,
    )
    formatted = _indent_entry(entry, item_indent if items else 2)
    new_lines = list(lines)
    if existing:
        if not replace:
            raise GoatError(f"Term {record['term']!r} already exists")
        item_start, item_end = existing[1], existing[2]
        new_lines[item_start:item_end] = [formatted]
    elif inline in {"", "|", ">"} or inline == "[]":
        header_line = "terms:\n" if inline == "[]" else header
        body = list(lines[start + 1 : end])
        if body and items and body[-1].strip():
            body.append("\n")
        new_lines[start:end] = [header_line, *body, formatted]
    else:
        raw = yaml.safe_load(text) or {}
        others = [
            item
            for item in (raw.get("terms") or [])
            if isinstance(item, dict)
            and _normalize(str(item.get("term") or "")) != needle
        ]
        rebuilt = ["terms:\n"]
        for item in others:
            rebuilt.append(
                _indent_entry(
                    _format_term_yaml(
                        {
                            "term": str(item.get("term") or ""),
                            "also": as_list(item.get("also")),
                            "kind": str(item.get("kind") or _guess_kind(str(item.get("term") or ""))),
                            "meaning": str(item.get("meaning") or ""),
                            "see": as_list(item.get("see")),
                        }
                    ),
                    2,
                )
            )
        rebuilt.append(formatted)
        new_lines[start:end] = rebuilt
    result = "".join(new_lines)
    if not result.endswith("\n"):
        result += "\n"
    return result


def _format_term_yaml(record: Mapping[str, Any]) -> str:
    lines = [f"  - term: {_yaml_scalar(str(record['term']))}"]
    also = [str(item) for item in (record.get("also") or []) if str(item).strip()]
    if also:
        lines.append(f"    also: [{', '.join(_yaml_scalar(item) for item in also)}]")
    kind = str(record.get("kind") or _guess_kind(str(record["term"])))
    lines.append(f"    kind: {kind}")
    meaning = str(record.get("meaning") or "").strip()
    if meaning:
        lines.append(f"    meaning: {_yaml_scalar(meaning)}")
    see = [str(item) for item in (record.get("see") or []) if str(item).strip()]
    if see:
        lines.append(f"    see: [{', '.join(_yaml_scalar(item) for item in see)}]")
    return "\n".join(lines) + "\n"


def _terms_section(lines: list[str]) -> tuple[int, int] | None:
    start = None
    for index, line in enumerate(lines):
        if _TERMS_KEY.match(line.rstrip("\n")):
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


def _term_items(
    lines: list[str], start: int, end: int
) -> tuple[int, list[tuple[str, int, int]]]:
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
            term = _term_from_rest(rest)
            index += 1
            while index < end:
                nxt = lines[index].rstrip("\n")
                nxt_item = _LIST_ITEM.match(nxt)
                if nxt_item and len(nxt_item.group(1)) == item_indent:
                    break
                if term is None:
                    nested = _TERM_NESTED.match(nxt)
                    if nested:
                        term = _unquote(nested.group(2))
                index += 1
            if term:
                items.append((term, item_start, index))
            continue
        index += 1
    return (item_indent if item_indent is not None else 2), items


def _term_from_rest(rest: str) -> str | None:
    match = _TERM_INLINE.match(rest.strip())
    if not match:
        return None
    return _unquote(match.group(1))


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _indent_entry(entry: str, item_indent: int) -> str:
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
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return "".join(lines)


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


def _file_payload(
    path: Path,
    source: str,
    terms: list[dict[str, Any]],
    *,
    present: bool,
    visibility: str,
) -> dict[str, Any]:
    return {
        "source": source,
        "path": str(path),
        "present": present,
        "count": len(terms),
        "visibility": visibility,
    }


def _guidance(
    action: str,
    query: str | None,
    matched: bool,
    terms: list[dict[str, Any]],
) -> list[str]:
    lines = [
        "Use these definitions when prompting. Do not invent workplace language.",
        "This is vocabulary, not product architecture. Feature notes stay in sibling docs/features.",
    ]
    if action == "get" and not matched:
        lines.insert(
            0,
            f"No glossary match for {query!r}. "
            f"Add it with goat glossary add {query} --meaning \"...\" "
            "or search with goat glossary search.",
        )
    elif action == "search" and not matched:
        lines.insert(0, f"No glossary hits for {query!r}.")
    elif action == "list" and not terms:
        lines.insert(
            0,
            "Glossary is empty. Add the first term with goat glossary add TERM "
            "--meaning \"...\" --visibility public|private.",
        )
    return lines


def _add_guidance(visibility: str) -> list[str]:
    if visibility == VISIBILITY_PRIVATE:
        return [
            "This term is personal and gitignored (catalog/glossary.local.yml). "
            "It will not be committed.",
            "Copilot should look terms up with goat glossary get, not guess.",
        ]
    return [
        "Commit catalog/glossary.yml if the term should be shared with the team.",
        "Copilot should look terms up with goat glossary get, not guess.",
    ]


def _suggest(query: str, terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels: list[str] = []
    by_label: dict[str, dict[str, Any]] = {}
    for item in terms:
        for name in [item["term"], *list(item.get("also") or [])]:
            labels.append(name)
            by_label.setdefault(name, item)
    hits = get_close_matches(query, labels, n=SUGGESTION_LIMIT, cutoff=0.5)
    seen: set[str] = set()
    suggestions: list[dict[str, Any]] = []
    for name in hits:
        item = by_label[name]
        key = f"{item['source']}:{item['term']}"
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(
            {
                "term": item["term"],
                "kind": item["kind"],
                "source": item["source"],
                "visibility": item.get("visibility"),
                "meaning": item["meaning"],
            }
        )
    return suggestions


def _matches_search(item: dict[str, Any], needle: str) -> bool:
    haystacks = [
        item["term"],
        item.get("meaning") or "",
        item.get("kind") or "",
        " ".join(item.get("also") or []),
        " ".join(item.get("see") or []),
    ]
    return any(needle in _normalize(value) for value in haystacks)


def _names(item: Mapping[str, Any]) -> set[str]:
    return {_normalize(item["term"]), *(_normalize(alias) for alias in item.get("also") or [])}


def _normalize(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.casefold())
    return " ".join(cleaned.split())


def _guess_kind(term: str) -> str:
    compact = term.replace(" ", "")
    if ACRONYM_RE.match(compact):
        return "acronym"
    return "term"


def _unique_names(values: list[str], *, skip: set[str]) -> list[str]:
    seen = {_normalize(item) for item in skip if item}
    names: list[str] = []
    for value in values:
        label = value.strip()
        key = _normalize(label)
        if not label or key in seen:
            continue
        seen.add(key)
        names.append(label)
    return names


def _sort_terms(terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        terms,
        key=lambda item: (
            item["term"].casefold(),
            0 if item.get("visibility") == VISIBILITY_PUBLIC else 1,
            item["source"],
        ),
    )


def _resolve_visibility(value: str | None, session: PromptSession) -> str:
    if value:
        return _normalize_visibility(value)
    if session.can_prompt():
        answer = session.ask(
            "Public (team catalog, committed) or private (personal, gitignored)",
            default=VISIBILITY_PUBLIC,
        )
        return _normalize_visibility(answer)
    raise GoatError(
        "Say whether the term is public or private: "
        "goat glossary add TERM --meaning \"...\" --visibility public|private"
    )


def _normalize_visibility(value: str) -> str:
    needle = value.strip().casefold()
    aliases = {
        "public": VISIBILITY_PUBLIC,
        "shared": VISIBILITY_PUBLIC,
        "team": VISIBILITY_PUBLIC,
        "private": VISIBILITY_PRIVATE,
        "personal": VISIBILITY_PRIVATE,
        "local": VISIBILITY_PRIVATE,
    }
    resolved = aliases.get(needle)
    if resolved is None:
        raise GoatError(
            f"visibility must be public or private, not {value!r}"
        )
    return resolved


def _relative_to_goat(path: Path, goat_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(goat_root.resolve()))
    except ValueError:
        return str(path)

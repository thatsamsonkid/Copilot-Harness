from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from goat import GoatError
from goat.catalog import as_list, read_yaml
from goat.graph.models import Candidate, Evidence, ExtractBatch, make_node
from goat.graph.schema import (
    COMPONENT_RELATIVE,
    DEFAULT_CONFIDENCE,
    LOCAL_OVERRIDES_RELATIVE,
    OVERRIDES_RELATIVE,
    canonical_classification,
    canonical_relationship,
    parse_ref,
)


def load_component_manifest(path: Path) -> dict[str, Any]:
    raw = read_yaml(path)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise GoatError(f"{path} must be a mapping")
    return raw


def load_overrides(goat_root: Path) -> dict[str, list[dict[str, Any]]]:
    declare: list[dict[str, Any]] = []
    reject: list[dict[str, Any]] = []
    for relative in (OVERRIDES_RELATIVE, LOCAL_OVERRIDES_RELATIVE):
        path = goat_root / relative
        if not path.is_file():
            continue
        raw = read_yaml(path)
        if raw is None:
            continue
        if not isinstance(raw, dict):
            raise GoatError(f"{path} must be a mapping with declare:/reject:")
        declare.extend(_as_override_rows(raw.get("declare"), path, "declare"))
        reject.extend(_as_override_rows(raw.get("reject"), path, "reject"))
    return {"declare": declare, "reject": reject}


def component_batch(
    repo_name: str, repo_id: str, path: Path, raw: dict[str, Any]
) -> ExtractBatch:
    component_id = str(raw.get("id") or repo_name)
    node_type = str(raw.get("type") or "service")
    name = str(raw.get("name") or component_id)
    primary = make_node(
        node_type,
        name,
        repository=repo_id,
        node=parse_ref(component_id, default_type=node_type)
        if ":" in str(component_id)
        else None,
    )
    if ":" not in str(component_id):
        primary = make_node(node_type, component_id, repository=repo_id)
        primary.name = name
    nodes = [primary]
    candidates: list[Candidate] = []
    evidence = Evidence(
        type="manifest",
        extractor="component",
        repository=repo_name,
        file=str(COMPONENT_RELATIVE),
        value=component_id,
    )
    files = [str(path)]

    if raw.get("domain"):
        domain = make_node("domain", str(raw["domain"]))
        nodes.append(domain)
        candidates.append(
            _declared(
                primary.id,
                "MEMBER_OF",
                domain.id,
                evidence,
                f"domain {raw['domain']}",
            )
        )

    for ref in _ref_list(raw.get("provides"), "api"):
        node = make_node("api", ref.split(":", 1)[-1], repository=repo_id, node=ref)
        nodes.append(node)
        candidates.append(_declared(primary.id, "PROVIDES", ref, evidence, "provides"))
    for ref in _ref_list(raw.get("consumes"), "api"):
        node = _target_node(ref)
        nodes.append(node)
        rel = "CONSUMES"
        candidates.append(_declared(primary.id, rel, ref, evidence, "consumes"))
    for ref in _ref_list(raw.get("resources"), "database"):
        node = _target_node(ref)
        nodes.append(node)
        candidates.append(_declared(primary.id, "USES", ref, evidence, "resources"))
    for ref in _ref_list(raw.get("publishes"), "event"):
        node = _target_node(ref)
        nodes.append(node)
        candidates.append(_declared(primary.id, "PUBLISHES", ref, evidence, "publishes"))
    for ref in _ref_list(raw.get("subscribes") or raw.get("listens"), "event"):
        node = _target_node(ref)
        nodes.append(node)
        candidates.append(
            _declared(primary.id, "SUBSCRIBES", ref, evidence, "subscribes")
        )
    return ExtractBatch(nodes=nodes, candidates=candidates, files=files)


def overrides_batch(rows: dict[str, list[dict[str, Any]]]) -> ExtractBatch:
    nodes = []
    candidates = []
    for row in rows.get("declare") or []:
        source = parse_ref(row["source"])
        target = parse_ref(row["target"])
        rel = canonical_relationship(row["relationship"])
        nodes.extend([_target_node(source), _target_node(target)])
        candidates.append(
            Candidate(
                source=source,
                target=target,
                relationship=rel,
                classification="DECLARED",
                confidence=DEFAULT_CONFIDENCE["DECLARED"],
                evidence=[
                    Evidence(
                        type="override",
                        extractor="overrides",
                        file=str(OVERRIDES_RELATIVE),
                        value=row.get("note") or rel,
                    )
                ],
                note=row.get("note"),
            )
        )
    for row in rows.get("reject") or []:
        source = parse_ref(row["source"])
        target = parse_ref(row["target"])
        rel = canonical_relationship(row["relationship"])
        nodes.extend([_target_node(source), _target_node(target)])
        candidates.append(
            Candidate(
                source=source,
                target=target,
                relationship=rel,
                classification="REJECTED",
                confidence=DEFAULT_CONFIDENCE["REJECTED"],
                evidence=[
                    Evidence(
                        type="override",
                        extractor="overrides",
                        file=str(OVERRIDES_RELATIVE),
                        value=row.get("note") or "rejected",
                    )
                ],
                note=row.get("note") or "explicitly rejected",
            )
        )
    return ExtractBatch(nodes=nodes, candidates=candidates)


def dump_example_component() -> str:
    return (
        "# Architectural intent this repo cannot express in code.\n"
        "# Do not duplicate extractable facts (package deps, OpenAPI paths).\n"
        "id: booking-service\n"
        "type: service\n"
        "provides:\n"
        "  - api:booking-v2\n"
        "resources:\n"
        "  - database:booking-db\n"
        "publishes:\n"
        "  - event:booking.updated\n"
    )


def _declared(
    source: str, relationship: str, target: str, evidence: Evidence, note: str
) -> Candidate:
    return Candidate(
        source=source,
        target=target,
        relationship=relationship,
        classification="DECLARED",
        confidence=DEFAULT_CONFIDENCE["DECLARED"],
        evidence=[evidence],
        note=note,
    )


def _target_node(ref: str):
    kind, _, name = ref.partition(":")
    return make_node(kind, name, node=ref)


def _ref_list(raw: Any, default_type: str) -> list[str]:
    refs: list[str] = []
    for item in as_list(raw) if not isinstance(raw, list) else raw:
        if isinstance(item, dict):
            ident = item.get("id") or item.get("ref") or item.get("name")
            kind = item.get("type") or default_type
            if ident:
                refs.append(parse_ref(str(ident), default_type=str(kind)))
            continue
        refs.append(parse_ref(str(item), default_type=default_type))
    return refs


def _as_override_rows(raw: Any, path: Path, label: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise GoatError(f"{path} {label}: must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise GoatError(f"{path} {label}: each entry must be a mapping")
        missing = [key for key in ("source", "target", "relationship") if not item.get(key)]
        if missing:
            raise GoatError(
                f"{path} {label}: missing {', '.join(missing)}"
            )
        canonical_relationship(str(item["relationship"]))
        if item.get("classification"):
            canonical_classification(str(item["classification"]))
        rows.append(item)
    return rows


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

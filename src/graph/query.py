from __future__ import annotations

from collections import deque
from typing import Any

from goat import GoatError
from goat.graph.schema import parse_ref


def explain(graph: dict[str, Any], left: str, right: str | None = None) -> dict[str, Any]:
    source = _resolve(graph, left)
    target = _resolve(graph, right) if right else None
    edges = []
    for edge in graph.get("edges") or []:
        if target is None:
            if edge.get("source") == source or edge.get("target") == source:
                edges.append(edge)
            continue
        if {edge.get("source"), edge.get("target")} == {source, target}:
            edges.append(edge)
    if not edges:
        raise GoatError(
            f"No edges for {source}" + (f" ↔ {target}" if target else "") + "."
        )
    return {
        "kind": "workspace_graph_explain",
        "source": source,
        "target": target,
        "edges": edges,
        "summary": [_summary(graph, edge) for edge in edges],
    }


def neighbors(graph: dict[str, Any], node: str) -> dict[str, Any]:
    ident = _resolve(graph, node)
    inbound: list[dict[str, Any]] = []
    outbound: list[dict[str, Any]] = []
    for edge in graph.get("edges") or []:
        if edge.get("source") == ident:
            outbound.append(edge)
        if edge.get("target") == ident:
            inbound.append(edge)
    return {
        "kind": "workspace_graph_neighbors",
        "node": ident,
        "inbound": inbound,
        "outbound": outbound,
    }


def path_between(graph: dict[str, Any], start: str, finish: str) -> dict[str, Any]:
    source = _resolve(graph, start)
    target = _resolve(graph, finish)
    adj: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.get("edges") or []:
        if edge.get("classification") == "REJECTED":
            continue
        adj.setdefault(str(edge["source"]), []).append(edge)
    queue = deque([(source, [])])
    seen = {source}
    while queue:
        current, trail = queue.popleft()
        if current == target:
            return {
                "kind": "workspace_graph_path",
                "from": source,
                "to": target,
                "edges": trail,
                "nodes": [source, *[item["target"] for item in trail]],
            }
        for edge in adj.get(current) or []:
            nxt = str(edge["target"])
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append((nxt, [*trail, edge]))
    raise GoatError(f"No directed path from {source} to {target}.")


def _resolve(graph: dict[str, Any], value: str) -> str:
    text = str(value or "").strip()
    ids = {str(node["id"]) for node in graph.get("nodes") or []}
    if text in ids:
        return text
    if ":" in text:
        try:
            ident = parse_ref(text)
        except GoatError:
            ident = text
        if ident in ids:
            return ident
    suffix = text.split(":")[-1]
    matches = [
        ident
        for ident in ids
        if ident.endswith(":" + suffix) or ident.split(":")[-1] == suffix
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        priority = ("application", "service", "api", "feature", "adr", "database")
        ranked = sorted(
            matches,
            key=lambda ident: (
                priority.index(ident.split(":")[0])
                if ident.split(":")[0] in priority
                else 99
            ),
        )
        if ranked[0].split(":")[0] in priority and (
            len(ranked) == 1
            or ranked[0].split(":")[0] != ranked[1].split(":")[0]
        ):
            return ranked[0]
        raise GoatError(
            f"Ambiguous node {value!r}. Matches: " + ", ".join(sorted(matches))
        )
    raise GoatError(f"Unknown graph node {value!r}.")


def _summary(graph: dict[str, Any], edge: dict[str, Any]) -> str:
    names = {node["id"]: node.get("name") or node["id"] for node in graph.get("nodes") or []}
    src = names.get(edge["source"], edge["source"])
    dst = names.get(edge["target"], edge["target"])
    return f"{src} {edge.get('relationship')} {dst}"

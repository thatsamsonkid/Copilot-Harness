from __future__ import annotations

from typing import Any

from goat import GoatError
from goat.graph.schema import (
    CLASSIFICATIONS,
    GRAPH_VERSION,
    NODE_TYPES,
    RELATIONSHIPS,
    is_node_id,
)


def validate_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Fail on structural corruption. Ambiguous edges are valid information."""
    errors: list[str] = []
    if not isinstance(graph, dict):
        raise GoatError("workspace graph must be a mapping")
    if graph.get("version") != GRAPH_VERSION:
        errors.append(f"unsupported version {graph.get('version')!r}")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        errors.append("nodes and edges must be lists")
        raise GoatError(_join(errors), payload={"errors": errors})

    node_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            errors.append("node is not a mapping")
            continue
        ident = str(node.get("id") or "")
        if ident in node_ids:
            errors.append(f"duplicate node id {ident}")
        node_ids.add(ident)
        if not is_node_id(ident):
            errors.append(f"malformed node id {ident!r}")
        if node.get("type") not in NODE_TYPES:
            errors.append(f"unknown node type {node.get('type')!r} on {ident}")
        if not node.get("name"):
            errors.append(f"node {ident} missing name")

    seen_edges: set[str] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            errors.append("edge is not a mapping")
            continue
        ident = str(edge.get("id") or "")
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        rel = str(edge.get("relationship") or "")
        classification = str(edge.get("classification") or "")
        if ident in seen_edges:
            errors.append(f"duplicate edge id {ident}")
        seen_edges.add(ident)
        if source not in node_ids:
            errors.append(f"edge {ident} source {source} is not a node")
        if target not in node_ids:
            errors.append(f"edge {ident} target {target} is not a node")
        if rel not in RELATIONSHIPS:
            errors.append(f"edge {ident} has invalid relationship {rel!r}")
        if classification not in CLASSIFICATIONS:
            errors.append(f"edge {ident} has invalid classification {classification!r}")
        confidence = edge.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            errors.append(f"edge {ident} has invalid confidence {confidence!r}")
        evidence = edge.get("evidence")
        if evidence is not None and not isinstance(evidence, list):
            errors.append(f"edge {ident} evidence must be a list")

    if errors:
        raise GoatError(
            "Workspace graph failed validation: " + "; ".join(errors[:12]),
            payload={"errors": errors, "ok": False},
        )
    return {
        "ok": True,
        "nodes": len(nodes),
        "edges": len(edges),
        "errors": [],
    }


def _join(errors: list[str]) -> str:
    return "Workspace graph failed validation: " + "; ".join(errors[:12])

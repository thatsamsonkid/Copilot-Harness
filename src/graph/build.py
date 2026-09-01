from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from goat.catalog import Catalog
from goat.graph.correlate import correlate
from goat.graph.extract import ExtractContext, default_extractors, run_extractors
from goat.graph.schema import (
    EVIDENCE_RELATIVE,
    GENERATED_RELATIVE,
    GRAPH_VERSION,
)
from goat.graph.validate import validate_graph
from goat.workspace_detect import resolve_workspace_scope, scoped_repos


def scan_workspace(
    catalog: Catalog,
    goat_root: Path,
    *,
    workspace_id: str | None = None,
    all_repos: bool = True,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    ctx = _context(
        catalog,
        goat_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    rows = run_extractors(ctx)
    return {
        "kind": "workspace_graph_scan",
        "workspace": ctx.workspace_id,
        "repos": [repo.name for repo in ctx.repos],
        "extractors": [
            {
                "name": row["name"],
                "nodes": row["nodes"],
                "candidates": row["candidates"],
                "files": [Path(item).name for item in row["files"][:20]],
                "detail": row["detail"],
            }
            for row in rows
        ],
        "guidance": [
            "Extractors report evidence. Correlation decides relationships.",
            "Declare implicit edges in catalog/graph.yaml or "
            "<repo>/.workspace/component.yaml.",
            "Reject false positives in catalog/graph.yaml reject: so they survive rebuilds.",
        ],
    }


def build_graph(
    catalog: Catalog,
    goat_root: Path,
    *,
    workspace_id: str | None = None,
    all_repos: bool = True,
    environ: Mapping[str, str] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    ctx = _context(
        catalog,
        goat_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    rows = run_extractors(ctx)
    nodes = []
    candidates = []
    files: list[str] = []
    for row in rows:
        nodes.extend(row["batch"].nodes)
        candidates.extend(row["batch"].candidates)
        files.extend(row["batch"].files)
    nodes, edges = correlate(nodes, candidates)
    graph = {
        "version": GRAPH_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "nodes": [node.to_dict() for node in sorted(nodes, key=lambda item: item.id)],
        "edges": [
            edge.to_edge_dict()
            for edge in sorted(edges, key=lambda item: item.id)
        ],
        "metadata": {
            "goat_root": str(goat_root),
            "workspace": ctx.workspace_id,
            "repos": [repo.name for repo in ctx.repos],
            "extractors": [item.name for item in default_extractors()],
            "files": sorted(set(files)),
            "guidance": [
                "This file is generated. Do not edit it.",
                "Put intent in catalog/graph.yaml or .workspace/component.yaml.",
                "Use goat graph explain to see why an edge exists.",
            ],
        },
    }
    validate_graph(graph)
    dest = goat_root / GENERATED_RELATIVE
    if write:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
        evidence_path = goat_root / EVIDENCE_RELATIVE
        evidence_path.write_text(
            json.dumps(
                {
                    "version": GRAPH_VERSION,
                    "generatedAt": graph["generatedAt"],
                    "extractors": [
                        {
                            "name": row["name"],
                            "nodes": row["nodes"],
                            "candidates": row["candidates"],
                            "files": row["files"],
                        }
                        for row in rows
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return {
        "kind": "workspace_graph_build",
        "file": str(dest),
        "wrote": write,
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "extractors": [row["name"] for row in rows],
        "validation": {"ok": True},
        "graph": graph,
    }


def load_graph(goat_root: Path, path: Path | None = None) -> dict[str, Any]:
    dest = Path(path) if path else goat_root / GENERATED_RELATIVE
    if not dest.is_file():
        from goat import GoatError

        raise GoatError(
            f"Workspace graph missing: {dest}. Run `goat graph build`."
        )
    return json.loads(dest.read_text(encoding="utf-8"))


def _context(
    catalog: Catalog,
    goat_root: Path,
    *,
    workspace_id: str | None,
    all_repos: bool,
    environ: Mapping[str, str] | None,
) -> ExtractContext:
    scope = resolve_workspace_scope(
        catalog,
        goat_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    repos = scoped_repos(catalog, scope)
    return ExtractContext(
        catalog=catalog,
        goat_root=goat_root,
        repos=list(repos),
        workspace_id=scope.id,
    )

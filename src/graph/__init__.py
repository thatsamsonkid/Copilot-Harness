"""Canonical workspace graph: extractors → evidence → correlated JSON."""

from goat.graph.build import build_graph, scan_workspace
from goat.graph.query import explain, neighbors, path_between
from goat.graph.validate import validate_graph

__all__ = [
    "build_graph",
    "explain",
    "neighbors",
    "path_between",
    "scan_workspace",
    "validate_graph",
]

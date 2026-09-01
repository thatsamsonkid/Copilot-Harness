from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from goat.graph.schema import (
    CLASSIFICATIONS,
    NODE_TYPES,
    RELATIONSHIPS,
    clamp_confidence,
    edge_id,
    node_id,
)


@dataclass
class Evidence:
    type: str
    extractor: str
    repository: str | None = None
    file: str | None = None
    line: int | None = None
    symbol: str | None = None
    key: str | None = None
    value: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not payload["metadata"]:
            payload.pop("metadata")
        return {key: item for key, item in payload.items() if item is not None}


@dataclass
class Node:
    id: str
    type: str
    name: str
    repository: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "name": self.name,
        }
        if self.repository:
            payload["repository"] = self.repository
        if self.attrs:
            payload["attrs"] = self.attrs
        return payload


@dataclass
class Candidate:
    source: str
    target: str
    relationship: str
    classification: str
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    note: str | None = None

    @property
    def id(self) -> str:
        return edge_id(self.source, self.relationship, self.target)

    def to_edge_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "relationship": self.relationship,
            "classification": self.classification,
            "confidence": clamp_confidence(self.confidence),
            "evidence": [item.to_dict() for item in self.evidence],
        }
        if self.note:
            payload["note"] = self.note
        return payload


@dataclass
class ExtractBatch:
    nodes: list[Node] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    detail: str = ""


def make_node(
    node_type: str,
    name: str,
    *,
    repository: str | None = None,
    attrs: dict[str, Any] | None = None,
    node: str | None = None,
) -> Node:
    ident = node or node_id(node_type, name)
    return Node(
        id=ident,
        type=ident.split(":", 1)[0],
        name=name,
        repository=repository,
        attrs=attrs or {},
    )


def known_type(value: str) -> bool:
    return value in NODE_TYPES


def known_relationship(value: str) -> bool:
    return value in RELATIONSHIPS


def known_classification(value: str) -> bool:
    return value in CLASSIFICATIONS

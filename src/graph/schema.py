from __future__ import annotations

import re
from pathlib import Path

from goat import GoatError

GRAPH_VERSION = 1
GENERATED_RELATIVE = Path(".workspace") / "generated" / "workspace-graph.json"
EVIDENCE_RELATIVE = Path(".workspace") / "generated" / "evidence.json"
COMPONENT_RELATIVE = Path(".workspace") / "component.yaml"
OVERRIDES_RELATIVE = Path("catalog") / "graph.yaml"
LOCAL_OVERRIDES_RELATIVE = Path(".workspace") / "overrides.yaml"

NODE_TYPES = frozenset(
    {
        "workspace",
        "repository",
        "application",
        "service",
        "library",
        "api",
        "api-operation",
        "event",
        "queue",
        "topic",
        "database",
        "table",
        "schema",
        "external-system",
        "deployment",
        "domain",
        "feature",
        "adr",
    }
)

TYPE_ALIASES = {
    "repo": "repository",
    "app": "application",
    "svc": "service",
    "db": "database",
}

RELATIONSHIPS = frozenset(
    {
        "CONTAINS",
        "MEMBER_OF",
        "DEPENDS_ON",
        "CONSUMES",
        "PROVIDES",
        "PUBLISHES",
        "SUBSCRIBES",
        "USES",
        "GOVERNED_BY",
        "ROUTES",
    }
)

CLASSIFICATIONS = frozenset(
    {
        "DECLARED",
        "OBSERVED",
        "EXTRACTED",
        "INFERRED",
        "AMBIGUOUS",
        "REJECTED",
    }
)

CLASSIFICATION_RANK = {
    "REJECTED": 0,
    "AMBIGUOUS": 1,
    "INFERRED": 2,
    "EXTRACTED": 3,
    "OBSERVED": 4,
    "DECLARED": 5,
}

DEFAULT_CONFIDENCE = {
    "DECLARED": 1.0,
    "OBSERVED": 0.99,
    "EXTRACTED": 0.95,
    "INFERRED": 0.7,
    "AMBIGUOUS": 0.4,
    "REJECTED": 0.0,
}

_ID = re.compile(r"^[a-z][a-z0-9_.:-]*:[a-z0-9][a-z0-9_.-]*$")
_SLUG = re.compile(r"[^a-z0-9.]+")


def slugify(value: str) -> str:
    text = _SLUG.sub("-", str(value).strip().lower()).strip("-")
    return text or "unnamed"


def node_id(node_type: str, name: str) -> str:
    kind = canonical_type(node_type)
    return f"{kind}:{slugify(name)}"


def canonical_type(node_type: str) -> str:
    kind = str(node_type or "").strip().lower()
    kind = TYPE_ALIASES.get(kind, kind)
    if kind not in NODE_TYPES:
        raise GoatError(
            f"Unknown node type {node_type!r}. Expected one of: "
            + ", ".join(sorted(NODE_TYPES))
        )
    return kind


def canonical_relationship(value: str) -> str:
    rel = str(value or "").strip().upper().replace(" ", "_")
    if rel not in RELATIONSHIPS:
        raise GoatError(
            f"Unknown relationship {value!r}. Expected one of: "
            + ", ".join(sorted(RELATIONSHIPS))
        )
    return rel


def canonical_classification(value: str) -> str:
    item = str(value or "").strip().upper()
    if item not in CLASSIFICATIONS:
        raise GoatError(
            f"Unknown classification {value!r}. Expected one of: "
            + ", ".join(sorted(CLASSIFICATIONS))
        )
    return item


def parse_ref(value: str, *, default_type: str | None = None) -> str:
    """Accept `api:booking-v2`, `repo:frontend`, or a bare slug with default_type."""
    text = str(value or "").strip()
    if not text:
        raise GoatError("Empty node reference")
    if ":" in text:
        kind, _, rest = text.partition(":")
        if kind.lower() in TYPE_ALIASES or kind.lower() in NODE_TYPES:
            return node_id(kind, rest)
        # ADR-014 style accidentally written as id:ADR-014
        return node_id(default_type or "external-system", text)
    if default_type:
        return node_id(default_type, text)
    raise GoatError(
        f"Node reference {value!r} must look like type:slug (api:booking-v2)"
    )


def edge_id(source: str, relationship: str, target: str) -> str:
    return f"{source}>{relationship}>{target}"


def is_node_id(value: str) -> bool:
    return bool(_ID.match(str(value or "")))


def clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

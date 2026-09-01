from __future__ import annotations

from goat.graph.models import Candidate, Evidence, Node
from goat.graph.schema import (
    CLASSIFICATION_RANK,
    DEFAULT_CONFIDENCE,
    clamp_confidence,
    edge_id,
)

HINT_ATTR = "hint"


def correlate(
    nodes: list[Node],
    candidates: list[Candidate],
) -> tuple[list[Node], list[Candidate]]:
    """Merge extractor output into explainable edges. Prefer contracts over repo DEPENDS_ON."""
    by_id = _merge_nodes(nodes)
    _rewire_hint_apis(by_id, candidates)
    merged: dict[str, Candidate] = {}
    for candidate in candidates:
        if candidate.source == candidate.target:
            continue
        key = edge_id(candidate.source, candidate.relationship, candidate.target)
        existing = merged.get(key)
        if existing is None:
            merged[key] = _copy(candidate)
            continue
        _merge_edge(existing, candidate)

    _mark_ambiguous_env_targets(merged)
    _derive_repo_depends(merged, by_id)

    edges = list(merged.values())
    used = {edge.source for edge in edges} | {edge.target for edge in edges}
    used.update(
        node.id
        for node in by_id.values()
        if node.type in {"workspace", "repository", "feature"}
    )
    kept = [node for node in by_id.values() if node.id in used]
    return kept, edges


def _merge_nodes(nodes: list[Node]) -> dict[str, Node]:
    by_id: dict[str, Node] = {}
    for node in nodes:
        current = by_id.get(node.id)
        if current is None:
            by_id[node.id] = Node(
                id=node.id,
                type=node.type,
                name=node.name,
                repository=node.repository,
                attrs=dict(node.attrs),
            )
            continue
        if node.repository and not current.repository:
            current.repository = node.repository
        if node.name and (current.name == current.id.split(":", 1)[-1] or len(node.name) > len(current.name)):
            if not current.attrs.get(HINT_ATTR) or not node.attrs.get(HINT_ATTR):
                current.name = node.name
        current.attrs.update({k: v for k, v in node.attrs.items() if k != HINT_ATTR})
        if not node.attrs.get(HINT_ATTR):
            current.attrs.pop(HINT_ATTR, None)
    return by_id


def _rewire_hint_apis(by_id: dict[str, Node], candidates: list[Candidate]) -> None:
    """Point env/proxy hint APIs at a real OpenAPI/declared API when tokens match uniquely."""
    real_apis = [
        node
        for node in by_id.values()
        if node.type == "api" and not node.attrs.get(HINT_ATTR)
    ]
    for candidate in candidates:
        if candidate.relationship != "CONSUMES":
            continue
        target = by_id.get(candidate.target)
        if target is None or not target.attrs.get(HINT_ATTR):
            continue
        token = (target.id.split(":", 1)[-1] if ":" in target.id else target.id)
        matches = [node for node in real_apis if _token_hits(token, node)]
        if len(matches) == 1:
            candidate.target = matches[0].id
            candidate.classification = _bump(candidate.classification, "INFERRED")
            candidate.confidence = max(candidate.confidence, 0.82)
            candidate.evidence.append(
                Evidence(
                    type="correlation",
                    extractor="correlate",
                    value=f"{token} matched {matches[0].id}",
                )
            )
            candidate.note = (candidate.note or "") + f"; correlated to {matches[0].id}"
        elif len(matches) > 1:
            candidate.classification = "AMBIGUOUS"
            candidate.confidence = DEFAULT_CONFIDENCE["AMBIGUOUS"]
            candidate.note = (
                f"token {token} matches " + ", ".join(item.id for item in matches)
            )


def _token_hits(token: str, node: Node) -> bool:
    slug = node.id.split(":", 1)[-1]
    name = node.name.lower().replace(" ", "-")
    if token and (token in slug or token in name or slug.startswith(token)):
        return True
    for path in node.attrs.get("paths") or []:
        parts = [part for part in str(path).split("/") if part]
        if parts and parts[0] == token:
            return True
        if len(parts) > 1 and parts[0] in {"api", "v1", "v2"} and parts[1] == token:
            return True
    return False


def _mark_ambiguous_env_targets(merged: dict[str, Candidate]) -> None:
    consumes: dict[tuple[str, str], list[Candidate]] = {}
    for edge in merged.values():
        if edge.relationship != "CONSUMES" or edge.classification == "REJECTED":
            continue
        tokens = {
            str(item.metadata.get("token"))
            for item in edge.evidence
            if item.metadata.get("token")
        }
        for token in tokens:
            consumes.setdefault((edge.source, token), []).append(edge)
    for group in consumes.values():
        targets = {item.target for item in group}
        if len(targets) > 1 and all(
            item.classification in {"INFERRED", "AMBIGUOUS"} for item in group
        ):
            for item in group:
                item.classification = "AMBIGUOUS"
                item.confidence = min(item.confidence, DEFAULT_CONFIDENCE["AMBIGUOUS"])


def _derive_repo_depends(merged: dict[str, Candidate], by_id: dict[str, Node]) -> None:
    provides: dict[str, set[str]] = {}
    consumes: dict[str, set[str]] = {}
    for edge in merged.values():
        if edge.classification == "REJECTED":
            continue
        source = by_id.get(edge.source)
        if edge.relationship == "PROVIDES" and source is not None:
            repo = source.repository or (edge.source if edge.source.startswith("repository:") else None)
            if repo:
                provides.setdefault(edge.target, set()).add(repo)
        if edge.relationship == "CONSUMES" and source is not None:
            repo = source.repository or (
                f"repository:{edge.source.split(':', 1)[-1]}"
                if edge.source.split(":")[0] in {"application", "service"}
                else None
            )
            if source.type == "repository":
                repo = source.id
            if repo:
                consumes.setdefault(edge.target, set()).add(repo)
    for api, consumers in consumes.items():
        producers = provides.get(api) or set()
        for consumer in consumers:
            for producer in producers:
                if consumer == producer:
                    continue
                key = edge_id(consumer, "DEPENDS_ON", producer)
                if key in merged:
                    continue
                merged[key] = Candidate(
                    source=consumer,
                    target=producer,
                    relationship="DEPENDS_ON",
                    classification="INFERRED",
                    confidence=0.75,
                    evidence=[
                        Evidence(
                            type="correlation",
                            extractor="correlate",
                            value=f"{consumer} consumes {api} provided by {producer}",
                        )
                    ],
                    note="derived from CONSUMES/PROVIDES; prefer the contract edge",
                )


def _merge_edge(existing: Candidate, incoming: Candidate) -> None:
    existing.evidence.extend(incoming.evidence)
    if incoming.classification == "REJECTED" or existing.classification == "REJECTED":
        existing.classification = "REJECTED"
        existing.confidence = 0.0
        return
    if CLASSIFICATION_RANK[incoming.classification] > CLASSIFICATION_RANK[existing.classification]:
        existing.classification = incoming.classification
    extra = max(0, len(existing.evidence) - 1)
    if existing.classification == "INFERRED":
        existing.confidence = clamp_confidence(0.6 + 0.12 * extra)
    else:
        existing.confidence = max(existing.confidence, incoming.confidence)
    if incoming.note and incoming.note not in (existing.note or ""):
        existing.note = " ".join(part for part in (existing.note, incoming.note) if part)


def _copy(candidate: Candidate) -> Candidate:
    return Candidate(
        source=candidate.source,
        target=candidate.target,
        relationship=candidate.relationship,
        classification=candidate.classification,
        confidence=candidate.confidence,
        evidence=list(candidate.evidence),
        note=candidate.note,
    )


def _bump(current: str, minimum: str) -> str:
    if CLASSIFICATION_RANK[current] >= CLASSIFICATION_RANK[minimum]:
        return current
    return minimum

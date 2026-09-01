from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import yaml

from goat.catalog import Catalog, Repo
from goat.context import discover_graphify, discover_knowledge
from goat.graph.manifests import (
    component_batch,
    load_component_manifest,
    load_overrides,
    overrides_batch,
)
from goat.graph.models import Candidate, Evidence, ExtractBatch, Node, make_node
from goat.graph.schema import (
    COMPONENT_RELATIVE,
    DEFAULT_CONFIDENCE,
    node_id,
    parse_ref,
    slugify,
)
from goat.start import discover_start

OPENAPI_FILES = (
    "openapi.yaml",
    "openapi.yml",
    "openapi.json",
    "swagger.yaml",
    "swagger.yml",
    "swagger.json",
    "docs/openapi.yaml",
    "docs/openapi.yml",
    "docs/openapi.json",
    "src/openapi.yaml",
    "src/main/resources/openapi.yaml",
    "src/main/resources/openapi.yml",
)

ENV_EXAMPLE_FILES = (".env.example", ".env.sample", ".env.template")
ENV_KEY = re.compile(r"^([A-Z][A-Z0-9_]+)=(.*)$")
API_KEY_HINT = re.compile(r"(API|BASE|SERVICE|GRAPHQL)_URL$")
ADR_FILE = re.compile(r"(?i)(?:^|[^a-z])adr[-_ ]?(\d+)")
PACKAGE_GITHUB = re.compile(
    r"(?:github:|git\+https://github\.com/|https://github\.com/)([^/]+)/([^/#.]+)"
)

FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.S)


@dataclass
class ExtractContext:
    catalog: Catalog
    goat_root: Path
    repos: list[Repo]
    workspace_id: str | None = None


class Extractor(Protocol):
    name: str

    def extract(self, ctx: ExtractContext) -> ExtractBatch: ...


@dataclass
class FnExtractor:
    name: str
    fn: Callable[[ExtractContext], ExtractBatch]

    def extract(self, ctx: ExtractContext) -> ExtractBatch:
        return self.fn(ctx)


def default_extractors() -> list[Extractor]:
    return [
        FnExtractor("catalog", extract_catalog),
        FnExtractor("overrides", extract_overrides),
        FnExtractor("component", extract_components),
        FnExtractor("package", extract_packages),
        FnExtractor("openapi", extract_openapi),
        FnExtractor("envconfig", extract_envconfig),
        FnExtractor("adr", extract_adrs),
        FnExtractor("proxy", extract_proxies),
        FnExtractor("bruno", extract_bruno),
        FnExtractor("graphify", extract_graphify),
    ]


def run_extractors(
    ctx: ExtractContext, extractors: list[Extractor] | None = None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for extractor in extractors or default_extractors():
        batch = extractor.extract(ctx)
        rows.append(
            {
                "name": extractor.name,
                "nodes": len(batch.nodes),
                "candidates": len(batch.candidates),
                "files": batch.files,
                "detail": batch.detail,
                "batch": batch,
            }
        )
    return rows


def extract_catalog(ctx: ExtractContext) -> ExtractBatch:
    workspace = make_node(
        "workspace",
        ctx.workspace_id or ctx.goat_root.name,
        attrs={"goat_root": str(ctx.goat_root)},
    )
    nodes = [workspace]
    candidates: list[Candidate] = []
    evidence = Evidence(
        type="catalog",
        extractor="catalog",
        file="repositories.yml",
        value="repositories.yml",
    )
    for repo in ctx.repos:
        repo_node = make_node(
            "repository",
            repo.name,
            repository=node_id("repository", repo.name),
            attrs={"path": repo.path, "tags": list(repo.tags), "url": repo.url},
        )
        nodes.append(repo_node)
        kind = _kind_from_tags(repo.tags)
        if kind:
            runtime = make_node(kind, repo.name, repository=repo_node.id)
            nodes.append(runtime)
            candidates.append(
                _extracted(
                    repo_node.id,
                    "CONTAINS",
                    runtime.id,
                    evidence,
                    f"tags {repo.tags} → {kind}",
                )
            )
        candidates.append(
            Candidate(
                source=workspace.id,
                target=repo_node.id,
                relationship="CONTAINS",
                classification="DECLARED",
                confidence=DEFAULT_CONFIDENCE["DECLARED"],
                evidence=[evidence],
                note="catalog membership",
            )
        )
    for item in ctx.catalog.workspaces:
        feature = make_node("feature", item.id, attrs={"workspace": item.id})
        nodes.append(feature)
        stack_ev = Evidence(
            type="catalog",
            extractor="catalog",
            file="catalog/stack.yaml",
            key="workspaces",
            value=item.id,
        )
        candidates.append(
            _extracted(workspace.id, "CONTAINS", feature.id, stack_ev, "stack workspace")
        )
        for name in ctx.catalog.workspace_repo_names(item):
            if name not in {repo.name for repo in ctx.repos}:
                continue
            candidates.append(
                _extracted(
                    feature.id,
                    "ROUTES",
                    node_id("repository", name),
                    stack_ev,
                    "workspace folders",
                )
            )
    return ExtractBatch(
        nodes=nodes,
        candidates=candidates,
        files=["repositories.yml", "catalog/stack.yaml"],
        detail=f"{len(ctx.repos)} catalog repos",
    )


def extract_overrides(ctx: ExtractContext) -> ExtractBatch:
    rows = load_overrides(ctx.goat_root)
    batch = overrides_batch(rows)
    batch.files = [
        str(ctx.goat_root / "catalog" / "graph.yaml"),
        str(ctx.goat_root / ".workspace" / "overrides.yaml"),
    ]
    batch.detail = f"{len(rows['declare'])} declared, {len(rows['reject'])} rejected"
    return batch


def extract_components(ctx: ExtractContext) -> ExtractBatch:
    batch = ExtractBatch(detail="repository .workspace/component.yaml")
    for repo, path in _cloned(ctx):
        manifest = path / COMPONENT_RELATIVE
        if not manifest.is_file():
            continue
        raw = load_component_manifest(manifest)
        part = component_batch(
            repo.name, node_id("repository", repo.name), manifest, raw
        )
        batch.nodes.extend(part.nodes)
        batch.candidates.extend(part.candidates)
        batch.files.extend(part.files)
    return batch


def extract_packages(ctx: ExtractContext) -> ExtractBatch:
    batch = ExtractBatch(detail="package.json / pyproject.toml dependencies")
    catalog_urls = {normalize_dep(repo.url): repo.name for repo in ctx.catalog.repos}
    catalog_names = {repo.name.lower(): repo.name for repo in ctx.catalog.repos}
    for repo, path in _cloned(ctx):
        repo_id = node_id("repository", repo.name)
        package = _read_json(path / "package.json")
        if isinstance(package, dict):
            batch.files.append(str(path / "package.json"))
            deps = {
                **(package.get("dependencies") or {}),
                **(package.get("devDependencies") or {}),
            }
            for name, spec in deps.items():
                target = _match_dep(str(name), str(spec), catalog_urls, catalog_names)
                if not target or target == repo.name:
                    continue
                evidence = Evidence(
                    type="package",
                    extractor="package",
                    repository=repo.name,
                    file="package.json",
                    key=str(name),
                    value=str(spec),
                )
                batch.candidates.append(
                    _extracted(
                        repo_id,
                        "DEPENDS_ON",
                        node_id("repository", target),
                        evidence,
                        "package.json dependency",
                    )
                )
        pyproject = path / "pyproject.toml"
        if pyproject.is_file():
            batch.files.append(str(pyproject))
            text = pyproject.read_text(encoding="utf-8")
            for name in catalog_names:
                if name == repo.name.lower():
                    continue
                if re.search(rf'["\']{re.escape(name)}["\']', text):
                    evidence = Evidence(
                        type="package",
                        extractor="package",
                        repository=repo.name,
                        file="pyproject.toml",
                        key=name,
                    )
                    batch.candidates.append(
                        _extracted(
                            repo_id,
                            "DEPENDS_ON",
                            node_id("repository", catalog_names[name]),
                            evidence,
                            "pyproject.toml mentions catalog repo",
                        )
                    )
    return batch


def extract_openapi(ctx: ExtractContext) -> ExtractBatch:
    batch = ExtractBatch(detail="OpenAPI specifications")
    for repo, path in _cloned(ctx):
        repo_id = node_id("repository", repo.name)
        runtime_node = _runtime_node(repo)
        runtime = runtime_node.id
        batch.nodes.append(runtime_node)
        for relative in OPENAPI_FILES:
            spec_path = path / relative
            if not spec_path.is_file():
                continue
            data = _read_yaml_or_json(spec_path)
            if not isinstance(data, dict) or not (data.get("paths") or data.get("openapi")):
                continue
            info = data.get("info") if isinstance(data.get("info"), dict) else {}
            title = str(info.get("title") or repo.name)
            api_slug = slugify(str(info.get("x-workspace-id") or title))
            api = make_node("api", title, repository=repo_id, node=node_id("api", api_slug))
            paths = [
                str(item)
                for item in (data.get("paths") or {})
                if isinstance(item, str) and item.startswith("/")
            ]
            api.attrs["paths"] = paths[:40]
            batch.nodes.append(api)
            evidence = Evidence(
                type="openapi-provider",
                extractor="openapi",
                repository=repo.name,
                file=relative,
                value=title,
                metadata={"paths": paths[:12]},
            )
            batch.candidates.append(
                _extracted(runtime, "PROVIDES", api.id, evidence, "OpenAPI spec")
            )
            batch.candidates.append(
                _extracted(repo_id, "CONTAINS", runtime, evidence, "provider repo")
            )
            batch.files.append(str(spec_path))
    return batch


def extract_envconfig(ctx: ExtractContext) -> ExtractBatch:
    batch = ExtractBatch(detail=".env.example keys only (no values)")
    for repo, path in _cloned(ctx):
        runtime_node = _runtime_node(repo, default="application")
        runtime = runtime_node.id
        batch.nodes.append(runtime_node)
        for relative in ENV_EXAMPLE_FILES:
            env_path = path / relative
            if not env_path.is_file():
                continue
            batch.files.append(str(env_path))
            for line in env_path.read_text(encoding="utf-8").splitlines():
                match = ENV_KEY.match(line.strip())
                if not match or not API_KEY_HINT.search(match.group(1)):
                    continue
                key = match.group(1)
                token = _token_from_env_key(key)
                evidence = Evidence(
                    type="configuration",
                    extractor="envconfig",
                    repository=repo.name,
                    file=relative,
                    key=key,
                    value=key,
                    metadata={"token": token},
                )
                hint = make_node("api", token or key, node=node_id("api", token or key))
                hint.attrs["hint"] = True
                batch.nodes.append(hint)
                batch.candidates.append(
                    Candidate(
                        source=runtime,
                        target=hint.id,
                        relationship="CONSUMES",
                        classification="INFERRED",
                        confidence=0.55,
                        evidence=[evidence],
                        note=f"{key} suggests an API",
                    )
                )
    return batch


def extract_adrs(ctx: ExtractContext) -> ExtractBatch:
    batch = ExtractBatch(detail="ADR markdown + optional governs: frontmatter")
    for repo, path in _cloned(ctx):
        knowledge = discover_knowledge(path, extra_dirs=repo.knowledge_dirs)
        repo_id = node_id("repository", repo.name)
        runtime_node = _runtime_node(repo)
        runtime = runtime_node.id
        batch.nodes.append(runtime_node)
        for item in knowledge.get("files") or []:
            if item.get("kind") != "adr":
                continue
            file_path = Path(item["path"])
            if not file_path.is_file():
                continue
            batch.files.append(str(file_path))
            meta = _adr_meta(file_path)
            adr_name = meta.get("id") or file_path.stem
            adr = make_node("adr", str(meta.get("title") or adr_name))
            adr.id = node_id("adr", str(adr_name))
            adr.attrs["title"] = meta.get("title") or adr.name
            batch.nodes.append(adr)
            evidence = Evidence(
                type="adr",
                extractor="adr",
                repository=repo.name,
                file=str(file_path.relative_to(path)),
                value=adr.id,
            )
            batch.candidates.append(
                _extracted(runtime, "GOVERNED_BY", adr.id, evidence, "ADR in repo")
            )
            for ref in meta.get("governs") or []:
                target = parse_ref(ref, default_type="service")
                batch.nodes.append(_loose_node(target))
                batch.candidates.append(
                    Candidate(
                        source=target,
                        target=adr.id,
                        relationship="GOVERNED_BY",
                        classification="DECLARED",
                        confidence=DEFAULT_CONFIDENCE["DECLARED"],
                        evidence=[evidence],
                        note="ADR frontmatter governs",
                    )
                )
            batch.candidates.append(
                _extracted(repo_id, "CONTAINS", adr.id, evidence, "ADR file")
            )
    return batch


def extract_proxies(ctx: ExtractContext) -> ExtractBatch:
    batch = ExtractBatch(detail="dev-server proxy targets")
    for repo, path in _cloned(ctx):
        if not (_kind_from_tags(repo.tags) in {"application", None} or "ui" in repo.tags):
            # still try; discover_start is cheap
            pass
        snapshot = discover_start(path, repo)
        runtime_node = _runtime_node(repo, default="application")
        runtime = runtime_node.id
        batch.nodes.append(runtime_node)
        for proxy in snapshot.get("proxies") or []:
            relative = proxy.get("relative") or "proxy"
            for target in proxy.get("targets") or []:
                context = str(target.get("context") or "")
                dest = str(target.get("target") or "")
                token = _token_from_path(context) or _token_from_url(dest)
                if not token:
                    continue
                api = make_node("api", token, node=node_id("api", token))
                api.attrs["hint"] = True
                batch.nodes.append(api)
                evidence = Evidence(
                    type="http-client",
                    extractor="proxy",
                    repository=repo.name,
                    file=relative,
                    key=context or None,
                    value=dest or context,
                    metadata={"token": token},
                )
                batch.candidates.append(
                    Candidate(
                        source=runtime,
                        target=api.id,
                        relationship="CONSUMES",
                        classification="INFERRED",
                        confidence=0.7,
                        evidence=[evidence],
                        note=f"proxy {context} → {dest}",
                    )
                )
                batch.files.append(str(path / relative))
    return batch


def extract_bruno(ctx: ExtractContext) -> ExtractBatch:
    from goat.bruno import collect_bruno_inventory

    batch = ExtractBatch(detail="Bruno collections as API consumers")
    inventory = collect_bruno_inventory(ctx.catalog, ctx.goat_root)
    wanted = {repo.name for repo in ctx.repos}
    for collection in inventory.get("collections") or []:
        repo_name = collection.get("repo")
        if repo_name not in wanted:
            continue
        runtime = node_id("application", str(repo_name))
        batch.nodes.append(make_node("application", str(repo_name), repository=node_id("repository", str(repo_name))))
        paths = []
        for request in collection.get("requests") or []:
            url = str(request.get("url") or request.get("path") or "")
            token = _token_from_path(url) or _token_from_url(url)
            if token:
                paths.append((token, request.get("id") or url))
        tokens = {token for token, _ in paths}
        for token in tokens:
            api = make_node("api", token, node=node_id("api", token))
            api.attrs["hint"] = True
            batch.nodes.append(api)
            evidence = Evidence(
                type="bruno",
                extractor="bruno",
                repository=str(repo_name),
                file=str(collection.get("relpath") or collection.get("path") or ""),
                value=token,
                metadata={"collection": collection.get("id")},
            )
            batch.candidates.append(
                Candidate(
                    source=runtime,
                    target=api.id,
                    relationship="CONSUMES",
                    classification="INFERRED",
                    confidence=0.6,
                    evidence=[evidence],
                    note=f"Bruno collection {collection.get('id')}",
                )
            )
    return batch


def extract_graphify(ctx: ExtractContext) -> ExtractBatch:
    batch = ExtractBatch(detail="Graphify graph.json promoted at workspace scale only")
    architectural = {
        "api",
        "service",
        "application",
        "database",
        "event",
        "queue",
        "topic",
        "external-system",
        "domain",
    }
    skip = {"file", "class", "method", "function", "symbol", "module", "directory"}
    for repo, path in _cloned(ctx):
        snapshot = discover_graphify(path, repo)
        graph_path = snapshot.get("graph")
        if not graph_path or not Path(graph_path).is_file():
            continue
        rel = str(Path(graph_path).relative_to(path)) if path in Path(graph_path).parents or Path(graph_path).parent == path else "graphify-out/graph.json"
        batch.files.append(str(graph_path))
        repo_id = node_id("repository", repo.name)
        evidence = Evidence(
            type="graphify",
            extractor="graphify",
            repository=repo.name,
            file=rel,
            value="graph.json",
        )
        data = _read_json(Path(graph_path))
        promoted = 0
        nodes_raw = []
        if isinstance(data, dict):
            nodes_raw = data.get("nodes") or data.get("communities") or []
        if not isinstance(nodes_raw, list):
            nodes_raw = []
        for item in nodes_raw:
            if promoted >= 25 or not isinstance(item, dict):
                continue
            kind = str(item.get("type") or item.get("kind") or item.get("label") or "").lower()
            if kind in skip:
                continue
            if kind not in architectural and not _looks_architectural(item):
                continue
            name = str(item.get("name") or item.get("id") or item.get("label") or "")
            if not name:
                continue
            use_type = kind if kind in architectural else "external-system"
            node = make_node(use_type, name, repository=repo_id)
            batch.nodes.append(node)
            batch.candidates.append(
                Candidate(
                    source=repo_id,
                    target=node.id,
                    relationship="CONTAINS",
                    classification="EXTRACTED",
                    confidence=0.8,
                    evidence=[evidence],
                    note="promoted from Graphify",
                )
            )
            promoted += 1
        if promoted == 0:
            batch.candidates.append(
                _extracted(
                    repo_id,
                    "CONTAINS",
                    repo_id,
                    evidence,
                    "Graphify present; no architectural nodes promoted",
                )
            )
            # CONTAINS self is invalid — drop that. Just record file.
            batch.candidates.pop()
        batch.detail = f"promoted {promoted} Graphify node(s)"
    return batch


def _cloned(ctx: ExtractContext) -> list[tuple[Repo, Path]]:
    found: list[tuple[Repo, Path]] = []
    for repo in ctx.repos:
        path = ctx.catalog.repo_path(ctx.goat_root, repo)
        if path.is_dir():
            found.append((repo, path))
    return found


def _runtime_node(repo: Repo, default: str = "service") -> Node:
    kind = _kind_from_tags(repo.tags) or default
    return make_node(kind, repo.name, repository=node_id("repository", repo.name))


def _kind_from_tags(tags: list[str]) -> str | None:
    lowered = {tag.lower() for tag in tags}
    if lowered & {"ui", "frontend", "web", "mobile"}:
        return "application"
    if lowered & {"api", "backend", "service"}:
        return "service"
    if lowered & {"lib", "library", "shared"}:
        return "library"
    if lowered & {"bruno"}:
        return "application"
    return None


def _extracted(
    source: str, relationship: str, target: str, evidence: Evidence, note: str
) -> Candidate:
    return Candidate(
        source=source,
        target=target,
        relationship=relationship,
        classification="EXTRACTED",
        confidence=DEFAULT_CONFIDENCE["EXTRACTED"],
        evidence=[evidence],
        note=note,
    )


def _loose_node(ref: str) -> Node:
    kind, _, name = ref.partition(":")
    return make_node(kind, name, node=ref)


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_yaml_or_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def _match_dep(
    name: str,
    spec: str,
    catalog_urls: dict[str, str],
    catalog_names: dict[str, str],
) -> str | None:
    if name.lower() in catalog_names:
        return catalog_names[name.lower()]
    github = PACKAGE_GITHUB.search(spec)
    if github:
        repo = github.group(2).removesuffix(".git").lower()
        if repo in catalog_names:
            return catalog_names[repo]
    normalized = normalize_dep(spec)
    if normalized in catalog_urls:
        return catalog_urls[normalized]
    if spec.startswith("file:"):
        folder = Path(spec.removeprefix("file:")).name.lower()
        if folder in catalog_names:
            return catalog_names[folder]
    return None


def normalize_dep(value: str) -> str:
    text = str(value).strip().lower()
    text = text.removeprefix("git+")
    text = text.removesuffix(".git")
    return text


def _token_from_env_key(key: str) -> str:
    text = key
    for suffix in ("_API_URL", "_BASE_URL", "_SERVICE_URL", "_GRAPHQL_URL", "_URL"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return slugify(text)


def _token_from_path(path: str) -> str:
    parts = [part for part in str(path).split("/") if part and not part.startswith("{")]
    if not parts:
        return ""
    if parts[0] in {"api", "v1", "v2", "v3"}:
        parts = parts[1:] or parts
    return slugify(parts[0]) if parts else ""


def _token_from_url(url: str) -> str:
    text = str(url)
    if "://" in text:
        text = text.split("://", 1)[1]
        text = text.split("/", 1)[-1] if "/" in text else ""
    return _token_from_path("/" + text) if text else ""


def _adr_meta(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, Any] = {}
    match = FRONTMATTER.match(text)
    if match:
        try:
            loaded = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            loaded = None
        if isinstance(loaded, dict):
            if loaded.get("id"):
                meta["id"] = str(loaded["id"])
            if loaded.get("title"):
                meta["title"] = str(loaded["title"])
            governs = loaded.get("governs") or []
            if isinstance(governs, list):
                meta["governs"] = [str(item) for item in governs]
    file_id = ADR_FILE.search(path.name)
    if "id" not in meta and file_id:
        meta["id"] = f"ADR-{file_id.group(1).zfill(3)}"
    if "title" not in meta:
        for line in text.splitlines():
            if line.startswith("# "):
                meta["title"] = line[2:].strip()
                break
    return meta


def _looks_architectural(item: dict[str, Any]) -> bool:
    name = str(item.get("name") or item.get("id") or item.get("label") or "")
    return bool(re.search(r"(Service|Api|API|Client|Database|Queue|Topic|Event)$", name))

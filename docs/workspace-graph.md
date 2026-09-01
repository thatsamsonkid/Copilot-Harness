# Workspace graph

Goat already answers “which sibling is cloned?” (`context`, `start`, Graphify per repo). The workspace graph answers **how those siblings relate** at architecture scale: APIs, events, databases, ADRs — including relationships that never appear as an import.

```
repositories → extractors → evidence → correlator → workspace-graph.json
```

This is **not** a Graphify replacement, not Neo4j, and not an LLM architecture sketch. Graphify stays a repo-level index. The workspace graph is a navigation layer: where to look, then open the sibling graph or source.

## Phase 1 inventory (this kit)

This repository is the Goat kit. Product remotes in `repositories.yml` are placeholders until a team fills them in. There are no booking/traveler clones in a fresh goat.

Signals Goat already knows how to discover (and the extractors we shipped):

| Signal | Where | Extractor |
| --- | --- | --- |
| Catalog repos + workspaces | `repositories.yml`, `catalog/stack.yaml` | `catalog` |
| Declared / rejected edges | `catalog/graph.yaml`, `.workspace/overrides.yaml` | `overrides` |
| Implicit contracts | `<repo>/.workspace/component.yaml` | `component` |
| npm / PyPI deps that name a catalog repo | `package.json`, `pyproject.toml` | `package` |
| OpenAPI provider | `openapi.yaml` (common paths only) | `openapi` |
| `*_API_URL` keys | `.env.example` **keys only** | `envconfig` |
| ADRs + `governs:` frontmatter | `docs/adr`, `docs/adrs`, `docs/decisions`, `adr/` | `adr` |
| Dev-server proxies | Angular `proxy.conf` | `proxy` |
| Bruno collections | repos tagged `bruno` | `bruno` |
| Graphify `graph.json` | `graphify-out/` | `graphify` (promote API/service-scale nodes only) |

Not implemented: Kubernetes, Helm, Terraform, AsyncAPI, GraphQL schemas, Maven/Gradle POM graphs, Docker, HTTP AST, OpenTelemetry. Add an extractor when a sibling actually has those files.

## Schema

Every graph is:

```json
{
  "version": 1,
  "generatedAt": "...",
  "nodes": [],
  "edges": [],
  "metadata": {}
}
```

**Node** `{ id, type, name, repository?, attrs? }`  
Stable ids: `type:slug` (`api:booking-v2`, `repository:frontend`). No UUIDs.

**Edge** `{ source, target, relationship, classification, confidence, evidence[], note? }`  
The graph never stores an inferred fact without evidence.

Classifications: `DECLARED` `OBSERVED` `EXTRACTED` `INFERRED` `AMBIGUOUS` `REJECTED`.

Relationships: `CONTAINS` `MEMBER_OF` `DEPENDS_ON` `CONSUMES` `PROVIDES` `PUBLISHES` `SUBSCRIBES` `USES` `GOVERNED_BY` `ROUTES`.

Prefer contract nodes over repo-to-repo edges:

```
application:frontend  CONSUMES  api:booking-v2
service:backend       PROVIDES  api:booking-v2
```

`DEPENDS_ON` between repositories is derived only after CONSUMES/PROVIDES exist.

## Inputs vs generated

| File | Role |
| --- | --- |
| `catalog/graph.yaml` | Committed declare / reject |
| `<clone>/.workspace/component.yaml` | Per-repo intent (keep small) |
| `.workspace/overrides.yaml` | Optional local overrides (not required) |
| `.workspace/generated/workspace-graph.json` | Generated. Gitignored. |

`reject:` survives rebuilds so extractors do not recreate known false positives.

## CLI

```bash
goat graph scan
goat graph build
goat graph validate
goat graph explain application:frontend api:booking-v2
goat graph neighbors api:booking-v2
goat graph path application:frontend database:booking-db
```

`explain` is the agent-facing command: classification, confidence, and pointers back to files — not source dumps.

## Adding an extractor

1. Implement `extract(ctx) -> ExtractBatch` (nodes, candidate edges with evidence).
2. Register it in `goat.graph.extract.default_extractors`.
3. Do **not** match across repos inside the extractor. Emit evidence; `correlate.py` joins tokens (env key `BOOKING_API_URL`, proxy `/booking`, OpenAPI paths).
4. Do not scan the whole tree unless the extractor needs one known filename.

Shards under `.workspace/generated/evidence.json` keep a per-extractor file list so a later incremental rebuild can rerun one repo without a new schema.

## Agent use

Ask the graph *where*, then open that sibling:

1. `goat graph explain traveler-web booking-v2`
2. `goat context --repo booking-service`
3. Read that repo's Graphify report / ADR / OpenAPI
4. Edit source

Do not treat `INFERRED` or `AMBIGUOUS` as confirmed facts. `REJECTED` means a human already said no.

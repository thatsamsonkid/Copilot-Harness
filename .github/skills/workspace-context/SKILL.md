---
name: workspace-context
description: Discover Graphify graphs, instruction files, feature notes/ADRs, and verify commands in sibling repos. Use for vague or low-context prompts, large monorepos, "where does X live?", or before implementing in a product repo. Prefer graphify query/path/explain, local AGENTS.md, and docs/features over grepping the whole tree.
---

# Workspace context

Product code lives in clones next to this harness (flat siblings or grouped folders such as `frontend/shop-web`). Those repos may already have Graphify output and their own Copilot instructions. The harness only discovers them.

## Commands

| User intent | Command |
| --- | --- |
| All enabled repos | `uv run harness context --format json` |
| One or more repos | `uv run harness context --repo frontend,backend --format json` |
| Ticket plus routing | `uv run harness prepare <KEY> --format json` (each `routing.repos[]` already includes `graphify`, `instructions`, `knowledge`, `tooling`) |

## Vague or low-context prompts

1. Run `harness context` (or use `prepare` if a Jira key is present).
2. For each cloned repo with `graphify.present`, read `graphify.report` (`GRAPH_REPORT.md`) before opening source files. Also skim `knowledge.files` (feature notes and ADRs).
3. For "how does A relate to B?", run the repo's `graphify.query_command` / `path_command` / `explain_command`.
4. If no graph exists, do **not** extract a whole monorepo. Say so, inspect instruction files, and ask which package or area to scope. Rebuild only if the user asks, preferably `graphify extract --code-only <path>`.
5. Ask which repo or Graphify community to use when routing is unclear.

## Standards

The harness does not own product patterns.

- Before editing a sibling, read its `instructions` files (`copilot-instructions.md`, `AGENTS.md`, path-specific `*.instructions.md`, skills).
- After edits, run that repo's `tooling.suggested_verify`. If it fails, fix or report. Do not skip it.
- Do not copy those files into the harness. Do not invent style rules that contradict them.
- Product knowledge stays in the sibling (`docs/features`, ADRs). If you added user-visible or non-obvious behavior, update or create a note there using `templates/feature-note.md`. Do not start a wiki in the harness.

## Hard rules

- Stay in the listed clone folders (including grouped paths). Never nest clones inside the harness.
- Do not grep a large monorepo as the first move when a graph or instruction file exists.
- Do not print `.env` or Jira tokens.
- If `graphify.stale` is true, say so and offer a *scoped* rebuild only after the user agrees.
- Do not hand-edit `tooling.generated` paths.

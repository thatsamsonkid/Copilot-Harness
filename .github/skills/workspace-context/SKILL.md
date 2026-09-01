---
name: workspace-context
description: Discover Graphify graphs, instruction files, feature notes/ADRs, and verify commands in sibling repos. Use for vague or low-context prompts, large monorepos, "where does X live?", or before implementing in a product repo. Prefer graphify query/path/explain, local AGENTS.md, and docs/features over grepping the whole tree.
---

# Workspace context

Product code lives in clones next to this goat (flat siblings or grouped folders such as `frontend/shop-web`). Those repos may already have Graphify output and their own Copilot instructions. The goat only discovers them.

## Commands

Run these from the goat repo. After `cd` into a sibling, use `uv run --project "$GOAT_ROOT" goat …` or `./scripts/goat.sh` — bare `uv run goat` cannot spawn from a product clone.

| User intent | Command |
| --- | --- |
| Open feature workspace | `uv run goat context --format json` (uses `GOAT_WORKSPACE` when a `.code-workspace` is open) |
| Which workspace is open | `uv run goat workspace current --format json` |
| One catalog workspace | `uv run goat context --workspace frontend --format json` |
| One or more repos | `uv run goat context --repo frontend,backend --format json` |
| Every enabled repo | `uv run goat context --all --format json` (only if the user asked for the full catalog) |
| Ticket plus routing | `uv run goat prepare <KEY> --format json` (each `routing.repos[]` already includes `graphify`, `instructions`, `knowledge`, `tooling`) |
| Local stack start plan | `uv run goat start --format json` (see the workspace-start skill). Saved sequences live in `workspaces/<id>.start.yml`. |
| Sibling / remote agent skills | `uv run goat skills list` then `skills lift` or `skills pull <url>` (see the skills-install skill). VS Code Agents does not scan multi-root child folders. |

## Vague or low-context prompts

1. Run `goat context` (or use `prepare` if a Jira key is present). Stay inside `workspace.repos`. Sibling clones that are only on disk are out of scope.
2. If `workspace_scope.detected` is false, do not treat every `parent_dir` clone as in scope. Ask which feature workspace to open, or pass `--workspace <id>`.
3. For each cloned repo with `graphify.present`, read `graphify.report` (`GRAPH_REPORT.md`) before opening source files. Also skim `knowledge.files` (feature notes and ADRs).
4. For "how does A relate to B?", run the repo's `graphify.query_command` / `path_command` / `explain_command`.
5. If no graph exists, do **not** extract a whole monorepo. Say so, inspect instruction files, and ask which package or area to scope. Rebuild only if the user asks, preferably `graphify extract --code-only <path>`.
6. Ask which repo or Graphify community to use when routing is unclear. Do not mention repos outside `workspace.repos`.

## Standards

The goat does not own product patterns.

- Before editing a sibling, read its `instructions` files (`copilot-instructions.md`, `AGENTS.md`, path-specific `*.instructions.md`, skills).
- If `language` / `languages[]` is set (typescript, python, java), load that `language_skill` before the first edit. Path-scoped goat rules live in `.github/instructions/<language>.instructions.md`.
- After edits, run that repo's `tooling.suggested_verify`. If it fails, fix or report. Do not skip it.
- Do not copy those files into the goat. Do not invent style rules that contradict them.
- Product knowledge stays in the sibling (`docs/features`, ADRs). If you added user-visible or non-obvious behavior, update or create a note there using `templates/feature-note.md`. Do not start a wiki in the goat.

## Hard rules

- Stay in the listed clone folders (including grouped paths). Never nest clones inside the goat.
- Do not flag, start, or plan repos that are not in the open feature workspace. Pass `--all` only when the user asked for the full catalog.
- Do not grep a large monorepo as the first move when a graph or instruction file exists.
- Do not print `.env` or Jira tokens.
- If `graphify.stale` is true, say so and offer a *scoped* rebuild only after the user agrees.
- Do not hand-edit `tooling.generated` paths.

## Related Copilot customizations

- TypeScript siblings: typescript skill or `/typescript`
- Python (goat or sibling): python skill or `/python`
- Java / Spring siblings: java skill or `/java`
- Local stack start: workspace-start skill or `/start-workspace`
- Sibling / remote agent skills: skills-install skill or `/skills-install`

---
name: new-workspace
description: Create a feature workspace; Copilot walks through id and repositories.yml projects
argument-hint: optional-id
tools: ['runCommands']
---

The user wants a new feature VS Code workspace. They may pass a slug as `${input:id:Workspace id (optional slug)}`.

Copilot collects the remaining params in chat, then runs the coboose CLI. Do **not** run interactive `coboose workspace create` (no TTY). Do **not** hand-edit `catalog/stack.yaml` or `workspaces/*.code-workspace`.

## Walkthrough

1. From the coboose repo (cwd = coboose folder; do not `cd` into a sibling), run `#tool:runCommands`:
   - `uv run coboose repos --format json`
   - `uv run coboose workspace list --format json`
   If `uv` is missing, run `./scripts/setup.sh`, then retry with `./scripts/coboose.sh`.
2. Show a numbered list of **enabled** `repositories.yml` projects: name, tags, description, `path` / `group` when organized, cloned or not.
3. Also list existing workspace ids so the user does not collide unless they mean to replace one.
4. Ask for anything still missing, one question at a time:
   - **id** — lowercase slug (`checkout`). Use `${input:id:Workspace id (optional slug)}` when it is a real slug; otherwise ask. Default a suggestion from their wording (`Checkout Flow` → `checkout-flow`).
   - **name** — default to a title-cased id.
   - **description** — optional; skip if they do not care.
   - **projects** — required. They may answer with numbers, names, ranges (`1-3`), `all`, or tags (`tag:ui`). Map that to repository `name` values from the repos JSON.
   - **include coboose** — default yes.
   - **Jira routing** (optional, only if they mention tickets/labels): `--match-projects`, `--match-labels`, `--keywords`.
5. If the id already exists, ask before replacing. Only then pass `--force`.
6. Restate the plan (id, name, folders, coboose yes/no) and wait for a short confirm unless they already said "just create it".
7. Run `#tool:runCommands` with `--no-prompt` and flags, for example:

```bash
uv run coboose workspace create <id> --projects frontend,backend --name "Checkout" --description "Cart flow" --no-prompt --format json
```

   Add `--tag`, `--no-include-coboose`, `--fallback`, or `--force` only when the user chose those.
8. From the CLI JSON, tell them:
   - catalog path and `workspace.file`
   - `open_command` (ask them to run it if those roots are not in this window)
   - any selected repo that is not cloned (`coboose clone --only …`)
   - that they can pin the boot sequence later with `coboose start --workspace <id> --save` (`workspaces/<id>.start.yml`)
9. Stop. Do not implement product code.

Never nest git clones inside this coboose repo. Never invent repository names that are not in `coboose repos`.

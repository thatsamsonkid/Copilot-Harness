---
name: new-workspace
description: Create a feature workspace; Copilot walks through id and repositories.yml projects
argument-hint: optional-id
tools: ['runCommands']
---

The user wants a new feature VS Code workspace. They may pass a slug as `${input:id:Workspace id (optional slug)}`.

Copilot collects the remaining params in chat, then runs the harness CLI. Do **not** run interactive `harness workspace create` (no TTY). Do **not** hand-edit `catalog/stack.yaml` or `workspaces/*.code-workspace`. Personal files belong under `workspaces/personal/` via `--personal`.

## Walkthrough

1. From the harness repo, run `#tool:runCommands`:
   - `uv run harness repos --format json`
   - `uv run harness workspace list --format json`
   If `uv` is missing, run `./scripts/setup.sh`, then retry with `./scripts/harness.sh`.
2. Show a numbered list of **enabled** `repositories.yml` projects: name, tags, description, `path` / `group` when organized, cloned or not.
3. Also list existing workspace ids so the user does not collide unless they mean to replace one.
4. Ask for anything still missing, one question at a time:
   - **kind** — **shared** (default: `catalog/stack.yaml` + `workspaces/<id>.code-workspace` for the team) or **personal** (local only under `workspaces/personal/`, gitignored, no catalog edit). If they say scratch, local, mine, or "don't commit it", use personal.
   - **id** — lowercase slug (`checkout`). Use `${input:id:Workspace id (optional slug)}` when it is a real slug; otherwise ask. Default a suggestion from their wording (`Checkout Flow` → `checkout-flow`).
   - **name** — default to a title-cased id.
   - **description** — optional; skip if they do not care.
   - **projects** — required. They may answer with numbers, names, ranges (`1-3`), `all`, or tags (`tag:ui`). Map that to repository `name` values from the repos JSON.
   - **include harness** — default yes.
   - **Jira routing** (optional, only if they mention tickets/labels, and only for **shared**): `--match-projects`, `--match-labels`, `--keywords`.
5. If the id already exists, ask before replacing. Only then pass `--force`.
6. Restate the plan (kind, id, name, folders, harness yes/no) and wait for a short confirm unless they already said "just create it".
7. Run `#tool:runCommands` with `--no-prompt` and flags, for example:

```bash
uv run harness workspace create <id> --projects frontend,backend --name "Checkout" --description "Cart flow" --no-prompt --format json
```

   Add `--personal` for a local-only workspace, or `--shared` to be explicit. Add `--tag`, `--no-include-harness`, `--fallback`, or `--force` only when the user chose those. Do not pass `--fallback` or Jira match flags with `--personal`.
8. From the CLI JSON, tell them:
   - catalog path and `workspace.file`
   - `open_command` (ask them to run it if those roots are not in this window)
   - any selected repo that is not cloned (`harness clone --only …`)
9. Stop. Do not implement product code.

Never nest git clones inside this harness repo. Never invent repository names that are not in `harness repos`.

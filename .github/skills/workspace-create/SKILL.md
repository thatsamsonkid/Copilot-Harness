---
name: workspace-create
description: Create a feature VS Code workspace by picking repositories.yml projects. Use for /new-workspace, Workspace Creator, "add a workspace", or mixing catalog repos. Run the compact --menu picker. Do not dump goat repos, goat commands, goat skills list, or goat context.
argument-hint: optional-id
---

# Workspace create

Chat collects an id and which `repositories.yml` projects to include. The CLI writes `catalog/stack.yaml` and a local `.code-workspace` file. Do not hand-edit those files. Do not run the interactive CLI from chat (no TTY).

This skill is only the picker. Ignore Jira, Figma, Bruno, Graphify, start plans, and the full CLI catalog unless the user asks for those next.

## Commands

Run these from the goat repo. After `cd` into a sibling, `uv run goat` cannot spawn — use `uv run --project "$GOAT_ROOT" goat …` or `./scripts/goat.sh`.

| User intent | Command |
| --- | --- |
| Compact picker (repos + existing ids) | `uv run goat workspace create --menu --format json` |
| Create after confirm | `uv run goat workspace create <id> --projects <names> --no-prompt --format json` |
| Create by tag | `uv run goat workspace create <id> --tag ui,api --no-prompt --format json` |

`--menu` is the only inventory command. It is `n`, `name`, `tags`, short `description`, `cloned`, existing workspace ids, and known tags. It does **not** include remotes, Graphify, knowledge dirs, skills, env, start files, or `goat commands`.

## Walkthrough

1. Run `--menu` from the goat folder. Do not also run `goat repos`, `goat catalog`, `goat workspace list`, `goat commands`, `goat skills list`, or `goat context`.
2. Show a compact numbered list from `projects[]`: `n. name` and tags. Include `description` only when it is short. Do not paste the raw JSON.
3. If `projects[]` has more than 12 entries, show `tags[]` first and ask whether to filter (`tag:ui`) or see the full numbered list.
4. Mention existing `workspaces[].id` so the user does not collide.
5. Ask for anything still missing, one question at a time:
   - **id** — lowercase slug. Suggest one from their wording (`Checkout Flow` → `checkout-flow`).
   - **projects** — required. Accept numbers, names, ranges (`1-3`), `all`, or `tag:<tag>`. Map those to `projects[].name`.
   - **name** — default to a title-cased id. Do not ask unless they care.
   - **description** — skip unless they offer one.
   - **include goat** — default yes. Do not ask.
6. Jira match flags (`--match-projects`, `--keywords`, …) only if they mention ticket routing.
7. If the id is already in `workspaces[]`, ask before `--force`.
8. Restate id + project names and wait for a short confirm unless they already said to create it.
9. Run `create_command` from the menu JSON (or the create row above) with `--no-prompt --format json`.
10. From the create JSON, report `workspace.file` and `open_command`. Mention `goat clone --only <name>` only for selected repos with `cloned: false`. Ignore the `skills` summary unless `conflicts` is non-empty. Stop.

## Hard rules

- Do not run `goat repos`, `goat catalog`, `goat workspace list`, `goat commands`, `goat skills list`, or `goat context` for this flow.
- Do not dump skills, CLI help, Graphify, or start-plan next steps.
- Do not implement product code.
- Never nest git clones inside this goat repo.
- Never invent repository names that are not in `--menu` `projects[]`.
- Never hand-edit `catalog/stack.yaml` or `workspaces/*.code-workspace`.

## Failures

| Symptom | What to tell them |
| --- | --- |
| `already exists` | Ask before passing `--force` |
| `Unknown project` / `Unknown repo` | Re-run `--menu` and use `projects[].name` |
| `Failed to spawn: goat` | Cwd is a sibling. Re-run from this repo or `uv run --project "$GOAT_ROOT" goat …` |
| Selected repo `cloned: false` | `uv run goat clone --only <name>` |

## Related Copilot customizations

- First-run setup: get-started skill or `/get-started`
- Open an existing starter: `goat workspace open <id>`
- Local stack start (after clones exist): workspace-start skill or `/start-workspace`
- Ticket routing: jira-cli skill or `/jira-ticket`

---
name: new-workspace
description: Create a feature workspace; Copilot walks through id and repositories.yml projects
argument-hint: optional-id
tools: ['runCommands']
---

The user wants a new feature VS Code workspace. They may pass a slug as `${input:id:Workspace id (optional slug)}`.

Load `.github/skills/workspace-create/SKILL.md`. Chat collects id and projects; the CLI writes the files.

Do **not** run interactive `goat workspace create` (no TTY). Do **not** hand-edit `catalog/stack.yaml` or `workspaces/*.code-workspace`.

## Walkthrough

1. From the goat repo (cwd = goat folder; do not `cd` into a sibling), run `#tool:runCommands`:

```bash
uv run goat workspace create --menu --format json
```

   If `uv` is missing, run `./scripts/setup.sh`, then retry with `./scripts/goat.sh`. Do **not** also run `goat repos`, `goat workspace list`, `goat commands`, `goat skills list`, or `goat context`.
2. Show a compact numbered list from `projects[]` (`n. name`, tags). If there are more than 12 projects, show `tags[]` first and ask whether to filter (`tag:ui`) or list all. Mention existing `workspaces[].id`. Do not paste the raw JSON.
3. Ask for anything still missing, one question at a time: **id** (use `${input:id:Workspace id (optional slug)}` when it is a real slug), then **projects** (numbers, names, ranges, `all`, or `tag:<tag>`). Default name from the id. Skip description unless they offer one. Include goat defaults yes.
4. If the id already exists, ask before `--force`.
5. Restate id + project names and wait for a short confirm unless they already said to create it.
6. Run `#tool:runCommands` with the menu `create_command`, for example:

```bash
uv run goat workspace create <id> --projects frontend,backend --no-prompt --format json
```

7. Report `workspace.file` and `open_command`. Mention `goat clone --only …` only for selected repos with `cloned: false`. Ignore the `skills` summary. Stop. Do not implement product code.

Never nest git clones inside this goat repo. Never invent repository names that are not in `--menu` `projects[]`.

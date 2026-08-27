# Copilot Harness

This repository is tooling only. Application code lives in **sibling git clones** next to this repo, never inside it.

## First-run and vague prompts

- First time in this repo, missing Jira auth, or "how do I set this up?": load `.github/skills/get-started/SKILL.md` and run `uv run harness init --format json`. Never collect the API token in chat.
- Vague, broad, or no-ticket prompts in a large workspace: load `.github/skills/workspace-context/SKILL.md` and run `uv run harness context --format json`. Read each cloned repo's Graphify `GRAPH_REPORT.md` before grepping.

## Default ticket workflow

When the user gives a Jira key or browse URL, load the **jira-cli** skill (`.github/skills/jira-cli/SKILL.md`) and follow it.

1. Run `uv run harness prepare <KEY> --format json` from this repo (or with `HARNESS_ROOT` set).
2. Use that CLI JSON as the only ticket source. It is already field-filtered. Do not ask Jira for more.
3. Tell the user to open `routing.open_command` so the feature workspace loads the right roots. Do not assume sibling repos are already in the current window.
4. If `routing.missing_repos` is non-empty, recommend `routing.clone_command`. Never `git clone` into this harness folder.
5. Write a plan covering impacted repos, likely files, risks, and tests. Do not implement until the user asks.

`harness` stdout is JSON by default. Read stdout. Errors are JSON on stderr with a non-zero exit code.

## Jira access (hard rules)

This workspace has **no Jira MCP server**. The API token must never enter the chat or a shell command. These rules apply even if the jira-cli skill is not loaded.

- Only talk to Jira through `uv run harness jira …`, `uv run harness prepare …`, or `uv run harness init` / `doctor`.
- Do **not** curl, fetch, or browse `*.atlassian.net` or `/rest/api/`.
- Do **not** read `.env`, print `env`, or expand `$JIRA_API_TOKEN` / `$JIRA_TOKEN`.
- Do **not** configure or call an MCP Jira tool.
- If credentials are missing, tell the user to edit `.env` locally. Never ask them to paste a token into chat.

## Repo layout

- Manifest: `repositories.yml` — every product repo (`name`, GitHub `url`, `tags`).
- Workspaces / Jira routing: `catalog/stack.yaml` — reference repos by name or tag.
- CLI: `src/harness` — clone, Jira basic auth, workspace generate/match, prepare, init, context.
- Feature workspaces: `workspaces/*.code-workspace` — multi-root; first folder is this harness.
- Secrets: `.env` (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`). Never commit tokens or print them.

## Commands

Prefer `uv` for Python. Run the CLI as `uv run harness <command>` (or `./scripts/harness.sh`). Jira command shapes live in the jira-cli skill. First-run lives in get-started. Graphify and repo standards live in workspace-context.

If `uv` is missing, run `./scripts/setup.sh`. Do not use pip to install this repo.

## Constraints

- Keep clones as siblings (`../<path>`). Do not add git submodules or nest repos here.
- Prefer the matched workspace repos. Only load extra roots when the ticket clearly needs them.
- After catalog edits, run `harness workspace generate`.
- When coding in a sibling repo, follow that repo's conventions. This harness does not override product architecture.
- Before editing a sibling, read the instruction files `harness context` lists for it (`AGENTS.md`, `.github/copilot-instructions.md`, path-specific instructions, skills).
- After editing a sibling, run that repo's `tooling.suggested_verify`. Do not skip a failing lint/test command from the product repo.
- Do not copy product standards into this harness. Do not rebuild a Graphify graph unless the user asked, and never extract an entire monorepo unprompted.

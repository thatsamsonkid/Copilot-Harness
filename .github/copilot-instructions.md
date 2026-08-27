# Copilot Harness

This repository is tooling only. Application code lives in **sibling git clones** next to this repo, never inside it.

## Default ticket workflow

When the user gives a Jira key or browse URL:

1. Run `uv run harness prepare <KEY> --format json` from this repo (or with `HARNESS_ROOT` set).
2. Use that CLI JSON as the only ticket source. It is already field-filtered. Do not ask Jira for more.
3. Tell the user to open `routing.open_command` so the feature workspace loads the right roots. Do not assume sibling repos are already in the current window.
4. If `routing.missing_repos` is non-empty, run or recommend `routing.clone_command`. Never `git clone` into this harness folder.
5. Write a plan covering impacted repos, likely files, risks, and tests. Do not implement until the user asks.

`harness` stdout is JSON by default. Read stdout. Errors are JSON on stderr with a non-zero exit code.

## Jira access (hard rules)

This workspace has **no Jira MCP server**. The API token must never enter the chat or a shell command.

- Only talk to Jira through `uv run harness jira …` or `uv run harness prepare …`.
- Do **not** curl, fetch, or browse `*.atlassian.net` or `/rest/api/`.
- Do **not** read `.env`, print `env`, or expand `$JIRA_API_TOKEN` / `$JIRA_TOKEN`.
- Do **not** configure or call an MCP Jira tool.
- If credentials are missing, tell the user to edit `.env` locally. Never ask them to paste a token into chat.

## Repo layout

- Manifest: `repositories.yml` — every product repo (`name`, GitHub `url`, `tags`).
- Workspaces / Jira routing: `catalog/stack.yaml` — reference repos by name or tag.
- CLI: `src/harness` — clone, Jira basic auth, workspace generate/match, prepare.
- Feature workspaces: `workspaces/*.code-workspace` — multi-root; first folder is this harness.
- Secrets: `.env` (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`). Never commit tokens or print them.

## Commands

Prefer `uv` for Python. Run the CLI as `uv run harness <command>` (or `./scripts/harness.sh`).

```bash
uv run harness prepare PROJ-123
uv run harness jira get PROJ-123
uv run harness jira context PROJ-123
uv run harness jira search 'project = PROJ AND status != Done'
uv run harness repos
uv run harness clone --only frontend,backend
uv run harness clone --tag ui
uv run harness workspace list
uv run harness workspace generate
uv run harness doctor
```

If `uv` is missing, run `./scripts/setup.sh`. Do not use pip to install this repo.

## Constraints

- Keep clones as siblings (`../<path>`). Do not add git submodules or nest repos here.
- Prefer the matched workspace repos. Only load extra roots when the ticket clearly needs them.
- After catalog edits, run `harness workspace generate`.
- When coding in a sibling repo, follow that repo's conventions. This harness does not override product architecture.

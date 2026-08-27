# Copilot Harness

This repository is tooling only. Application code lives in **sibling git clones** next to this repo, never inside it.

## Default ticket workflow

When the user gives a Jira key or browse URL:

1. Run `harness prepare <KEY> --format json` from this repo (or with `HARNESS_ROOT` set).
2. Use the JSON `issue` object as source of truth. If comments are empty and the ticket looks thin, run `harness jira context <KEY>`.
3. Tell the user to open `routing.open_command` so the feature workspace loads the right roots. Do not assume sibling repos are already in the current window.
4. If `routing.missing_repos` is non-empty, run or recommend `routing.clone_command`. Never `git clone` into this harness folder.
5. Write a plan covering impacted repos, likely files, risks, and tests. Do not implement until the user asks.

`harness` stdout is JSON by default. Read stdout. Errors are JSON on stderr with a non-zero exit code.

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

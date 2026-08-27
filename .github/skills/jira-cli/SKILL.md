---
name: jira-cli
description: Operate the local harness Jira CLI (uv run harness). Use when the user pastes a Jira key or browse URL, asks to fetch/search/comment on a ticket, run prepare, inspect Jira schema, or diagnose Jira auth. Do not curl Atlassian, read .env, print tokens, or use a Jira MCP server.
argument-hint: PROJ-123
---

# Jira CLI

This workspace talks to Jira Cloud only through the `harness` CLI. There is no Jira MCP server.

## Hard rules

- Run `uv run harness <command>` from the harness repo (or `./scripts/harness.sh`). If `uv` is missing, follow `docs/install-uv.md` (macOS/Linux: `./scripts/setup.sh`; Windows: `.\scripts\setup.ps1`).
- Default `--format` is `json`. Keep JSON. Read stdout. Errors are JSON on stderr with a non-zero exit.
- Treat CLI JSON as complete. It is already filtered by `catalog/stack.yaml` `jira.fields`. Do not ask Jira for more fields.
- Never curl, fetch, or browse `*.atlassian.net` or `/rest/api/`.
- Never read `.env`, print `env`, or expand `$JIRA_API_TOKEN` / `$JIRA_TOKEN`.
- Never configure or call a Jira MCP tool.
- If credentials are missing, tell the user to set URL/email in `.env` and run `uv run harness jira login` in their own terminal. Never ask them to paste a token into chat.
- `jira whoami` must not include a token. If it ever does, stop and do not repeat it.

## Parse the issue

Accept `PROJ-123` or a browse URL. The CLI extracts the key.

## Which command

| User intent | Command |
| --- | --- |
| Start work on a ticket (default) | `uv run harness prepare <KEY> --format json` |
| One issue, no routing | `uv run harness jira get <KEY>` |
| Issue plus comments | `uv run harness jira context <KEY>` |
| Comments only | `uv run harness jira comments <KEY>` |
| JQL search | `uv run harness jira search '<jql>'` |
| What Copilot is allowed to see | `uv run harness jira schema` |
| Auth check (no token in output) | `uv run harness jira whoami` |
| Store token in OS keychain | Tell them to run `uv run harness jira login` (or `--from-env`) themselves |
| Catalog / clones / Jira env | `uv run harness doctor` |
| Live Jira ping | `uv run harness doctor --ping-jira` |
| First-run / missing token | `uv run harness init` (see the get-started skill) |
| Graphs + repo instructions | `uv run harness context` (see the workspace-context skill) |

Prefer `prepare` over assembling get + match + clone yourself.

Do not pass `--clone-missing` unless the user asked to clone. If `routing.missing_repos` is set, show `routing.clone_command` and let them confirm. Never `git clone` into the harness folder.

## `prepare` JSON

Use these objects only:

- `issue` — allowlisted ticket fields (and comments when enabled)
- `routing.workspace_id`, `routing.reasons`, `routing.score`
- `routing.open_command` — tell the user to run this so sibling repos become workspace roots
- `routing.missing_repos` / `routing.clone_command`
- `routing.repos` — inspect only these folders unless the ticket clearly needs more
- `routing.repos[].graphify` / `instructions` / `tooling` — use these before grepping or inventing verify commands
- `next_steps`

If `routing.score` is `0` or reasons are only fallback, ask which workspace to open.

Do not assume sibling repos are already in the current window.

## After a successful fetch

This skill is the CLI contract, not an implementer.

1. Summarize from returned fields only. Do not invent custom fields.
2. Name the matched workspace and whether clones are missing.
3. Ask the user to run `routing.open_command` when those roots are not open.
4. If the user wants a plan, write one and stop. Do not edit product code until they ask.

## Auth and setup failures

| Symptom | What to do |
| --- | --- |
| Missing `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` | Tell the user to set URL/email in `.env` and run `uv run harness jira login` |
| 401 / 403 from the CLI | Tell them to rotate the Atlassian API token and run `uv run harness jira login` |
| Placeholder clone URLs | Tell them to edit `repositories.yml`; do not invent remotes |
| `uv` missing | `docs/install-uv.md` — macOS/Linux `setup.sh`, Windows `setup.ps1` |

## Related Copilot customizations

- Always-on rules: `.github/copilot-instructions.md`
- First-run setup: get-started skill or `/get-started`
- Vague / large-repo orientation: workspace-context skill or `/orient`
- Plan a ticket: Jira Planner agent or `/jira-ticket`
- Create a feature workspace: Workspace Creator agent or `/new-workspace`
- Implement an agreed plan: Implementer agent

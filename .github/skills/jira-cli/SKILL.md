---
name: jira-cli
description: Operate the local coboose Jira CLI (uv run coboose). Use when the user pastes a Jira key or browse URL, asks to fetch/search/comment on a ticket, run prepare, inspect Jira schema, or diagnose Jira auth. Do not curl Atlassian, read .env, print tokens, or use a Jira MCP server.
argument-hint: PROJ-123
---

# Jira CLI

This workspace talks to Jira Cloud only through the `coboose` CLI. There is no Jira MCP server.

## Hard rules

- Run `uv run coboose <command>` from the coboose repo (or `./scripts/coboose.sh` / `.\scripts\coboose.ps1`). If you already `cd`'d into a sibling, use `uv run --project "$COBOOSE_ROOT" coboose <command>` — bare `uv run coboose` cannot spawn there. If `uv` is missing, follow `docs/install-uv.md` (macOS/Linux: `./scripts/setup.sh`; Windows: `.\scripts\setup.ps1`).
- Default `--format` is `json`. Keep JSON. Read stdout. Errors are JSON on stderr with a non-zero exit.
- Treat CLI JSON as complete. It is already filtered by `catalog/stack.yaml` `jira.fields` and `jira.shapes`. Do not ask Jira for more fields.
- Never curl, fetch, or browse `*.atlassian.net` or `/rest/api/`.
- Never read `.env`, print `env`, or expand `$JIRA_API_TOKEN` / `$JIRA_TOKEN`.
- Never configure or call a Jira MCP tool.
- If credentials are missing, tell the user to set URL/email in `.env` and run `uv run coboose jira login` in their own terminal. Never ask them to paste a token into chat.
- `jira whoami` must not include a token. If it ever does, stop and do not repeat it.

## Parse the issue

Accept `PROJ-123` or a browse URL. The CLI extracts the key.

## Which command

| User intent | Command |
| --- | --- |
| Start work on a ticket (default) | `uv run coboose prepare <KEY> --format json` |
| One issue, no routing | `uv run coboose jira get <KEY>` |
| Issue plus comments | `uv run coboose jira context <KEY>` |
| Comments only | `uv run coboose jira comments <KEY>` |
| JQL search | `uv run coboose jira search '<jql>'` |
| My open issues | `uv run coboose jira mine` |
| What Copilot is allowed to see | `uv run coboose jira schema` |
| Auth check (no token in output) | `uv run coboose jira whoami` |
| Store token in OS keychain | Tell them to run `uv run coboose jira login` (or `--from-env`) themselves |
| Other declared secrets | `uv run coboose env list` then `uv run coboose env set NAME` in their terminal |
| Catalog / clones / Jira env | `uv run coboose doctor` |
| Live Jira ping | `uv run coboose doctor --ping-jira` |
| First-run / missing token | `uv run coboose init` (see the get-started skill) |
| Graphs + repo instructions | `uv run coboose context` (see the workspace-context skill) |
| Sibling git snapshot | `uv run coboose status` |
| Same branch in each sibling | `uv run coboose branch <KEY>` (add `--create` only if they asked) |
| Pause / resume a chat | `uv run coboose handoff write` / `latest` (see the handoff skill) |

Prefer `prepare` over assembling get + match + clone yourself.

Do not pass `--clone-missing` unless the user asked to clone. If `routing.missing_repos` is set, show `routing.clone_command` and let them confirm. Never `git clone` into the coboose folder.

## `prepare` JSON

Use these objects only:

- `issue` — allowlisted ticket fields (and comments when enabled)
- `routing.workspace_id`, `routing.reasons`, `routing.score`
- `routing.open_command` — tell the user to run this so sibling repos become workspace roots
- `routing.missing_repos` / `routing.clone_command`
- `routing.repos` — inspect only these folders unless the ticket clearly needs more
- `current_workspace` — the open window, when `COBOOSE_WORKSPACE` is set. If it differs from `routing.workspace_id`, tell the user to open `routing.open_command`
- `routing.repos[].graphify` / `instructions` / `tooling` — use these before grepping or inventing verify commands
- `routing.suggested_branch`
- `done_when` — stop condition (ticket AC + repo verify + coboose invariants)
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
| Missing `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` | Tell the user to set URL/email in `.env` and run `uv run coboose jira login` |
| 401 / 403 from the CLI | Tell them to rotate the Atlassian API token and run `uv run coboose jira login` |
| Placeholder clone URLs | Tell them to edit `repositories.yml`; do not invent remotes |
| `uv` missing | `docs/install-uv.md` — macOS/Linux `setup.sh`, Windows `setup.ps1` |
| `Failed to spawn: coboose` / no `pyproject.toml` | Cwd is a sibling. Re-run from the coboose folder, `uv run --project "$COBOOSE_ROOT" coboose …`, or `uv run coboose install` so `coboose` is on PATH |

## Related Copilot customizations

- Always-on rules: `.github/copilot-instructions.md`
- First-run setup: get-started skill or `/get-started`
- Vague / large-repo orientation: workspace-context skill or `/orient`
- Local stack start: workspace-start skill or `/start-workspace`
- Plan a ticket: Jira Planner agent or `/jira-ticket`
- Figma frames: figma-cli skill or `/figma-frame`
- Bruno collections: bruno-cli skill or `/bruno`
- Create a feature workspace: Workspace Creator agent or `/new-workspace`
- Implement an agreed plan: Implementer agent
- Review a diff: Reviewer agent or `/review`
- Pause / resume: handoff skill or `/handoff`
- Sibling / remote agent skills: skills-install skill or `/skills-install`

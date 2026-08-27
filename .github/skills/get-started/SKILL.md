---
name: get-started
description: Walk a new user through harness setup (Jira email, API token, repositories.yml, clones). Use when someone is first opening the harness, asks how to create an Atlassian token, or auth/doctor is failing. Never read .env, never ask for the token in chat, never use a Jira MCP server.
---

# Get started

This skill is the first-run contract. Secrets stay in `.env`. Chat only sees `harness init` / `harness doctor` JSON.

## Commands

| User intent | Command |
| --- | --- |
| First-run checklist | `uv run harness init --format json` |
| Fill missing values in a local terminal | Tell them to run `uv run harness init --interactive` themselves |
| Recheck catalog, clones, Jira env | `uv run harness doctor` |
| Live Jira ping | `uv run harness doctor --ping-jira` or `uv run harness jira whoami` |

If `uv` is missing, `./scripts/setup.sh` then `./scripts/harness.sh`.

## Walkthrough order

1. `.env` exists (copy from `.env.example` if needed).
2. `JIRA_BASE_URL` — `https://your-domain.atlassian.net`.
3. `JIRA_EMAIL` — the Atlassian account email that will own the token.
4. `JIRA_API_TOKEN` — they create it using `docs/jira-api-token.md` and paste it into `.env` only.
5. `repositories.yml` — replace `YOUR_ORG` placeholder remotes.
6. `./scripts/clone-repos.sh` then `uv run harness workspace generate`.

## Hard rules

- Never read `.env`, print `env`, or expand `$JIRA_API_TOKEN` / `$JIRA_TOKEN`.
- Never ask the user to paste a token or password into chat.
- Never curl `*.atlassian.net`.
- Never configure or call a Jira MCP tool.
- `init --interactive` is for their terminal, not for Copilot to drive with visible prompts.

## Failures

| Symptom | What to tell them |
| --- | --- |
| Missing Jira keys | Edit `.env` using `docs/jira-api-token.md` |
| 401 / 403 | Rotate the token on the Atlassian page and update `.env` |
| Placeholder clone URLs | Edit `repositories.yml`; do not invent remotes |
| `whoami` ever includes a token | Stop. Treat it as a leak. |

After `ready` is true, point them at `/jira-ticket` or `/orient`.

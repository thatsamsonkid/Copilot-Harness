---
name: get-started
description: Walk a new user through harness setup (install uv on macOS or Windows, Jira email, API token in the OS keychain, repositories.yml, clones). Use when someone is first opening the harness, uv is missing, asks how to create an Atlassian token, or auth/doctor is failing. Never read .env, never ask for the token in chat, never use a Jira MCP server.
---

# Get started

This skill is the first-run contract. Site URL and email stay in `.env`. The API token stays in the OS keychain. Chat only sees `harness init` / `harness doctor` JSON.

## Commands

| User intent | Command |
| --- | --- |
| Check uv | `uv --version` |
| First-run checklist | `uv run harness init --format json` |
| Fill missing values in a local terminal | Tell them to run `uv run harness init --interactive` or `uv run harness jira login` themselves |
| Recheck catalog, clones, Jira env | `uv run harness doctor` |
| Live Jira ping | `uv run harness doctor --ping-jira` or `uv run harness jira whoami` |

## Walkthrough order

1. Confirm `uv` is installed. Run `uv --version`. If that fails, stop and use `docs/install-uv.md`:
   - macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh` then `./scripts/setup.sh`
   - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` then `.\scripts\setup.ps1`
   - Linux: same curl command as macOS, then `./scripts/setup.sh`
   Do **not** tell a Windows user to run `setup.sh`. Tell them to open a new terminal after install so PATH updates.
2. `.env` exists (copy from `.env.example` if needed).
3. `JIRA_BASE_URL` — `https://your-domain.atlassian.net`.
4. `JIRA_EMAIL` — the Atlassian account email that will own the token.
5. `JIRA_API_TOKEN` — they create it using `docs/jira-api-token.md` and store it with `uv run harness jira login` (macOS Keychain or Windows Credential Manager). Use `keychain_guide.macos` or `keychain_guide.windows` from `harness init` for GUI steps. Do not put it in chat. `.env` is only a fallback.
6. `repositories.yml` — replace `YOUR_ORG` placeholder remotes.
7. `./scripts/clone-repos.sh` then `uv run harness workspace generate`.

## Hard rules

- Never read `.env`, print `env`, or expand `$JIRA_API_TOKEN` / `$JIRA_TOKEN`.
- Never ask the user to paste a token or password into chat.
- Never curl `*.atlassian.net`.
- Never configure or call a Jira MCP tool.
- `init --interactive` is for their terminal, not for Copilot to drive with visible prompts.

## Failures

| Symptom | What to tell them |
| --- | --- |
| `uv` missing | `docs/install-uv.md` — macOS/Linux `setup.sh`, Windows `setup.ps1` |
| Missing Jira keys | Edit `.env` for URL/email (`docs/jira-api-token.md`) and run `uv run harness jira login` |
| 401 / 403 | Rotate the token on the Atlassian page and run `uv run harness jira login` again |
| Placeholder clone URLs | Edit `repositories.yml`; do not invent remotes |
| `whoami` ever includes a token | Stop. Treat it as a leak. |

After `ready` is true, point them at `/jira-ticket` or `/orient`.

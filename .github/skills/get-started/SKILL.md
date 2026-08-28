---
name: get-started
description: Walk a new user through coboose setup (install uv on macOS or Windows, Jira email, API token in the OS keychain, repositories.yml, clones). Use when someone is first opening the coboose, uv is missing, asks how to create an Atlassian token, or auth/doctor is failing. Never read .env, never ask for the token in chat, never use a Jira MCP server.
---

# Get started

This skill is the first-run contract. Site URL and email stay in `.env`. The API token stays in the OS keychain. Chat only sees `coboose init` / `coboose doctor` JSON.

## Commands

Run these from the coboose repo. After `cd` into a sibling, `uv run coboose` cannot spawn — use `uv run --project "$COBOOSE_ROOT" coboose …` or `./scripts/coboose.sh`.

| User intent | Command |
| --- | --- |
| Check uv | `uv --version` |
| First-run checklist | `uv run coboose init --format json` |
| Fill missing values in a local terminal | Tell them to run `uv run coboose init --interactive` or `uv run coboose jira login` themselves |
| Recheck catalog, clones, Jira env | `uv run coboose doctor` |
| List declared env/secrets (no values) | `uv run coboose env list` |
| Store a declared secret | Tell them to run `uv run coboose env set NAME` themselves |
| Live Jira ping | `uv run coboose doctor --ping-jira` or `uv run coboose jira whoami` |
| Live Figma ping (optional) | `uv run coboose doctor --ping-figma` or `uv run coboose figma whoami` |

## Walkthrough order

1. Confirm `uv` is installed. Run `uv --version`. If that fails, stop and use `docs/install-uv.md`:
   - macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh` then `./scripts/setup.sh`
   - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` then `.\scripts\setup.ps1`
   - Linux: same curl command as macOS, then `./scripts/setup.sh`
   Do **not** tell a Windows user to run `setup.sh`. Tell them to open a new terminal after install so PATH updates.
2. `.env` exists (copy from `.env.example` if needed).
3. `JIRA_BASE_URL` — `https://your-domain.atlassian.net`.
4. `JIRA_EMAIL` — the Atlassian account email that will own the token.
5. `JIRA_API_TOKEN` — they create it using `docs/jira-api-token.md` and store it with `uv run coboose jira login` (macOS Keychain or Windows Credential Manager). Use `keychain_guide.macos` or `keychain_guide.windows` from `coboose init` for GUI steps. Do not put it in chat. `.env` is only a fallback.
6. Optional Figma: they create a personal access token using `docs/figma-access-token.md` and store it with `uv run coboose figma login`. Skip this if the team does not use Figma.
7. Any other `env.variables` row from `coboose init` / `catalog/env.yaml` where `ok` is false. Non-secrets: edit `.env`. Secrets: `uv run coboose env set NAME` in their terminal. Do not put values in `.code-workspace` files.
8. `repositories.yml` — replace `YOUR_ORG` placeholder remotes.
9. `./scripts/clone-repos.sh` then `uv run coboose workspace generate`. `setup.sh` / `setup.ps1` already end by running `coboose init`.

## Hard rules

- Never read `.env`, print `env`, or expand `$JIRA_API_TOKEN` / `$JIRA_TOKEN` / `$FIGMA_ACCESS_TOKEN`.
- Never ask the user to paste a token or password into chat.
- Never curl `*.atlassian.net` or `api.figma.com`.
- Never configure or call a Jira or Figma MCP tool.
- `init --interactive` is for their terminal, not for Copilot to drive with visible prompts.

## Failures

| Symptom | What to tell them |
| --- | --- |
| `uv` missing | `docs/install-uv.md` — macOS/Linux `setup.sh`, Windows `setup.ps1` |
| Missing Jira keys | Edit `.env` for URL/email (`docs/jira-api-token.md`) and run `uv run coboose jira login` |
| Missing Figma token | Run `uv run coboose figma login` (`docs/figma-access-token.md`). Optional. |
| 401 / 403 | Rotate the token on the Atlassian page and run `uv run coboose jira login` again |
| Placeholder clone URLs | Edit `repositories.yml`; do not invent remotes |
| `whoami` ever includes a token | Stop. Treat it as a leak. |
| `Failed to spawn: coboose` | Cwd is a sibling clone. Re-run from this repo or `uv run --project "$COBOOSE_ROOT" coboose …` |

After `ready` is true, point them at `/jira-ticket` or `/orient`.

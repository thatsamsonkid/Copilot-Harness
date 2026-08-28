---
name: get-started
description: First-run walkthrough for uv (macOS/Windows), Jira email, API token, repos, and workspace setup
agent: agent
---

The user is setting up this Copilot harness for the first time, or something is not working. Load `.github/skills/get-started/SKILL.md` and follow it.

1. Run `#tool:runCommands` with `uv --version`. If that fails, do **not** guess. Open `docs/install-uv.md` and give the install command for the user's OS (macOS vs Windows vs Linux). macOS/Linux: `./scripts/setup.sh`. Windows: `.\scripts\setup.ps1`. Tell them to open a new terminal after install.
2. Once `uv` works, from the harness repo (do not `cd` into a sibling) run `uv run harness init --format json`. If cwd is already a product clone, use `uv run --project "$HARNESS_ROOT" harness init --format json`.
3. Walk the user through every `steps` entry where `ok` is false. Use `docs/install-uv.md` for uv and `docs/jira-api-token.md` for token creation.
4. Never ask them to paste `JIRA_API_TOKEN` into chat. Tell them to set URL/email in `.env` and run `uv run harness jira login` (or `uv run harness init --interactive`) in their own terminal. The token goes in macOS Keychain or Windows Credential Manager.
5. After they say they stored the token, run `uv run harness doctor --ping-jira --format json` and `uv run harness jira whoami --format json`.
6. If repository URLs are still placeholders, tell them to edit `repositories.yml` and then `./scripts/clone-repos.sh`.
7. Finish with `harness workspace generate` and tell them they can run `/jira-ticket PROJ-123` or `/orient` next.

Do not read `.env`. Do not curl Atlassian. Do not configure a Jira MCP server.

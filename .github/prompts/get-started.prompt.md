---
name: get-started
description: First-run walkthrough for Jira email, API token, repos, and workspace setup
agent: agent
---

The user is setting up this Copilot harness for the first time, or something is not working. Load `.github/skills/get-started/SKILL.md` and follow it.

1. From the harness repo, run `#tool:runCommands` with `uv run harness init --format json`.
2. If `uv` is missing, run `./scripts/setup.sh`, then retry with `./scripts/harness.sh init --format json`.
3. Walk the user through every `steps` entry where `ok` is false. Use `docs/jira-api-token.md` for token creation.
4. Never ask them to paste `JIRA_API_TOKEN` into chat. Tell them to edit `.env` locally, or to run `uv run harness init --interactive` in their own terminal.
5. After they say they filled `.env`, run `uv run harness doctor --ping-jira --format json` and `uv run harness jira whoami --format json`.
6. If repository URLs are still placeholders, tell them to edit `repositories.yml` and then `./scripts/clone-repos.sh`.
7. Finish with `harness workspace generate` and tell them they can run `/jira-ticket PROJ-123` or `/orient` next.

Do not read `.env`. Do not curl Atlassian. Do not configure a Jira MCP server.

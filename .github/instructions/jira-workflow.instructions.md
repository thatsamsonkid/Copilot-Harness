---
name: Jira ticket workflow
description: How to pull Jira context and choose a feature workspace
applyTo: "**"
---

Jira access is CLI-only. There is no Jira MCP server in this workspace. Load `.github/skills/jira-cli/SKILL.md` for commands, flags, and output shapes.

- Run `uv run goat prepare <KEY> --format json` unless the user asked for a narrower `jira` subcommand.
- The CLI returns a field allowlist from `catalog/stack.yaml` (`jira.fields`). Treat that JSON as complete. Do not request additional Jira fields.
- Never curl Atlassian URLs, never read `.env`, never print `JIRA_API_TOKEN`, and never ask the user to paste credentials. Missing tokens: tell them to run `uv run goat jira login`.
- If auth fails, tell the user to set values in `.env` themselves.

Parse issue keys from either `PROJ-123` or a browse URL. Prefer `prepare` over assembling get/match/clone yourself.

When planning from a ticket, cite the issue key, status, components, labels, and the matched workspace id. If routing confidence is low (score 0 or only fallback reasons), ask which workspace to open. New tickets should follow `templates/jira-ticket.md` (`## Acceptance Criteria` checkboxes; Figma frames listed by role, not a bare page link). To draft one from notes, use `/prepare-jira` — it writes a gitignored file under `jira-tickets/` for copy-paste. The CLI cannot create the issue.

If `routing.repos` include Graphify reports or instruction files, read those before searching the sibling tree. Product standards stay in the sibling repo.

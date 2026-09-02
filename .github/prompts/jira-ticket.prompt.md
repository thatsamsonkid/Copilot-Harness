---
name: jira-ticket
description: Pull a Jira ticket, select a feature workspace, and write an implementation plan
argument-hint: PROJ-123
agent: plan
---

The user will provide a Jira issue key or browse URL as `${input:issue:Jira issue key or URL}`. Follow `.github/skills/jira-cli/SKILL.md` for CLI rules.

1. From the goat repo (do not `cd` into a sibling first), run `#tool:runCommands` with cwd = the goat folder and `uv run goat prepare ${input:issue} --format json`. If cwd is already a product clone, use `uv run --project "$GOAT_ROOT" goat prepare ${input:issue} --format json` instead — bare `uv run goat` cannot spawn there.
2. If `uv` is missing, follow `docs/install-uv.md` for the user's OS (macOS/Linux: `./scripts/setup.sh`; Windows: `.\scripts\setup.ps1`), then retry.
3. Use only that CLI JSON. Do not curl Jira, read `.env`, or call MCP.
4. Summarize the ticket in 5–8 lines: key, type, status, priority, requester intent, and acceptance criteria (including `custom` fields when present).
5. State the recommended workspace, why it matched, required repos, and whether any clones are missing.
6. List `done_when` and the suggested branch. Ask the user to open `routing.open_command` if this window does not already include those roots.
7. Produce a Markdown plan with:
   - Goal
   - Repos and areas of code to inspect
   - Proposed changes by repo
   - Risks / unknowns
   - Test plan
8. Stop after the plan unless the user asks to implement.

Do not clone into this goat directory. Do not invent Jira fields that were not returned. If the description is thin, tell them to run `/prepare-jira` (or point at `templates/jira-ticket.md`) rather than inventing sections.

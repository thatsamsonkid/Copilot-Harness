---
name: jira-ticket
description: Pull a Jira ticket, select a feature workspace, and write an implementation plan
argument-hint: PROJ-123
agent: plan
---

The user will provide a Jira issue key or browse URL as `${input:issue:Jira issue key or URL}`.

1. From the harness repo, run `#tool:runCommands` with `uv run harness prepare ${input:issue} --format json`.
2. If `uv` is missing, run `./scripts/setup.sh`, then retry with `./scripts/harness.sh prepare ${input:issue} --format json`.
3. Use only that CLI JSON. Do not curl Jira, read `.env`, or call MCP.
3. Summarize the ticket in 5–8 lines: key, type, status, priority, requester intent, and acceptance criteria (including `custom` fields when present).
4. State the recommended workspace, why it matched, required repos, and whether any clones are missing.
5. Ask the user to open `routing.open_command` if this window does not already include those roots.
6. Produce a Markdown plan with:
   - Goal
   - Repos and areas of code to inspect
   - Proposed changes by repo
   - Risks / unknowns
   - Test plan
7. Stop after the plan unless the user asks to implement.

Do not clone into this harness directory. Do not invent Jira fields that were not returned.

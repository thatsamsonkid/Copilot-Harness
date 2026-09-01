---
name: jira-ticket
description: Plan work from a Jira issue key or browse URL via goat prepare. Use when the user runs /jira-ticket, pastes PROJ-123 for an implementation plan, or asks to pull a ticket and choose a feature workspace. Follow the jira-cli skill for every Jira call. Do not curl Atlassian, read .env, print tokens, or use a Jira MCP server.
argument-hint: PROJ-123
---

# Jira ticket plan

This skill is the planning workflow for one ticket. CLI rules, flags, and JSON shapes live in `.github/skills/jira-cli/SKILL.md`. Load that skill before any `goat` Jira command.

The issue key is the text after `/jira-ticket` (for example `PROJ-123` or a browse URL). If none is present, ask for one. Do not open a VS Code input form.

## Workflow

1. From the goat repo (do not `cd` into a sibling first), run `uv run goat prepare <KEY> --format json`. If cwd is already a product clone, use `uv run --project "$GOAT_ROOT" goat prepare <KEY> --format json` instead — bare `uv run goat` cannot spawn there (`Failed to spawn: goat`).
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

Do not clone into this goat directory. Do not invent Jira fields that were not returned. Do not pass `--clone-missing`.

## Related Copilot customizations

- CLI contract: jira-cli skill or `/jira-cli`
- First-run setup: get-started skill or `/get-started`
- Vague / large-repo orientation: workspace-context skill or `/orient`
- Implement an agreed plan: Implementer agent
- Review a diff: Reviewer agent or `/review`

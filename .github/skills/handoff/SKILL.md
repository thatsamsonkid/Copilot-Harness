---
name: handoff
description: Write or resume a Copilot session note under handoffs/ using goat status. Use when the user says they are stopping, switching chats, handing off, or asking what they were last doing. Never store secrets or .env values in the note.
argument-hint: PROJ-123
---

# Session handoff

Handoff notes live in this goat (`handoffs/`), not in product repos. They are gitignored.

## Commands

| User intent | Command |
| --- | --- |
| Snapshot siblings | `uv run goat status --format json` (open workspace only) |
| Which workspace is open | `uv run goat workspace current --format json` |
| Write a note | `uv run goat handoff write --issue <KEY> --note "<resume in one paragraph>" --format json` |
| Resume | `uv run goat handoff latest --format json` |
| List notes | `uv run goat handoff list --format json` |
| Ticket context | `uv run goat prepare <KEY> --format json` |

## Write

1. Run `goat status`. Stay inside `workspace.repos`. Do not list sibling clones that are only on disk.
2. If a Jira key is in the conversation, include `--issue`.
3. `--note` is what the next chat should do first. Include branch names, dirty siblings, and open questions. Do not paste ticket descriptions or tokens.
4. Tell the user the `relative` path. Do not commit the file unless they ask.

## Resume

1. Run `goat handoff latest`.
2. Refresh with `goat status`.
3. If the note has an issue key, run `goat prepare <KEY>` and treat `done_when` as the remaining stop condition.
4. Open the feature `.code-workspace` if `cwd_hint.kind` is `sibling` or `other`.

## Hard rules

- Do not read `.env` or print tokens.
- Do not write product architecture into the note. Point at sibling `docs/features` / Graphify instead.
- Do not nest clones inside the goat.

---
name: handoff
description: Save or resume a session note so the next chat does not re-fetch the world
argument-hint: PROJ-123
agent: agent
---

The user wants to pause, switch chats, or resume prior work. Load `.github/skills/handoff/SKILL.md`.

If they are **saving**:

1. Run `#tool:runCommands` with `uv run harness status --format json`.
2. Write one paragraph of resume notes (dirty siblings, branch names, what is left). No secrets.
3. Run `uv run harness handoff write --issue ${input:issue:} --note "<paragraph>" --format json` (omit `--issue` if there is no key).
4. Tell them the `relative` path and that the file is gitignored.

If they are **resuming** or did not say write:

1. Run `uv run harness handoff latest --format json`. If none exists, say so and run `status` instead.
2. Refresh `uv run harness status --format json`.
3. If there is a Jira key, run `uv run harness prepare <KEY> --format json` and list unchecked `done_when` items.
4. Ask them to open the feature workspace when `cwd_hint` says this window is a single folder.

Do not implement. Do not read `.env`.

---
name: start-workspace
description: Plan and start every local app in the current feature workspace
argument-hint: optional workspace id or repo names
agent: agent
---

The user wants to run the local stack (Java, Angular, Node, or mixed) for the open feature workspace. Load `.github/skills/workspace-start/SKILL.md` and follow it.

1. Run `#tool:runCommands` with `uv run harness start --format json` (add `--workspace <id>` or `--repo <names>` when the user named them).
2. Summarize the plan: start order, command, port hints, proxy files, and blocked items.
3. Start backends first, one process at a time. Wait until each is listening. If `port_hint` is wrong or missing, read the startup logs for the live port.
4. Rewrite Angular / frontend proxy targets to those live local URLs in the sibling working tree. Do not commit that change unless the user asked.
5. Start frontends. Report name, live port, and URL for each running app.
6. Do not start docker compose or invent a process supervisor. `harness start` is a plan only.

If a repo is not cloned or has no start command, stop that item and say what is missing. Do not nest clones inside the harness.

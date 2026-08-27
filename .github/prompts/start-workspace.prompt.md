---
name: start-workspace
description: Plan and start every local app in the current feature workspace
argument-hint: optional workspace id or repo names
agent: agent
---

The user wants to run the local stack (Java, Angular, Node, or mixed) for the open feature workspace. Load `.github/skills/workspace-start/SKILL.md` and follow it.

1. Run `#tool:runCommands` with `uv run harness start --format json` (add `--workspace <id>` or `--repo <names>` when the user named them).
2. Summarize the plan: start order, command, port hints, proxy files, and blocked items.
3. Start backends first, one process at a time, **one VS Code terminal per app**. If a terminal already exists for that repo (same `cwd` / start command), reuse it and read its log. Otherwise open a **new** terminal in that repo’s folder. Never start a second long-running app in a busy terminal.
4. Wait until each is listening. If `port_hint` is wrong or missing, read that terminal’s startup logs for the live port.
5. Rewrite Angular / frontend proxy targets to those live local URLs in the sibling working tree. Do not commit that change unless the user asked.
6. Start frontends the same way (new or reused terminal per app). Report name, live port, URL, and which terminal for each running app.
7. Do not start docker compose or invent a process supervisor. `harness start` is a plan only.

If a repo is not cloned or has no start command, stop that item and say what is missing. Do not nest clones inside the harness.

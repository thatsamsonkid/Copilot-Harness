---
name: goat-plan
description: Write a detailed implementation plan into plans/ that a lower-context model can execute
argument-hint: PROJ-123
agent: agent
---

The user wants an implementation plan written to a file, usually for another (often smaller) model or agent to execute later. Load `.github/skills/planning/SKILL.md` and follow it.

1. If an issue key like `${input:issue:}` is present, run `uv run goat prepare <KEY> --format json` and plan against `routing.repos`. Otherwise run `uv run goat context --format json` and stay inside `workspace.repos`.
2. Read each matched repo's Graphify `GRAPH_REPORT.md` and instruction files before naming file paths or conventions. Verify every path you name.
3. Write the plan to `plans/<YYYY-MM-DD>-<key-or-slug>.plan.md` starting from `templates/plan.md`. Assume the executor has only the plan file and the repo checkouts — restate all requirements, make every decision, and give each step exact files, symbols, commands, expected results, and a verify check.
4. Copy `done_when` into the plan when there is a ticket. Include an out-of-scope section.
5. Tell the user the plan's relative path and that it is gitignored.

Do not implement. Do not read `.env` or print tokens.

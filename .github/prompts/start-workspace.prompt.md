---
name: start-workspace
description: Plan and start every local app in the current feature workspace
argument-hint: optional workspace id or repo names
agent: agent
---

The user wants to run the local stack (Java, Angular, Node, or mixed) for the open feature workspace. Load `.github/skills/workspace-start/SKILL.md` and follow it.

1. Run `#tool:runCommands` with cwd = the harness workspace folder (first root, named `harness`) and `uv run harness start --format json` (add `--workspace <id>` or `--repo <names>` when the user named them). Do not `cd` into a product repo first. If cwd is already a sibling, use `uv run --project "$HARNESS_ROOT" harness start --format json` or `./scripts/harness.sh start --format json` (Windows: `.\scripts\harness.ps1`). Bare `uv run harness` cannot spawn from a sibling.
2. If `plan_source` is `saved`, follow that sequence. If it is `discovered` and the order looks right, save it once with `uv run harness start --workspace <id> --save --format json` so later starts skip rediscovery (`workspaces/<id>.start.yml`).
3. Summarize the plan: start order, `run_via`, command, port hints, proxy files, launch configuration names / env keys, and blocked items. Do not read `.vscode/launch.json` or `.env`.
4. Start backends first, one process at a time, **one VS Code terminal per app**. If `run_via` is `harness`, run `copilot_command` (`uv run --project "$HARNESS_ROOT" harness start run --repo <name>`) from the harness cwd — the CLI starts the process in the repo folder. If `run_via` is `vscode`, use **Run Without Debugging** on the named launch configuration (not Debug unless asked). If `run_via` is `terminal`, run `command` as usual. If a terminal already exists for that repo, reuse it and read its log. Never start a second long-running app in a busy terminal.
5. Wait until each is listening. If `port_hint` is wrong or missing, read that terminal’s startup logs for the live port.
6. Rewrite Angular / frontend proxy targets to those live local URLs in the sibling working tree. Do not commit that change unless the user asked.
7. Start frontends the same way (new or reused terminal per app). Report name, live port, URL, and which terminal for each running app.
8. Do not start docker compose or invent a process supervisor. `harness start` is a plan only. Do not rewrite a saved plan unless the user asked or the workspace repos / commands changed. Never reconstruct launch env or args in the shell.

If a repo is not cloned or has no start command, stop that item and say what is missing. Do not nest clones inside the harness.

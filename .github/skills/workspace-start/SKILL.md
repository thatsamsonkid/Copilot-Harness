---
name: workspace-start
description: Plan and start local apps in the current feature workspace (Java, Angular, Node). Use when the user wants to run the stack, start services, wire Angular proxies to local backends, or asks how to boot every repo. Discover with coboose start; start one process at a time. Do not launch everything in parallel. Never read launch.json or reconstruct env/args.
---

# Workspace start

The coboose does **not** own product start scripts. `coboose start` inspects sibling clones and prints a plan. You start processes one at a time so real ports and proxy rewrites can be applied after each backend is up.

A workspace start sequence rarely changes. After the first good plan, save it next to the workspace file as `workspaces/<id>.start.yml` (or `workspaces/personal/<id>.start.yml`). Later `coboose start --workspace <id>` prefers that file over rediscovery. Live clone status, proxy files, and compose markers are still inspected. Do not put `start:` on `repositories.yml` entries.

Java apps often keep args and environment variables in `.vscode/launch.json`. Those values must not enter chat. The plan only lists configuration names and env **keys**. Start those apps with `coboose start run` or VS Code **Run Without Debugging** — not by reading `launch.json` and not by forcing Debug.

## Commands

| User intent | Command |
| --- | --- |
| Plan for every enabled repo | `uv run coboose start --format json` |
| Plan for the open feature workspace | `uv run coboose start --workspace <id> --format json` |
| Pin the current sequence next to the workspace | `uv run coboose start --workspace <id> --save --format json` |
| Rediscover and overwrite the saved plan | `uv run coboose start --workspace <id> --refresh --save --format json` |
| One or more repos | `uv run coboose start --repo frontend,backend --format json` |
| Human-readable plan | `uv run coboose start --workspace <id> --format markdown` |
| Start one repo with launch.json env/args (no leak) | `uv run coboose start run --repo <name>` |
| Preview that run (keys + redacted `exec_command`) | `uv run coboose start run --repo <name> --dry-run --format json` |
| Inspect one repo's launch env (keys + collisions) | `uv run coboose start env --repo <name> --format json` |
| Apply that env in a dedicated terminal | `uv run coboose start env --repo <name> --shell` |

`coboose start` (no `run`) never launches processes. Do not invent a second supervisor. `--save` requires `--workspace` and writes the full workspace sequence; do not combine it with `--repo`.

`start run --dry-run` prints `exec_command` with launch `args` / `vmArgs` replaced by `<redacted>`, plus `arg_count` and `vm_arg_count`. Use that to confirm extras were applied. Values stay hidden.

## How to run the CLI

`uv run coboose` only works when the process **cwd is this coboose repo** (`pyproject.toml` / `uv.lock`). Sibling product clones do not have that project. If you `cd` into a repo (or set the terminal/`runCommands` cwd there) uv fails with **Failed to spawn: `coboose`**.

Always do one of:

1. Keep cwd on the coboose root (first workspace folder, named `coboose`). Do not `cd` before this command.
2. `uv run --project "$COBOOSE_ROOT" coboose start --format json` from any cwd (same `--project` form for `start run`)
3. `./scripts/coboose.sh start --format json` or `.\scripts\coboose.ps1 start --format json` using the coboose-root path

`coboose start` JSON includes `invoke.command`, `invoke.cwd`, and `invoke.script` for the cwd-safe form. App terminals stay in each service `path`. Never run `uv run coboose` from those terminals.

## Walkthrough order

1. Run `coboose start` for the workspace the user has open (or `--repo` if they named apps). Use the coboose cwd or `invoke.command` — do not `cd` into a product repo first.
2. If `plan_source` is `saved`, follow that sequence. Do not rediscover or re-plan. Mention `unplanned` or `stale` names if present.
3. If `plan_source` is `discovered` and the order looks right, save it once with `--save` so later starts skip rediscovery. Show the plan: order, `run_via`, command, `port_hint`, proxy files, launch configuration name / env keys, and anything in `blocked`. Do not open `launch.json` to "confirm" env values.
4. If a service is blocked (`not cloned` or `no start command`), stop that item. Clone first, or inspect that repo's README / `package.json` / `pom.xml` and ask before guessing. If `run_via` is `vscode` and there is no shell command, ask the user to **Run Without Debugging** on `launch.configuration`.
5. Start **infra** (only if the user asked for compose) then **backends**, one at a time. Use **one VS Code terminal per app** (see below).
6. Wait until the process is listening. Prefer `wait` (`listen:8080` or an HTTP URL). If `port_hint` is missing or wrong, read that app’s terminal log (`Tomcat started on port`, `Local: http://localhost:…`) and use the live port.
7. For each frontend with `proxies[]`, rewrite `target` values to the live backend URL in the sibling working tree. Do **not** commit proxy edits unless the user asked.
8. Start frontends the same way: one terminal per app. Report the running map (name, command, live port, URL, terminal).

## How to start each app

Use `run_via` from the plan. Do not invent a shell command that exports secrets.

| `run_via` | What to do |
| --- | --- |
| `coboose` | Run `copilot_command` from the coboose cwd (it already includes `--project`). Do not `cd` into the sibling first — the CLI starts the process in the repo cwd and applies launch env to that child only. Bare `uv run coboose` cannot spawn from an app terminal. The CLI loads launch.json / envFile in-process and does not print values. If you need the env in the terminal itself (without starting the app), use `start env --repo <name> --shell` |
| `vscode` | Tell the user (or invoke) **Run Without Debugging** on `launch.configuration`. Do **not** start Debugging unless they asked. Do not read `launch.json` |
| `terminal` | Run `command` in that app’s `cwd` as before |

If `launch.uses_vscode_inputs` is true, only the VS Code Run path can supply those prompts. Never ask the user to paste the resolved values into chat.

## Terminals

The coboose does not open terminals. You do, via the chat terminal / `runCommands` tool.

- **One long-running process per terminal.** Never start a second app in a terminal that is already hosting Spring, `ng serve`, or similar.
- **Reuse if that app is already up.** If a terminal is already named for the repo (or is clearly running that command in that `cwd`), do not launch another copy. Read its log for the live port and continue.
- **Otherwise open a new terminal** in that service’s `cwd` (`path` from the plan). Title or label it with the repo name when the tool allows (`backend`, `frontend`).
- Leave those terminals running. Do not reuse a busy app terminal to run `coboose start` or git commands. `uv run coboose` cannot spawn from a product-repo cwd.

## Hard rules

- Stay in listed clone folders. Never nest git clones inside the coboose.
- Do not start every service in parallel. Ports and Angular proxies depend on backends that are already listening.
- Do not start two apps in the same terminal.
- Do not run `docker compose up` unless the user asked, even when `compose` files are listed.
- Do not kill unrelated processes. If a planned port is already in use, say so and ask whether to reuse it or pick another.
- Do not copy product start scripts into `repositories.yml`. Pin the **workspace boot order** in `workspaces/<id>.start.yml` via `--save` (or edit that file). Discovery is only for the first plan.
- Do not rewrite a saved plan unless the user asked or the workspace repos / commands changed (`--refresh --save`, or edit the YAML).
- Prefer `plan_source: saved` over rediscovery. The sequence is workspace-level; live ports still come from process logs.
- Do not commit generated local-dev proxy or env changes unless the user wants that default in git.
- Never print `.env` or Jira tokens.
- Never read sibling `.vscode/launch.json`, `envFile`, or product `.env` files. `coboose start` already redacts them to names and keys.
- Never `export` launch env, reconstruct args/vmArgs, or paste secrets into a terminal command. Use `coboose start env --repo <name>` (keys and collisions only) or `coboose start env --repo <name> --shell` (applies values in-process to a new shell). Do not `eval` or print values.
- Application env keys stay unprefixed so Spring/Node see the same names as VS Code. Collisions with the current terminal are reported as `overwritten_keys`. Pass `--keep-existing` to leave already-set keys alone. Use `--prefix BACKEND` only when you want namespaced copies (`BACKEND_DB_PASSWORD`); that will not satisfy an app looking up `DB_PASSWORD`. Coboose stamps `COBOOSE_ENV_REPO` (and `COBOOSE_ENV_CONFIGURATION` when known) so you can see which project env is active.
- Prefer **Run Without Debugging** over Debug when the VS Code launch path is required.

## Failures

| Symptom | What to do |
| --- | --- |
| `blocked: repo is not cloned` | Show `coboose clone --only <name>` (or `prepare` clone command). Do not `git clone` into the coboose folder |
| `blocked: no start command found` | Read that repo's README / Makefile / `package.json`. Ask. Then put the command in `workspaces/<id>.start.yml` (`--save` or edit) |
| `run_via: vscode` and no command | Ask the user to Run Without Debugging on `launch.configuration`. Do not open launch.json |
| `uses_vscode_inputs` | Same as vscode. `coboose start run` / `start env` cannot resolve `${input:…}` |
| Launch env missing from the parent terminal after `start run` | Expected. `start run` applies env to the child process only. Use `start env --repo <name> --shell` in that app's terminal, or start the app with `start run` |
| Port unknown until start | Keep that app’s terminal open and read the bound port from its log, then continue |
| Two apps in one terminal | Stop. Open a new terminal for the second app. Do not stack long-running commands |
| Angular still hits remote API | Confirm `proxies[].path` was updated to the live local target **before** `ng serve` |
| Java app takes minutes | Say so, wait, do not start the next service yet |
| Saved vs discovered mismatch | Trust `source: saved`. Discovery is a first-run hint |
| User wants this sequence next time | `coboose start --workspace <id> --save` → `workspaces/<id>.start.yml` |
| Workspace repos or commands changed | `--refresh --save`, or edit the YAML by hand |
| `unplanned` names in a saved plan | Those repos are in the workspace but not in the YAML. Ask before starting them; `--save` pins them |
| `Failed to spawn: coboose` / no `pyproject.toml` | Cwd is a sibling clone. Re-run from the coboose folder, or use `invoke.command` / `scripts/coboose.sh` (Windows: `scripts/coboose.ps1`) |

## Workspace start plan

`workspaces/<id>.start.yml` sits next to `workspaces/<id>.code-workspace`. Shared plans are committed so the team reuses the same sequence. Personal workspaces use `workspaces/personal/<id>.start.yml` (gitignored with the rest of that folder). Do not add `start:` to `repositories.yml`.

```yaml
workspace: frontend
order:
  - backend
  - frontend
services:
  - name: backend
    command: ./mvnw spring-boot:run
    port: 8080
    role: backend
    wait: listen:8080
    launch: Launch Backend
    method: coboose
  - name: frontend
    command: pnpm start
    port: 4200
    role: frontend
    depends_on: [backend]
```

This file is the boot **sequence** (order, command, port, wait, optional `launch` / `method`). It is not a process supervisor. When discovery is wrong, edit this file. `launch` selects a `launch.json` configuration; `method` is `terminal`, `vscode`, or `coboose`. Prefer keeping secrets in a gitignored `envFile` / `.env` referenced from `launch.json`.

## Related Copilot customizations

- Vague / large-repo orientation: workspace-context skill or `/orient`
- First-run setup: get-started skill or `/get-started`
- Ticket routing: jira-cli skill or `/jira-ticket`

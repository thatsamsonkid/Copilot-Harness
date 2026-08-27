---
name: workspace-start
description: Plan and start local apps in the current feature workspace (Java, Angular, Node). Use when the user wants to run the stack, start services, wire Angular proxies to local backends, or asks how to boot every repo. Discover with harness start; start one process at a time. Do not launch everything in parallel. Never read launch.json or reconstruct env/args.
---

# Workspace start

The harness does **not** own product start scripts. `harness start` inspects sibling clones (and optional `repositories.yml` `start:` overrides) and prints a plan. You start processes one at a time so real ports and proxy rewrites can be applied after each backend is up.

Java apps often keep args and environment variables in `.vscode/launch.json`. Those values must not enter chat. The plan only lists configuration names and env **keys**. Start those apps with `harness start run` or VS Code **Run Without Debugging** — not by reading `launch.json` and not by forcing Debug.

## Commands

| User intent | Command |
| --- | --- |
| Plan for every enabled repo | `uv run harness start --format json` |
| Plan for the open feature workspace | `uv run harness start --workspace <id> --format json` |
| One or more repos | `uv run harness start --repo frontend,backend --format json` |
| Human-readable plan | `uv run harness start --workspace <id> --format markdown` |
| Start one repo with launch.json env/args (no leak) | `uv run harness start run --repo <name>` |
| Preview that run (keys only) | `uv run harness start run --repo <name> --dry-run --format json` |

`harness start` (no `run`) never launches processes. Do not invent a second supervisor.

## How to run the CLI

`uv run harness` only works when the process **cwd is this harness repo** (`pyproject.toml` / `uv.lock`). Sibling product clones do not have that project. If you `cd` into a repo (or set the terminal/`runCommands` cwd there) uv fails with **Failed to spawn: `harness`**.

Always do one of:

1. Keep cwd on the harness root (first workspace folder, named `harness`). Do not `cd` before this command.
2. `uv run --project "$HARNESS_ROOT" harness start --format json` from any cwd (same `--project` form for `start run`)
3. `./scripts/harness.sh start --format json` or `.\scripts\harness.ps1 start --format json` using the harness-root path

`harness start` JSON includes `invoke.command`, `invoke.cwd`, and `invoke.script` for the cwd-safe form. App terminals stay in each service `path`. Never run `uv run harness` from those terminals.

## Walkthrough order

1. Run `harness start` for the workspace the user has open (or `--repo` if they named apps). Use the harness cwd or `invoke.command` — do not `cd` into a product repo first.
2. Show the plan: order, `run_via`, command, `port_hint`, proxy files, launch configuration name / env keys, and anything in `blocked`. Do not open `launch.json` to "confirm" env values.
3. If a service is blocked (`not cloned` or `no start command`), stop that item. Clone first, or inspect that repo's README / `package.json` / `pom.xml` and ask before guessing. If `run_via` is `vscode` and there is no shell command, ask the user to **Run Without Debugging** on `launch.configuration`.
4. Start **infra** (only if the user asked for compose) then **backends**, one at a time. Use **one VS Code terminal per app** (see below).
5. Wait until the process is listening. Prefer `wait` (`listen:8080` or an HTTP URL). If `port_hint` is missing or wrong, read that app’s terminal log (`Tomcat started on port`, `Local: http://localhost:…`) and use the live port.
6. For each frontend with `proxies[]`, rewrite `target` values to the live backend URL in the sibling working tree. Do **not** commit proxy edits unless the user asked.
7. Start frontends the same way: one terminal per app. Report the running map (name, command, live port, URL, terminal).

## How to start each app

Use `run_via` from the plan. Do not invent a shell command that exports secrets.

| `run_via` | What to do |
| --- | --- |
| `harness` | Run `copilot_command` from the harness cwd (it already includes `--project`). Do not `cd` into the sibling first — the CLI starts the process in the repo cwd. Bare `uv run harness` cannot spawn from an app terminal. The CLI loads launch.json / envFile in-process and does not print values |
| `vscode` | Tell the user (or invoke) **Run Without Debugging** on `launch.configuration`. Do **not** start Debugging unless they asked. Do not read `launch.json` |
| `terminal` | Run `command` in that app’s `cwd` as before |

If `launch.uses_vscode_inputs` is true, only the VS Code Run path can supply those prompts. Never ask the user to paste the resolved values into chat.

## Terminals

The harness does not open terminals. You do, via the chat terminal / `runCommands` tool.

- **One long-running process per terminal.** Never start a second app in a terminal that is already hosting Spring, `ng serve`, or similar.
- **Reuse if that app is already up.** If a terminal is already named for the repo (or is clearly running that command in that `cwd`), do not launch another copy. Read its log for the live port and continue.
- **Otherwise open a new terminal** in that service’s `cwd` (`path` from the plan). Title or label it with the repo name when the tool allows (`backend`, `frontend`).
- Leave those terminals running. Do not reuse a busy app terminal to run `harness start` or git commands. `uv run harness` cannot spawn from a product-repo cwd.

## Hard rules

- Stay in listed clone folders. Never nest git clones inside the harness.
- Do not start every service in parallel. Ports and Angular proxies depend on backends that are already listening.
- Do not start two apps in the same terminal.
- Do not run `docker compose up` unless the user asked, even when `compose` files are listed.
- Do not kill unrelated processes. If a planned port is already in use, say so and ask whether to reuse it or pick another.
- Do not copy product start scripts into the harness. If discovery is wrong, prefer a thin `repositories.yml` `start:` override (`command`, `port`, `role`, `wait`, `launch`, `env_file`, `method`).
- Do not commit generated local-dev proxy or env changes unless the user wants that default in git.
- Never print `.env` or Jira tokens.
- Never read sibling `.vscode/launch.json`, `envFile`, or product `.env` files. `harness start` already redacts them to names and keys.
- Never `export` launch env, reconstruct args/vmArgs, or paste secrets into a terminal command.
- Prefer **Run Without Debugging** over Debug when the VS Code launch path is required.

## Failures

| Symptom | What to do |
| --- | --- |
| `blocked: repo is not cloned` | Show `harness clone --only <name>` (or `prepare` clone command). Do not `git clone` into the harness folder |
| `blocked: no start command found` | Read that repo's README / Makefile / `package.json`. Ask. Then add `start.command` in `repositories.yml` if it should stick |
| `run_via: vscode` and no command | Ask the user to Run Without Debugging on `launch.configuration`. Do not open launch.json |
| `uses_vscode_inputs` | Same as vscode. `harness start run` cannot resolve `${input:…}` |
| Port unknown until start | Keep that app’s terminal open and read the bound port from its log, then continue |
| Two apps in one terminal | Stop. Open a new terminal for the second app. Do not stack long-running commands |
| Angular still hits remote API | Confirm `proxies[].path` was updated to the live local target **before** `ng serve` |
| Java app takes minutes | Say so, wait, do not start the next service yet |
| Override vs discovered mismatch | Trust `source: override`. Discovery is a hint |
| `Failed to spawn: harness` / no `pyproject.toml` | Cwd is a sibling clone. Re-run from the harness folder, or use `invoke.command` / `scripts/harness.sh` (Windows: `scripts/harness.ps1`) |

## Optional `repositories.yml` override

```yaml
start:
  command: ./mvnw spring-boot:run
  port: 8080
  role: backend
  wait: http://localhost:8080/actuator/health
  launch: Launch Backend
  env_file: .env
  method: harness
```

`launch` selects a `launch.json` configuration. `env_file` is a repo-relative dotenv loaded by `harness start run`. `method` is `terminal`, `vscode`, or `harness`. Keep this thin. Do not file product secrets or architecture here.

Prefer keeping secrets in a gitignored `envFile` / `.env` and referencing it from `launch.json`, rather than inlining values in a committed launch config.

## Related Copilot customizations

- Vague / large-repo orientation: workspace-context skill or `/orient`
- First-run setup: get-started skill or `/get-started`
- Ticket routing: jira-cli skill or `/jira-ticket`

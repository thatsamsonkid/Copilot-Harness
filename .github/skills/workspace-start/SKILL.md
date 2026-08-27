---
name: workspace-start
description: Plan and start local apps in the current feature workspace (Java, Angular, Node). Use when the user wants to run the stack, start services, wire Angular proxies to local backends, or asks how to boot every repo. Discover with harness start; start one process at a time. Do not launch everything in parallel.
---

# Workspace start

The harness does **not** own product start scripts. `harness start` inspects sibling clones (and optional `repositories.yml` `start:` overrides) and prints a plan. You start processes one at a time so real ports and proxy rewrites can be applied after each backend is up.

## Commands

| User intent | Command |
| --- | --- |
| Plan for every enabled repo | `uv run harness start --format json` |
| Plan for the open feature workspace | `uv run harness start --workspace <id> --format json` |
| One or more repos | `uv run harness start --repo frontend,backend --format json` |
| Human-readable plan | `uv run harness start --workspace <id> --format markdown` |

`harness start` never launches processes. Do not invent a second supervisor.

## Walkthrough order

1. Run `harness start` for the workspace the user has open (or `--repo` if they named apps).
2. Show the plan: order, command, `port_hint`, proxy files, and anything in `blocked`.
3. If a service is blocked (`not cloned` or `no start command`), stop that item. Clone first, or inspect that repo's README / `package.json` / `pom.xml` and ask before guessing.
4. Start **infra** (only if the user asked for compose) then **backends**, one at a time. Use **one VS Code terminal per app** (see below).
5. Wait until the process is listening. Prefer `wait` (`listen:8080` or an HTTP URL). If `port_hint` is missing or wrong, read that app’s terminal log (`Tomcat started on port`, `Local: http://localhost:…`) and use the live port.
6. For each frontend with `proxies[]`, rewrite `target` values to the live backend URL in the sibling working tree. Do **not** commit proxy edits unless the user asked.
7. Start frontends the same way: one terminal per app. Report the running map (name, command, live port, URL, terminal).

## Terminals

The harness does not open terminals. You do, via the chat terminal / `runCommands` tool.

- **One long-running process per terminal.** Never start a second app in a terminal that is already hosting Spring, `ng serve`, or similar.
- **Reuse if that app is already up.** If a terminal is already named for the repo (or is clearly running that command in that `cwd`), do not launch another copy. Read its log for the live port and continue.
- **Otherwise open a new terminal** in that service’s `cwd` (`path` from the plan). Title or label it with the repo name when the tool allows (`backend`, `frontend`).
- Leave those terminals running. Do not reuse a busy app terminal to run `harness start` or git commands.

## Hard rules

- Stay in listed clone folders. Never nest git clones inside the harness.
- Do not start every service in parallel. Ports and Angular proxies depend on backends that are already listening.
- Do not start two apps in the same terminal.
- Do not run `docker compose up` unless the user asked, even when `compose` files are listed.
- Do not kill unrelated processes. If a planned port is already in use, say so and ask whether to reuse it or pick another.
- Do not copy product start scripts into the harness. If discovery is wrong, prefer a thin `repositories.yml` `start:` override (`command`, `port`, `role`, `wait`).
- Do not commit generated local-dev proxy or env changes unless the user wants that default in git.
- Never print `.env` or Jira tokens.

## Failures

| Symptom | What to do |
| --- | --- |
| `blocked: repo is not cloned` | Show `harness clone --only <name>` (or `prepare` clone command). Do not `git clone` into the harness folder |
| `blocked: no start command found` | Read that repo's README / Makefile / `package.json`. Ask. Then add `start.command` in `repositories.yml` if it should stick |
| Port unknown until start | Keep that app’s terminal open and read the bound port from its log, then continue |
| Two apps in one terminal | Stop. Open a new terminal for the second app. Do not stack long-running commands |
| Angular still hits remote API | Confirm `proxies[].path` was updated to the live local target **before** `ng serve` |
| Java app takes minutes | Say so, wait, do not start the next service yet |
| Override vs discovered mismatch | Trust `source: override`. Discovery is a hint |

## Optional `repositories.yml` override

```yaml
start:
  command: ./mvnw spring-boot:run
  port: 8080
  role: backend
  wait: http://localhost:8080/actuator/health
```

Use this when the same repo always starts the same way. Keep it thin. Do not file product architecture here.

## Related Copilot customizations

- Vague / large-repo orientation: workspace-context skill or `/orient`
- First-run setup: get-started skill or `/get-started`
- Ticket routing: jira-cli skill or `/jira-ticket`

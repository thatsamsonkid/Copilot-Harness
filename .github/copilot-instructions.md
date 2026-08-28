# Coboose

This repository is tooling only. Application code lives in **git clones next to this repo** (flat siblings or grouped folders under `parent_dir`), never inside it.

## First-run and vague prompts

- First time in this repo, missing Jira auth, or "how do I set this up?": load `.github/skills/get-started/SKILL.md` and run `uv run coboose init --format json`. Never collect the API token in chat.
- Vague, broad, or no-ticket prompts in a large workspace: load `.github/skills/workspace-context/SKILL.md` and run `uv run coboose context --format json`. Stay inside `workspace.repos`. If `workspace_scope.detected` is false, run `coboose workspace current` and ask which feature workspace to open — do not treat every clone under `parent_dir` as in scope. Read each listed repo's Graphify `GRAPH_REPORT.md` before grepping.
- "Start the apps / run the local stack": load `.github/skills/workspace-start/SKILL.md` and run `uv run coboose start --format json`. That command is a plan only and follows the open workspace (`COBOOSE_WORKSPACE`). Prefer a saved `workspaces/<id>.start.yml` when `plan_source` is `saved`; pin a first good plan with `--save`. Start one process at a time, one VS Code terminal per app (reuse that app’s terminal if it already exists); rewrite Angular proxies after backends are listening. If `run_via` is `coboose`, run `coboose start run --repo <name>` instead of reconstructing launch.json env/args. To inspect or apply one repo's launch env without starting it, use `coboose start env --repo <name>` (add `--shell` to exec a terminal that has the values). Never read sibling `.vscode/launch.json` or product `.env` files. Never start repos that are not in `workspace.repos`.

## Default ticket workflow

When the user gives a Jira key or browse URL, load the **jira-cli** skill (`.github/skills/jira-cli/SKILL.md`) and follow it.

1. Run `uv run coboose prepare <KEY> --format json` from this repo (first workspace folder). If cwd is a sibling clone, `uv run coboose` cannot spawn — use `uv run --project "$COBOOSE_ROOT" coboose prepare <KEY> --format json` or `./scripts/coboose.sh`.
2. Use that CLI JSON as the only ticket source. It is already field-filtered. Do not ask Jira for more.
3. Tell the user to open `routing.open_command` so the feature workspace loads the right roots. Do not assume sibling repos are already in the current window.
4. If `routing.missing_repos` is non-empty, recommend `routing.clone_command`. Never `git clone` into this coboose folder.
5. Write a plan covering impacted repos, likely files, risks, and tests. Do not implement until the user asks.

When the user gives a Figma file/design/proto URL or asks to look at a frame, load the **figma-cli** skill (`.github/skills/figma-cli/SKILL.md`) and follow it.

1. Run `uv run coboose figma images <URL> --format json` from this repo. If cwd is a sibling clone, use `uv run --project "$COBOOSE_ROOT" coboose figma images <URL> --format json`.
2. Use that CLI JSON as the Figma source. It is already field-filtered. Do not ask Figma for the whole file tree.
3. Open each `images[].url` in VS Code Simple Browser so you can see the rendered frame. That image is the visual source of truth.
4. Optionally run `coboose figma comments <URL>` for designer notes. Run `coboose figma nodes <URL>` only for a small specific frame when you need exact tokens. Do not reconstruct layout from node JSON.
5. Do not curl `api.figma.com`, read `.env`, or call a Figma MCP tool.

`coboose` stdout is JSON by default. Read stdout. Errors are JSON on stderr with a non-zero exit code.

## Jira access (hard rules)

This workspace has **no Jira MCP server**. The API token must never enter the chat or a shell command. These rules apply even if the jira-cli skill is not loaded.

- Only talk to Jira through `uv run coboose jira …`, `uv run coboose prepare …`, or `uv run coboose init` / `doctor`.
- Do **not** curl, fetch, or browse `*.atlassian.net` or `/rest/api/`.
- Do **not** read `.env`, print `env`, or expand `$JIRA_API_TOKEN` / `$JIRA_TOKEN`.
- Do **not** read sibling `.vscode/launch.json` env/args or product `.env` / `envFile` values. Use `coboose start` (redacted keys), `coboose start run`, and `coboose start env`.
- Do **not** configure or call an MCP Jira tool.
- If credentials are missing, tell the user to set `JIRA_BASE_URL` / `JIRA_EMAIL` in `.env` and run `uv run coboose jira login` in their own terminal (macOS Keychain or Windows Credential Manager). Never ask them to paste a token into chat.

## Figma access (hard rules)

This workspace has **no Figma MCP server**. The personal access token must never enter the chat or a shell command. These rules apply even if the figma-cli skill is not loaded.

- Only talk to Figma through `uv run coboose figma …` or `uv run coboose doctor --ping-figma`.
- Do **not** curl, fetch, or browse `api.figma.com` or `/v1/`.
- Do **not** read `.env`, print `env`, or expand `$FIGMA_ACCESS_TOKEN` / `$FIGMA_TOKEN` / `$FIGMA_API_TOKEN`.
- Do **not** configure or call an MCP Figma tool.
- If credentials are missing, tell the user to run `uv run coboose figma login` in their own terminal. Never ask them to paste a token into chat.

## Repo layout

- Manifest: `repositories.yml` — every product repo (`name`, GitHub `url`, `tags`; optional `group` / nested `path`).
- Templates: `templates.yml` — starter remotes for bootstrapping **new** projects. Not the current stack.
- Workspaces / Jira routing: `catalog/stack.yaml` — reference repos by name or tag.
- CLI: `src/coboose` — clone, template bootstrap, Jira basic auth, Figma images/comments/nodes, workspace create/generate/match, prepare, init, context, status, branch, handoff, start.
- Feature workspaces: `workspaces/*.code-workspace` — multi-root; first folder is this Coboose repo. Personal/local mixes live in `workspaces/personal/` (gitignored, not in `catalog/stack.yaml`).
- Secrets: declared in `catalog/env.yaml`. Non-secrets go in `.env`. Secrets go in the OS keychain via `coboose env set NAME` / `coboose jira login` / `coboose figma login` (`.env` is a fallback). Never commit tokens or print them. Never put values in generated `.code-workspace` files.

## Commands

Prefer `uv` for Python. Run the CLI as `uv run coboose <command>` **from this Coboose repo**, or `uv run --project "$COBOOSE_ROOT" coboose <command>` / `./scripts/coboose.sh` (Windows: `.\scripts\coboose.ps1`) from any cwd. Sibling clones are not a uv project; `uv run coboose` fails there with Failed to spawn. Jira command choice, flags, and output shapes live in the jira-cli skill. Figma image, comment, and scoped-node exports live in the figma-cli skill. First-run lives in get-started. Graphify and repo standards live in workspace-context. Local stack start lives in workspace-start.

```bash
uv run coboose templates
uv run coboose templates --tag mobile
uv run coboose bootstrap --template <name> --name <folder>
```

If `uv` is missing, follow `docs/install-uv.md` for the user's OS. macOS/Linux: `./scripts/setup.sh`. Windows: `.\scripts\setup.ps1`. Do not use pip to install this repo. Do not tell Windows users to run the bash setup script.

## Bootstrap a new project

When the user asks to create, scaffold, or bootstrap a new project:

1. Run `uv run coboose templates --format json` and treat that list as the source of truth.
2. If they named a listed template (or one clearly matches), run
   `uv run coboose bootstrap --template <name> --name <folder>` (add `--group frontend` to organize under `parent_dir`).
3. If they did not name one, show the listed templates and ask which to use. Do not invent a scaffold when a listed template fits.
4. Put the new project under `parent_dir` (a sibling folder, or `frontend/<name>` via `--group` / a nested `--name`). Never `git clone` into this coboose directory.
5. Ask before `--register` (adds the project to `repositories.yml`) or `--fresh-git`.
6. After bootstrap, follow the CLI `next_steps` and the new repo's own conventions.

## Constraints

- Keep clones outside this repo (`../<path>` or `../frontend/<name>`). Do not add git submodules or nest repos here.
- Prefer the matched / open workspace repos (`workspace.repos` or `routing.repos`). Only load extra roots when the ticket clearly needs them. Do not flag, inspect, or start sibling clones that are merely present on disk.
- After catalog edits, run `coboose workspace generate`. To add a workspace, prefer `/new-workspace` or the **Workspace Creator** agent so chat can collect shared vs personal, id, and `repositories.yml` projects, then run `coboose workspace create <id> --projects … --no-prompt` (add `--personal` for local-only). In a terminal the same command prompts. Never hand-edit `catalog/stack.yaml` or run the interactive CLI from chat.
- When coding in a sibling repo, follow that repo's conventions. This coboose does not override product architecture.
- Before editing a sibling, read the instruction files `coboose context` lists for it (`AGENTS.md`, `.github/copilot-instructions.md`, path-specific instructions, skills).
- After editing a sibling, run that repo's `tooling.suggested_verify`. Do not skip a failing lint/test command from the product repo.
- Do not copy product standards into this coboose. Do not rebuild a Graphify graph unless the user asked, and never extract an entire monorepo unprompted.
- Product knowledge (feature notes, ADRs) lives in the sibling repo. Discover it via `coboose context` `knowledge`. Do not start a second wiki here.

## Invariants (coboose-level only)

These stay few and stable. Everything else lives in the product repo.

- Put the Jira key in each sibling branch name (`uv run coboose branch <KEY>`).
- Open one pull request per sibling repo. Do not squash unrelated repos.
- Never commit `.env` or print secrets.
- Treat `prepare` `done_when` as the stop condition.
- Do not hand-edit `tooling.generated` paths.

## Status, branches, and handoff

- Before planning or pausing, run `uv run coboose status --format json`. It follows the open workspace; pass `--all` only if the user asked for every clone.
- Assigned work: `uv run coboose jira mine --format json`.
- Pause / next chat: `/handoff` or `uv run coboose handoff write --issue <KEY> --note "..."`.
- Review a diff: `/review` or the **Reviewer** agent. Do not implement while reviewing.

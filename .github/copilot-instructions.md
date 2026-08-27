# Copilot Harness

This repository is tooling only. Application code lives in **git clones next to this repo** (flat siblings or grouped folders under `parent_dir`), never inside it.

## First-run and vague prompts

- First time in this repo, missing Jira auth, or "how do I set this up?": load `.github/skills/get-started/SKILL.md` and run `uv run harness init --format json`. Never collect the API token in chat.
- Vague, broad, or no-ticket prompts in a large workspace: load `.github/skills/workspace-context/SKILL.md` and run `uv run harness context --format json`. Read each cloned repo's Graphify `GRAPH_REPORT.md` before grepping.

## Default ticket workflow

When the user gives a Jira key or browse URL, load the **jira-cli** skill (`.github/skills/jira-cli/SKILL.md`) and follow it.

1. Run `uv run harness prepare <KEY> --format json` from this repo (or with `HARNESS_ROOT` set).
2. Use that CLI JSON as the only ticket source. It is already field-filtered. Do not ask Jira for more.
3. Tell the user to open `routing.open_command` so the feature workspace loads the right roots. Do not assume sibling repos are already in the current window.
4. If `routing.missing_repos` is non-empty, recommend `routing.clone_command`. Never `git clone` into this harness folder.
5. Write a plan covering impacted repos, likely files, risks, and tests. Do not implement until the user asks.

`harness` stdout is JSON by default. Read stdout. Errors are JSON on stderr with a non-zero exit code.

## Jira access (hard rules)

This workspace has **no Jira MCP server**. The API token must never enter the chat or a shell command. These rules apply even if the jira-cli skill is not loaded.

- Only talk to Jira through `uv run harness jira …`, `uv run harness prepare …`, or `uv run harness init` / `doctor`.
- Do **not** curl, fetch, or browse `*.atlassian.net` or `/rest/api/`.
- Do **not** read `.env`, print `env`, or expand `$JIRA_API_TOKEN` / `$JIRA_TOKEN`.
- Do **not** configure or call an MCP Jira tool.
- If credentials are missing, tell the user to edit `.env` locally. Never ask them to paste a token into chat.

## Repo layout

- Manifest: `repositories.yml` — every product repo (`name`, GitHub `url`, `tags`; optional `group` / nested `path`).
- Templates: `templates.yml` — starter remotes for bootstrapping **new** projects. Not the current stack.
- Workspaces / Jira routing: `catalog/stack.yaml` — reference repos by name or tag.
- CLI: `src/harness` — clone, template bootstrap, Jira basic auth, workspace create/generate/match, prepare, init, context, status, branch, handoff.
- Feature workspaces: `workspaces/*.code-workspace` — multi-root; first folder is this harness.
- Secrets: `.env` (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`). Never commit tokens or print them.

## Commands

Prefer `uv` for Python. Run the CLI as `uv run harness <command>` (or `./scripts/harness.sh`). Jira command choice, flags, and output shapes live in the jira-cli skill. First-run lives in get-started. Graphify and repo standards live in workspace-context.

```bash
uv run harness templates
uv run harness templates --tag mobile
uv run harness bootstrap --template <name> --name <folder>
```

If `uv` is missing, follow `docs/install-uv.md` for the user's OS. macOS/Linux: `./scripts/setup.sh`. Windows: `.\scripts\setup.ps1`. Do not use pip to install this repo. Do not tell Windows users to run the bash setup script.

## Bootstrap a new project

When the user asks to create, scaffold, or bootstrap a new project:

1. Run `uv run harness templates --format json` and treat that list as the source of truth.
2. If they named a listed template (or one clearly matches), run
   `uv run harness bootstrap --template <name> --name <folder>` (add `--group frontend` to organize under `parent_dir`).
3. If they did not name one, show the listed templates and ask which to use. Do not invent a scaffold when a listed template fits.
4. Put the new project under `parent_dir` (a sibling folder, or `frontend/<name>` via `--group` / a nested `--name`). Never `git clone` into this harness directory.
5. Ask before `--register` (adds the project to `repositories.yml`) or `--fresh-git`.
6. After bootstrap, follow the CLI `next_steps` and the new repo's own conventions.

## Constraints

- Keep clones outside this repo (`../<path>` or `../frontend/<name>`). Do not add git submodules or nest repos here.
- Prefer the matched workspace repos. Only load extra roots when the ticket clearly needs them.
- After catalog edits, run `harness workspace generate`. To add a workspace, prefer `/new-workspace` or the **Workspace Creator** agent so chat can collect id and `repositories.yml` projects, then run `harness workspace create <id> --projects … --no-prompt`. In a terminal the same command prompts. Never hand-edit `catalog/stack.yaml` or run the interactive CLI from chat.
- When coding in a sibling repo, follow that repo's conventions. This harness does not override product architecture.
- Before editing a sibling, read the instruction files `harness context` lists for it (`AGENTS.md`, `.github/copilot-instructions.md`, path-specific instructions, skills).
- After editing a sibling, run that repo's `tooling.suggested_verify`. Do not skip a failing lint/test command from the product repo.
- Do not copy product standards into this harness. Do not rebuild a Graphify graph unless the user asked, and never extract an entire monorepo unprompted.
- Product knowledge (feature notes, ADRs) lives in the sibling repo. Discover it via `harness context` `knowledge`. Do not start a second wiki here.

## Invariants (harness-level only)

These stay few and stable. Everything else lives in the product repo.

- Put the Jira key in each sibling branch name (`uv run harness branch <KEY>`).
- Open one pull request per sibling repo. Do not squash unrelated repos.
- Never commit `.env` or print secrets.
- Treat `prepare` `done_when` as the stop condition.
- Do not hand-edit `tooling.generated` paths.

## Status, branches, and handoff

- Before planning or pausing, run `uv run harness status --format json`.
- Assigned work: `uv run harness jira mine --format json`.
- Pause / next chat: `/handoff` or `uv run harness handoff write --issue <KEY> --note "..."`.
- Review a diff: `/review` or the **Reviewer** agent. Do not implement while reviewing.

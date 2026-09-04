# Goat

This repository is tooling only. Application code lives in **git clones next to this repo** (flat siblings or grouped folders under `parent_dir`), never inside it.

## First-run and vague prompts

- First time in this repo, missing Jira auth, or "how do I set this up?": load `.github/skills/get-started/SKILL.md` and run `uv run goat init --format json`. Never collect the API token in chat.
- VS Code Agents cannot see skills in multi-root child folders: load `.github/skills/skills-install/SKILL.md` and run `uv run goat skills list --brief --format json`. From chat, lift with `goat skills lift --only` or `--all-skills`. In a terminal, `goat skills lift` prompts (numbers, names, `all`). Or `goat skills pull <git-url>` then `--only`. `init` / `prepare` / `workspace generate` already copy goat + in-scope sibling skills into this repo's `.github/skills`. Do not commit those copies.
- Vague, broad, or no-ticket prompts in a large workspace: load `.github/skills/workspace-context/SKILL.md` and run `uv run goat context --format json`. Stay inside `workspace.repos`. If `workspace_scope.detected` is false, run `goat workspace current` and ask which feature workspace to open — do not treat every clone under `parent_dir` as in scope. Read each listed repo's Graphify `GRAPH_REPORT.md` before grepping.
- Unknown workplace word, acronym, or "what do we call X?": load `.github/skills/glossary/SKILL.md` and run `uv run goat glossary get TERM --format json` (or `glossary search`). Do not invent team language. Public org terms live in `catalog/glossary.yml`; personal nicknames live in `catalog/glossary.local.yml` (gitignored); product-only terms may live in a sibling `docs/glossary.yml`. When adding, ask public vs private and pass `--visibility`. Short definitions only — not a second wiki.
- "Start the apps / run the local stack": load `.github/skills/workspace-start/SKILL.md` and run `uv run goat start --format json`. That command is a plan only and follows the open workspace (`GOAT_WORKSPACE`). Prefer a saved `workspaces/<id>.start.yml` when `plan_source` is `saved`; pin a first good plan with `--save`. Start one process at a time, one VS Code terminal per app (reuse that app’s terminal if it already exists); rewrite Angular proxies after backends are listening. If `run_via` is `goat`, run `goat start run --repo <name>` instead of reconstructing launch.json env/args. To inspect or apply one repo's launch env without starting it, use `goat start env --repo <name>` (add `--shell` to exec a terminal that has the values). Never read sibling `.vscode/launch.json` or product `.env` files. Never start repos that are not in `workspace.repos`.

## Default ticket workflow

When the user gives a Jira key or browse URL, load the **jira-cli** skill (`.github/skills/jira-cli/SKILL.md`) and follow it.

1. Run `uv run goat prepare <KEY> --format json` from this repo (first workspace folder). If cwd is a sibling clone, `uv run goat` cannot spawn — use `uv run --project "$GOAT_ROOT" goat prepare <KEY> --format json` or `./scripts/goat.sh`.
2. Use that CLI JSON as the only ticket source. It is already field-filtered. Do not ask Jira for more.
3. Tell the user to open `routing.open_command` so the feature workspace loads the right roots. Do not assume sibling repos are already in the current window.
4. If `routing.missing_repos` is non-empty, recommend `routing.clone_command`. Never `git clone` into this goat folder.
5. Write a plan covering impacted repos, likely files, risks, and tests. Do not implement until the user asks. If the plan should be saved for later or handed to another model, load `.github/skills/planning/SKILL.md` and write it to `plans/` (gitignored) from `templates/plan.md` — detailed enough for a zero-context executor.

When the user wants to **write or draft** a Jira ticket from notes (or runs `/prepare-jira`), load `.github/skills/prepare-jira/SKILL.md`. Format from `templates/jira-ticket.md`, write `jira-tickets/<YYYY-MM-DD>-<slug>.md` (gitignored), and print copy-paste blocks. Do not create the issue in Jira — the CLI is read-only.

When the user gives a Figma file/design/proto URL or asks to look at a frame, load the **figma-cli** skill (`.github/skills/figma-cli/SKILL.md`) and follow it.

1. Run `uv run goat figma images <URL> --format json` from this repo. If cwd is a sibling clone, use `uv run --project "$GOAT_ROOT" goat figma images <URL> --format json`.
2. Use that CLI JSON as the Figma source. Images and comments are field-filtered. `figma nodes` is raw node JSON for a targeted frame only. Do not ask Figma for a whole file tree.
3. Open each `images[].url` in VS Code Simple Browser so you can see the rendered frame. That image is the visual source of truth.
4. Optionally run `goat figma comments <URL>` for designer notes. Run `goat figma nodes <URL>` only for a small targeted frame (a button or similar). That command returns raw Figma node JSON and will overwhelm context on a page or file. Do not reconstruct layout from the tree.
5. Do not curl `api.figma.com`, read `.env`, or call a Figma MCP tool.

When the user mentions Bruno, bru, a `.bru` file, an API collection, or a multi-step API workflow (search then cart), load the **bruno-cli** skill (`.github/skills/bruno-cli/SKILL.md`) and follow it.

1. Run `uv run goat bruno collections --format json` from this repo. If cwd is a sibling clone, use `uv run --project "$GOAT_ROOT" goat bruno collections --format json`.
2. Use that CLI JSON to find the Bruno sibling, collections, services, environments, and workflows. Environment values are not returned.
3. Generate new requests as `.bru` files in that collection. Execute with `goat bruno run` (or `bru run` from the collection root) and `--env` / `--env-var`. Workflows are a plan — pick values between steps.
4. Do not curl product APIs, read Bruno environment file values, or clone into this goat folder.

`goat` stdout is JSON by default. Read stdout. Errors are JSON on stderr with a non-zero exit code.

## Jira access (hard rules)

This workspace has **no Jira MCP server**. The API token must never enter the chat or a shell command. These rules apply even if the jira-cli skill is not loaded.

- Only talk to Jira through `uv run goat jira …`, `uv run goat prepare …`, or `uv run goat init` / `doctor`.
- Do **not** curl, fetch, or browse `*.atlassian.net` or `/rest/api/`.
- Do **not** read `.env`, print `env`, or expand `$JIRA_API_TOKEN` / `$JIRA_TOKEN`.
- Do **not** read sibling `.vscode/launch.json` env/args or product `.env` / `envFile` values. Use `goat start` (redacted keys), `goat start run`, and `goat start env`.
- Do **not** configure or call an MCP Jira tool.
- If credentials are missing, tell the user to set `JIRA_BASE_URL` / `JIRA_EMAIL` in `.env` and run `uv run goat jira login` in their own terminal (macOS Keychain or Windows Credential Manager). Never ask them to paste a token into chat.

## Figma access (hard rules)

This workspace has **no Figma MCP server**. The personal access token must never enter the chat or a shell command. These rules apply even if the figma-cli skill is not loaded.

- Only talk to Figma through `uv run goat figma …` or `uv run goat doctor --ping-figma`.
- Do **not** curl, fetch, or browse `api.figma.com` or `/v1/`.
- Do **not** read `.env`, print `env`, or expand `$FIGMA_ACCESS_TOKEN` / `$FIGMA_TOKEN` / `$FIGMA_API_TOKEN`.
- Do **not** configure or call an MCP Figma tool.
- If credentials are missing, tell the user to run `uv run goat figma login` in their own terminal. Never ask them to paste a token into chat.

## Bruno access (hard rules)

Bruno collections are git files plus the `bru` CLI. These rules apply even if the bruno-cli skill is not loaded.

- Discover collections through `uv run goat bruno …`. Execute HTTP with `goat bruno run` or `bru run` from the collection root.
- Do **not** curl product APIs when a `.bru` request exists for that call.
- Do **not** read Bruno `environments/*.bru` values or print tokens. Yard Goat only lists environment and variable **names**.
- Do **not** nest a collections clone inside this goat folder.

## Repo layout

- Manifest: `repositories.yml` — every product repo (`name`, GitHub `url`, `tags`; optional `group` / nested `path`).
- Templates: `templates.yml` — starter remotes for bootstrapping **new** projects. Not the current stack.
- Workspaces / Jira routing: `catalog/stack.yaml` — reference repos by name or tag.
- CLI: `src/` (imported as `goat`) — clone, template bootstrap, Jira basic auth, Figma images/comments/nodes, Bruno collection discovery / bru wrap, workspace create/generate/match, workspace graph (`goat graph`), prepare, init, context, glossary, status, branch, handoff, start, skills list/lift/pull. `goat commands` (alias `help`) is the live catalog; `docs/cli.md` is the human cheat sheet.
- Feature workspaces: `catalog/stack.yaml` is the committed catalog. `workspaces/*.code-workspace` files are generated locally (gitignored); first folder is this Goat repo.
- Secrets: declared in `catalog/env.yaml`. Non-secrets go in `.env`. Secrets go in the OS keychain via `goat env set NAME` / `goat jira login` / `goat figma login` (`.env` is a fallback). Never commit tokens or print them. Never put values in generated `.code-workspace` files.

## Commands

Prefer `uv` for Python. Run the CLI as `uv run goat <command>` **from this Goat repo**, or `uv run --project "$GOAT_ROOT" goat <command>` / `./scripts/goat.sh` (Windows: `.\scripts\goat.ps1`) from any cwd. After `uv run goat install`, a `~/.local/bin` shim makes `goat` work from any cwd. Sibling clones are not a uv project; `uv run goat` fails there with Failed to spawn. For a full command catalog, run `uv run goat commands --format json` (or read `docs/cli.md`) — not during `/new-workspace`. Jira command choice, flags, and output shapes live in the jira-cli skill. Figma image, comment, and scoped-node exports live in the figma-cli skill. Bruno collections, workflows, and `bru run` wrapping live in the bruno-cli skill. First-run lives in get-started. Graphify and repo standards live in workspace-context. Workplace words and acronyms live in the glossary skill (`goat glossary get`). Local stack start lives in workspace-start. New feature workspaces live in workspace-create (`goat workspace create --menu`). VS Code Agents skill copies live in skills-install.

```bash
uv run goat templates
uv run goat templates --tag mobile
uv run goat bootstrap --template <name> --name <folder>
```

If `uv` is missing, follow `docs/install-uv.md` for the user's OS. macOS/Linux: `./scripts/setup.sh`. Windows: `.\scripts\setup.ps1`. Do not use pip to install this repo. Do not tell Windows users to run the bash setup script.

## Bootstrap a new project

When the user asks to create, scaffold, or bootstrap a new project:

1. Run `uv run goat templates --format json` and treat that list as the source of truth.
2. If they named a listed template (or one clearly matches), run
   `uv run goat bootstrap --template <name> --name <folder>` (add `--group frontend` to organize under `parent_dir`).
3. If they did not name one, show the listed templates and ask which to use. Do not invent a scaffold when a listed template fits.
4. Put the new project under `parent_dir` (a sibling folder, or `frontend/<name>` via `--group` / a nested `--name`). Never `git clone` into this goat directory.
5. Ask before `--register` (adds the project to `repositories.yml`) or `--fresh-git`.
6. After bootstrap, follow the CLI `next_steps` and the new repo's own conventions.

## Constraints

- Keep clones outside this repo (`../<path>` or `../frontend/<name>`). Do not add git submodules or nest repos here.
- Prefer the matched / open workspace repos (`workspace.repos` or `routing.repos`). Only load extra roots when the ticket clearly needs them. Do not flag, inspect, or start sibling clones that are merely present on disk.
- After catalog edits, run `goat workspace generate` so local `.code-workspace` files match. Do not commit those files. To add a workspace, load `.github/skills/workspace-create/SKILL.md` and run `goat workspace create --menu` (compact picker). Do not also run `goat repos`, `goat commands`, or `goat skills list`. Then `goat workspace create <id> --projects … --no-prompt`. In a terminal the same command prompts. Never hand-edit `catalog/stack.yaml` or generated `.code-workspace` files, or run the interactive CLI from chat.
- When coding in a sibling repo, follow that repo's conventions. This goat does not override product architecture.
- Before editing a sibling, read the instruction files `goat context` lists for it (`AGENTS.md`, `.github/copilot-instructions.md`, path-specific instructions, skills).
- After editing a sibling, run that repo's `tooling.suggested_verify`. Do not skip a failing lint/test command from the product repo.
- Do not copy product standards into this goat. Do not rebuild a Graphify graph unless the user asked, and never extract an entire monorepo unprompted.
- Product knowledge (feature notes, ADRs) lives in the sibling repo. Discover it via `goat context` `knowledge`. Do not start a second wiki here.
- Workplace vocabulary is the exception: `catalog/glossary.yml` (public) plus `catalog/glossary.local.yml` (private, gitignored) plus `goat glossary`. Look terms up; do not guess. Ask public vs private before adding.

## Invariants (goat-level only)

These stay few and stable. Everything else lives in the product repo.

- Put the Jira key in each sibling branch name (`uv run goat branch <KEY>`).
- Open one pull request per sibling repo. Do not squash unrelated repos.
- Never commit `.env` or print secrets.
- Treat `prepare` `done_when` as the stop condition.
- Do not hand-edit `tooling.generated` paths.

## Status, branches, and handoff

- Before planning or pausing, run `uv run goat status --format json`. It follows the open workspace; pass `--all` only if the user asked for every clone.
- Assigned work: `uv run goat jira mine --format json`.
- Pause / next chat: `/handoff` or `uv run goat handoff write --issue <KEY> --note "..."`.
- Review a diff: `/review` or the **Reviewer** agent. Do not implement while reviewing.

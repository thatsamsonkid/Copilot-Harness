# Coboose CLI quick reference

Run from this repo: `uv run coboose <command>`. After `cd` into a sibling, `uv run coboose` cannot spawn — use `uv run --project "$COBOOSE_ROOT" coboose …` or `./scripts/coboose.sh` (Windows: `.\scripts\coboose.ps1`). To type `coboose` from any directory, run `uv run coboose install` once (macOS, Linux, and Windows). That writes a shim to `~/.local/bin` which pins this kit and calls `uv run --project`.

Stdout is JSON by default. Use `--format markdown` or `text` for a human view. Errors are JSON on stderr.

This page is the human cheat sheet. The live catalog (same list, plus flags) is:

```bash
uv run coboose commands --format markdown
uv run coboose commands jira
uv run coboose help start
```

`coboose help` is an alias for `coboose commands`. For flags on one command, run `coboose <command> --help`.

Shared flags on every command: `--format`, `--catalog`, `--repos`, `--templates`, `--root`.

## Setup and health

| Command | What it does |
| --- | --- |
| `coboose commands [GROUP]` | Print this catalog (`help` is an alias) |
| `coboose init` | First-run checklist for `.env`, Jira token, and repos |
| `coboose install` | Put `coboose` on PATH (shim in `~/.local/bin`, any cwd) |
| `coboose uninstall` | Remove the PATH shim written by `coboose install` |
| `coboose doctor` | Check catalog, clones, Jira, optional Figma, and Bruno |
| `coboose env list` | Show declared env vars and whether each is present (never values) |
| `coboose env set NAME` | Set one declared variable (secrets go in the OS keychain) |
| `coboose env unset NAME` | Remove a secret from the OS keychain |

`init --interactive` and `env set` / `jira login` / `figma login` are for a local terminal, not chat.

## Repos, templates, and workspaces

| Command | What it does |
| --- | --- |
| `coboose repos` | Show the `repositories.yml` manifest |
| `coboose catalog` | Show the resolved catalog |
| `coboose clone` | Clone remotes under `parent_dir` (outside this coboose) |
| `coboose templates [NAME]` | List starter remotes from `templates.yml` |
| `coboose bootstrap [TEMPLATE]` | Clone a listed template as a new project |
| `coboose workspace list` | List feature workspaces |
| `coboose workspace generate` | Write local `.code-workspace` files from `catalog/stack.yaml` (`--check` reports drift, no write) |
| `coboose workspace create [ID]` | Create a workspace and pick projects from `repositories.yml` |
| `coboose workspace match ISSUE` | Recommend a workspace for an issue |
| `coboose workspace open ID` | Open a workspace in VS Code |
| `coboose workspace path ID` | Print a workspace file path |
| `coboose workspace current` | Detect the open feature workspace |

Typical bootstrap: `coboose bootstrap --template <name> --name <folder>`. Catalog starters: `coboose workspace generate` then `coboose workspace open <id>`. Your own mix: `coboose workspace create`.

## Tickets (Jira)

There is no Jira MCP server. Never read `.env` or paste a token into chat.

| Command | What it does |
| --- | --- |
| `coboose prepare ISSUE` | Fetch a ticket, choose a workspace, report missing repos, attach `done_when` |
| `coboose jira get ISSUE` | Fetch one issue |
| `coboose jira context ISSUE` | Issue plus comments |
| `coboose jira comments ISSUE` | Comments only |
| `coboose jira search JQL` | Run JQL |
| `coboose jira mine` | Unresolved issues assigned to you |
| `coboose jira schema` | Configured Jira output fields |
| `coboose jira whoami` | Validate Jira credentials (no token in output) |
| `coboose jira login` | Store the API token in the OS keychain |
| `coboose jira logout` | Remove the API token from the OS keychain |

Prefer `prepare` over assembling get + match + clone yourself. See `.github/skills/jira-cli/SKILL.md`.

## Figma

There is no Figma MCP server. Open each `images[].url` in VS Code Simple Browser.

| Command | What it does |
| --- | --- |
| `coboose figma images FILE` | Export rendered frame URLs |
| `coboose figma comments FILE` | Clipped file comments (optional node filter) |
| `coboose figma nodes FILE` | Raw node JSON for a small targeted frame (not a page) |
| `coboose figma schema` | Configured Figma output fields |
| `coboose figma whoami` | Validate Figma credentials (no token in output) |
| `coboose figma login` | Store the personal access token in the OS keychain |
| `coboose figma logout` | Remove the token from the OS keychain |

`FILE` can be a `https://www.figma.com/design/…` URL or a file key. See `.github/skills/figma-cli/SKILL.md`.

## Bruno (API collections)

`bru run` executes HTTP. Coboose discovers the sibling collections repo and resolves cwd / `--env`. Workflows are a plan, not a runner.

| Command | What it does |
| --- | --- |
| `coboose bruno collections` | List Bruno repos, collections, services, and workflows |
| `coboose bruno requests [TARGET]` | List requests (optional collection or request filter) |
| `coboose bruno envs [COLLECTION]` | List environment and variable names (never values) |
| `coboose bruno workflows [NAME]` | List described workflows, or one full step plan |
| `coboose bruno run REQUEST` | Resolve collection cwd + env, then invoke `bru run` |
| `coboose bruno schema` | Configured Bruno output fields and the request template |

Tag the collections remote `bruno` in `repositories.yml` (or set `catalog/stack.yaml` `bruno.repos`). See `.github/skills/bruno-cli/SKILL.md` and [docs/bruno.md](bruno.md).

## Day-to-day loop

These follow the open feature workspace (`COBOOSE_WORKSPACE`). Pass `--workspace <id>` to pin one, or `--all` only when you want every clone.

| Command | What it does |
| --- | --- |
| `coboose context` | Graphify graphs, instruction files, feature notes, verify commands |
| `coboose status` | Read-only git snapshot (branch, dirty, ahead/behind) |
| `coboose branch ISSUE` | Suggest the same Jira-key branch in matched clones (`--create` on a clean tree) |
| `coboose handoff write` | Write a session note under `handoffs/` (gitignored) |
| `coboose handoff list` | List handoff notes |
| `coboose handoff latest` | Show the newest handoff note |
| `coboose start` | Print a start plan (does not launch) |
| `coboose start run` | Start one repo with launch.json env loaded in-process (`--repo` required) |
| `coboose start env` | List or apply one repo's launch env (`--shell` execs a terminal) |

Pin a good start sequence with `coboose start --save`. See `.github/skills/workspace-start/SKILL.md`.

## Agent skills

VS Code Agents does not scan multi-root child skills. Lift copies into this coboose `.github/skills`.

| Command | What it does |
| --- | --- |
| `coboose skills list` | Discover skills in this coboose and cloned siblings |
| `coboose skills list --brief` | Name + description only (no `sources[]` dump) |
| `coboose skills lift` | In a terminal: numbered picker (`all` is valid). Chat/scripts: `--only` or `--all-skills` |
| `coboose skills pull URL` | Clone a skills repo temporarily and install selected ones |

`init`, `prepare`, and `workspace generate` already lift coboose + in-scope sibling skills. Do not commit those copies. See `.github/skills/skills-install/SKILL.md`.

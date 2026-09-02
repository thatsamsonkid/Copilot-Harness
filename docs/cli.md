# Goat CLI quick reference

Run from this repo: `uv run goat <command>`. After `cd` into a sibling, `uv run goat` cannot spawn — use `uv run --project "$GOAT_ROOT" goat …` or `./scripts/goat.sh` (Windows: `.\scripts\goat.ps1`). To type `goat` from any directory, run `uv run goat install` once (macOS, Linux, and Windows). That writes a shim to `~/.local/bin` which pins this kit and calls `uv run --project`.

Stdout is JSON by default. Use `--format markdown` or `text` for a human view. Errors are JSON on stderr.

This page is the human cheat sheet. The live catalog (same list, plus flags) is:

```bash
uv run goat commands --format markdown
uv run goat commands jira
uv run goat help start
```

`goat help` is an alias for `goat commands`. For flags on one command, run `goat <command> --help`.

Shared flags on every command: `--format`, `--catalog`, `--repos`, `--templates`, `--root`.

## Setup and health

| Command | What it does |
| --- | --- |
| `goat commands [GROUP]` | Print this catalog (`help` is an alias) |
| `goat init` | First-run checklist for `.env`, Jira token, and repos |
| `goat install` | Put `goat` on PATH (shim in `~/.local/bin`, any cwd) |
| `goat uninstall` | Remove the PATH shim written by `goat install` |
| `goat doctor` | Check catalog, clones, Jira, optional Figma, and Bruno |
| `goat env list` | Show declared env vars and whether each is present (never values) |
| `goat env set NAME` | Set one declared variable (secrets go in the OS keychain) |
| `goat env unset NAME` | Remove a secret from the OS keychain |

`init --interactive` and `env set` / `jira login` / `figma login` are for a local terminal, not chat.

## Repos, templates, and workspaces

| Command | What it does |
| --- | --- |
| `goat repos` | Show the `repositories.yml` manifest |
| `goat catalog` | Show the resolved catalog |
| `goat clone` | Clone remotes under `parent_dir` (outside this goat) |
| `goat templates [NAME]` | List starter remotes from `templates.yml` |
| `goat bootstrap [TEMPLATE]` | Clone a listed template as a new project |
| `goat workspace list` | List feature workspaces |
| `goat workspace generate` | Write local `.code-workspace` files from `catalog/stack.yaml` (`--check` reports drift, no write) |
| `goat workspace create [ID]` | Create a workspace and pick projects from `repositories.yml` |
| `goat workspace match ISSUE` | Recommend a workspace for an issue |
| `goat workspace open ID` | Open a workspace in VS Code |
| `goat workspace path ID` | Print a workspace file path |
| `goat workspace current` | Detect the open feature workspace |
| `goat graph scan` | Run workspace-graph extractors (no write) |
| `goat graph build` | Correlate evidence and write `.workspace/generated/workspace-graph.json` |
| `goat graph validate` | Validate a workspace-graph.json file |
| `goat graph explain` | Show why an edge exists (classification, confidence, evidence) |
| `goat graph neighbors` | Inbound and outbound edges for one node |
| `goat graph path` | Directed path between two nodes |

Typical bootstrap: `goat bootstrap --template <name> --name <folder>`. Catalog starters: `goat workspace generate` then `goat workspace open <id>`. Your own mix: `goat workspace create`. Architectural map: `goat graph build` then `goat graph explain` (see [workspace-graph.md](workspace-graph.md)).

## Tickets (Jira)

There is no Jira MCP server. Never read `.env` or paste a token into chat.

| Command | What it does |
| --- | --- |
| `goat prepare ISSUE` | Fetch a ticket, choose a workspace, report missing repos, attach `done_when` |
| `goat jira get ISSUE` | Fetch one issue |
| `goat jira context ISSUE` | Issue plus comments |
| `goat jira comments ISSUE` | Comments only |
| `goat jira search JQL` | Run JQL |
| `goat jira mine` | Unresolved issues assigned to you |
| `goat jira schema` | Configured Jira output fields |
| `goat jira whoami` | Validate Jira credentials (no token in output) |
| `goat jira login` | Store the API token in the OS keychain |
| `goat jira logout` | Remove the API token from the OS keychain |

Prefer `prepare` over assembling get + match + clone yourself. See `.github/skills/jira-cli/SKILL.md`. Draft a new ticket from notes with `/prepare-jira` (writes `jira-tickets/`, gitignored) from `templates/jira-ticket.md` so `## Acceptance Criteria` parses into `done_when` and each Figma frame is labeled by role (the Images API returns ids and URLs only). The CLI cannot create or update the issue.

## Figma

There is no Figma MCP server. Open each `images[].url` in VS Code Simple Browser.

| Command | What it does |
| --- | --- |
| `goat figma images FILE` | Export rendered frame URLs |
| `goat figma comments FILE` | Clipped file comments (optional node filter) |
| `goat figma nodes FILE` | Raw node JSON for a small targeted frame (not a page) |
| `goat figma schema` | Configured Figma output fields |
| `goat figma whoami` | Validate Figma credentials (no token in output) |
| `goat figma login` | Store the personal access token in the OS keychain |
| `goat figma logout` | Remove the token from the OS keychain |

`FILE` can be a `https://www.figma.com/design/…` URL or a file key. See `.github/skills/figma-cli/SKILL.md`. For several states (success, error, empty), label each frame URL by role in `templates/jira-ticket.md` — `figma images` returns `{id, url}` only.

## Bruno (API collections)

`bru run` executes HTTP. Yard Goat discovers the sibling collections repo and resolves cwd / `--env`. Workflows are a plan, not a runner.

| Command | What it does |
| --- | --- |
| `goat bruno collections` | List Bruno repos, collections, services, and workflows |
| `goat bruno requests [TARGET]` | List requests (optional collection or request filter) |
| `goat bruno envs [COLLECTION]` | List environment and variable names (never values) |
| `goat bruno workflows [NAME]` | List described workflows, or one full step plan |
| `goat bruno run REQUEST` | Resolve collection cwd + env, then invoke `bru run` |
| `goat bruno schema` | Configured Bruno output fields and the request template |

Tag the collections remote `bruno` in `repositories.yml` (or set `catalog/stack.yaml` `bruno.repos`). See `.github/skills/bruno-cli/SKILL.md` and [docs/bruno.md](bruno.md).

## Day-to-day loop

These follow the open feature workspace (`GOAT_WORKSPACE`). Pass `--workspace <id>` to pin one, or `--all` only when you want every clone.

| Command | What it does |
| --- | --- |
| `goat context` | Graphify graphs, instruction files, feature notes, verify commands |
| `goat graph build` | Canonical workspace graph (APIs, events, ADRs, evidence) |
| `goat status` | Read-only git snapshot (branch, dirty, ahead/behind) |
| `goat branch ISSUE` | Suggest the same Jira-key branch in matched clones (`--create` on a clean tree) |
| `goat handoff write` | Write a session note under `handoffs/` (gitignored) |
| `goat handoff list` | List handoff notes |
| `goat handoff latest` | Show the newest handoff note |
| `goat start` | Print a start plan (does not launch) |
| `goat start run` | Start one repo with launch.json env loaded in-process (`--repo` required) |
| `goat start env` | List or apply one repo's launch env (`--shell` execs a terminal) |

Pin a good start sequence with `goat start --save`. See `.github/skills/workspace-start/SKILL.md`.

## Agent skills

VS Code Agents does not scan multi-root child skills. Lift copies into this goat `.github/skills`.

| Command | What it does |
| --- | --- |
| `goat skills list` | Discover skills in this goat and cloned siblings |
| `goat skills list --brief` | Name + description only (no `sources[]` dump) |
| `goat skills lift` | In a terminal: numbered picker (`all` is valid). Chat/scripts: `--only` or `--all-skills` |
| `goat skills pull URL` | Clone a skills repo temporarily and install selected ones |

`init`, `prepare`, and `workspace generate` already lift goat + in-scope sibling skills. Do not commit those copies. See `.github/skills/skills-install/SKILL.md`.

Language packs (TypeScript, Python, Java) are first-party skills plus path-scoped `.github/instructions/*.instructions.md`. `goat context` / `prepare` set `language` and `language_skill` from `repositories.yml` `language`, tags, or lockfiles.

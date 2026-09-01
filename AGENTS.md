# Agent instructions

This repo is **Goat** (Yard Goat), a Copilot Kit — not the product codebase.

Application repositories are cloned **next to** this folder (flat siblings, or grouped under `parent_dir` folders such as `frontend/`, `backend/`, `infra/`, `shared/`). The full-app list lives in `repositories.yml`. Starter remotes for new projects live in `templates.yml`. Feature workspaces and Jira routing live in `catalog/stack.yaml`. `workspaces/*.code-workspace` files are generated locally from that catalog (`goat workspace generate`) and are gitignored — do not commit them. See also `.github/copilot-instructions.md`.

Run `uv run goat …` from this Goat repo (or `uv run --project "$GOAT_ROOT" goat …` / `./scripts/goat.sh`). After `cd` into a sibling clone, bare `uv run goat` cannot spawn. `uv run goat install` writes a `~/.local/bin` shim so `goat` works from any cwd (macOS, Linux, Windows). Full command catalog: `uv run goat commands --format json` or [docs/cli.md](docs/cli.md).

When asked to bootstrap a new project:

```bash
uv run goat templates --format json
uv run goat bootstrap --template <name> --name <folder> --format json
```

To add a feature workspace, use `/new-workspace` (or the Workspace Creator agent) and walk the user through id and `repositories.yml` projects, then run `uv run goat workspace create <id> --projects … --no-prompt`. In a terminal, `goat workspace create` prompts on its own.

First-run setup: `.github/skills/get-started/SKILL.md` (`uv run goat init`).
VS Code Agents does not scan multi-root child skills: `.github/skills/skills-install/SKILL.md` (`uv run goat skills list` / `skills lift` / `skills pull <url>`). `init`, `prepare`, and `workspace generate` already lift goat + in-scope sibling skills into this repo's `.github/skills`.
Vague or large-repo prompts: `.github/skills/workspace-context/SKILL.md` (`uv run goat context`). Those commands follow the open feature workspace (`GOAT_WORKSPACE`). Do not inspect sibling clones that are only on disk; pass `--workspace <id>` or `--all` only when asked. Cross-repo architecture (APIs, events, ADRs): `uv run goat graph build` / `goat graph explain` (`docs/workspace-graph.md`). Do not treat Graphify as the workspace graph.
Sibling git snapshot / pause a session: `uv run goat status` and `.github/skills/handoff/SKILL.md`.
Writing an implementation plan to a file (for another or a smaller model to execute): `.github/skills/planning/SKILL.md`. Plans go in the root `plans/` directory (gitignored), start from `templates/plan.md`, and must be detailed enough for a zero-context executor — a complete file map of every file to change, plus exact symbols, commands, expected results, and verify checks per step.
Local stack start: `.github/skills/workspace-start/SKILL.md` (`uv run goat start`). Pin a workspace sequence with `--save` (`workspaces/<id>.start.yml`). If a service has launch.json env/args, start it with `uv run goat start run --repo <name>` or VS Code Run Without Debugging; never read launch.json. To apply that env in a terminal without starting the app, use `uv run goat start env --repo <name> --shell` (or omit `--shell` for keys and collisions only).
Detect the open window: `uv run goat workspace current`.
For any Jira key, follow `.github/skills/jira-cli/SKILL.md`:

```bash
uv run goat prepare ISSUE-123 --format json
```

Then open `routing.open_command` and plan against those roots. Treat `done_when` as the stop condition. Do not nest git clones inside this repository.

For a Figma file or frame URL, follow `.github/skills/figma-cli/SKILL.md`:

```bash
uv run goat figma images 'https://www.figma.com/design/…' --format json
```

Open each returned `images[].url` in VS Code Simple Browser. Optionally run `figma comments` for designer notes, or `figma nodes` for a small targeted frame only (raw JSON; a page will overwhelm context). Do not curl Figma or reconstruct the layout from JSON.

For Bruno API collections (`.bru` files, `bru run`, or a multi-step API workflow), follow `.github/skills/bruno-cli/SKILL.md`:

```bash
uv run goat bruno collections --format json
```

That JSON says which sibling holds the collections, which requests/environments exist, and which `--env` to pass. Execute HTTP with `goat bruno run` (or `bru run` from the collection root). Workflows are a plan — pick values between steps. Do not curl product APIs or read environment file values. See [docs/bruno.md](docs/bruno.md).

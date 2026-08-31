# Agent instructions

This repo is **Goat** (Yard Goat), a Copilot Kit — not the product codebase.

Application repositories are cloned **next to** this folder (flat siblings, or grouped under `parent_dir` folders such as `frontend/`, `backend/`, `infra/`, `shared/`). The full-app list lives in `repositories.yml`. Starter remotes for new projects live in `templates.yml`. See also `catalog/stack.yaml` and `.github/copilot-instructions.md`.

Run `uv run goat …` from this Goat repo (or `uv run --project "$GOAT_ROOT" goat …` / `./scripts/goat.sh`). After `cd` into a sibling clone, bare `uv run goat` cannot spawn. Full command catalog: `uv run goat commands --format json` or [docs/cli.md](docs/cli.md).

When asked to bootstrap a new project:

```bash
uv run goat templates --format json
uv run goat bootstrap --template <name> --name <folder> --format json
```

To add a feature workspace, use `/new-workspace` (or the Workspace Creator agent) and walk the user through shared vs personal, id, and `repositories.yml` projects, then run `uv run goat workspace create <id> --projects … --no-prompt` (add `--personal` for a local-only file under `workspaces/personal/`). In a terminal, `goat workspace create` prompts on its own.

First-run setup: `.github/skills/get-started/SKILL.md` (`uv run goat init`).
VS Code Agents does not scan multi-root child skills: `.github/skills/skills-install/SKILL.md` (`uv run goat skills list` / `skills lift` / `skills pull <url>`). `init`, `prepare`, and `workspace generate` already lift goat + in-scope sibling skills into this repo's `.github/skills`.
Vague or large-repo prompts: `.github/skills/workspace-context/SKILL.md` (`uv run goat context`). Those commands follow the open feature workspace (`GOAT_WORKSPACE`). Do not inspect sibling clones that are only on disk; pass `--workspace <id>` or `--all` only when asked.
Sibling git snapshot / pause a session: `uv run goat status` and `.github/skills/handoff/SKILL.md`.
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

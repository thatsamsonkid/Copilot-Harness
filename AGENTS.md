# Agent instructions

This repo is **Coboose**, a Copilot Kit — not the product codebase.

Application repositories are cloned **next to** this folder (flat siblings, or grouped under `parent_dir` folders such as `frontend/`, `backend/`, `infra/`, `shared/`). The full-app list lives in `repositories.yml`. Starter remotes for new projects live in `templates.yml`. See also `catalog/stack.yaml` and `.github/copilot-instructions.md`.

Run `uv run coboose …` from this Coboose repo (or `uv run --project "$COBOOSE_ROOT" coboose …` / `./scripts/coboose.sh`). After `cd` into a sibling clone, bare `uv run coboose` cannot spawn.

When asked to bootstrap a new project:

```bash
uv run coboose templates --format json
uv run coboose bootstrap --template <name> --name <folder> --format json
```

To add a feature workspace, use `/new-workspace` (or the Workspace Creator agent) and walk the user through shared vs personal, id, and `repositories.yml` projects, then run `uv run coboose workspace create <id> --projects … --no-prompt` (add `--personal` for a local-only file under `workspaces/personal/`). In a terminal, `coboose workspace create` prompts on its own.

First-run setup: `.github/skills/get-started/SKILL.md` (`uv run coboose init`).
Vague or large-repo prompts: `.github/skills/workspace-context/SKILL.md` (`uv run coboose context`). Those commands follow the open feature workspace (`COBOOSE_WORKSPACE`). Do not inspect sibling clones that are only on disk; pass `--workspace <id>` or `--all` only when asked.
Sibling git snapshot / pause a session: `uv run coboose status` and `.github/skills/handoff/SKILL.md`.
Local stack start: `.github/skills/workspace-start/SKILL.md` (`uv run coboose start`). Pin a workspace sequence with `--save` (`workspaces/<id>.start.yml`). If a service has launch.json env/args, start it with `uv run coboose start run --repo <name>` or VS Code Run Without Debugging; never read launch.json. To apply that env in a terminal without starting the app, use `uv run coboose start env --repo <name> --shell` (or omit `--shell` for keys and collisions only).
Detect the open window: `uv run coboose workspace current`.
For any Jira key, follow `.github/skills/jira-cli/SKILL.md`:

```bash
uv run coboose prepare ISSUE-123 --format json
```

Then open `routing.open_command` and plan against those roots. Treat `done_when` as the stop condition. Do not nest git clones inside this repository.

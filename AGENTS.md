# Agent instructions

This repo is a **Copilot / VS Code harness**, not the product codebase.

Application repositories are cloned **next to** this folder (flat siblings, or grouped under `parent_dir` folders such as `frontend/`, `backend/`, `infra/`, `shared/`). The full-app list lives in `repositories.yml`. Starter remotes for new projects live in `templates.yml`. See also `catalog/stack.yaml` and `.github/copilot-instructions.md`.

When asked to bootstrap a new project:

```bash
uv run harness templates --format json
uv run harness bootstrap --template <name> --name <folder> --format json
```

To add a feature workspace, use `/new-workspace` (or the Workspace Creator agent) and walk the user through shared vs personal, id, and `repositories.yml` projects, then run `uv run harness workspace create <id> --projects … --no-prompt` (add `--personal` for a local-only file under `workspaces/personal/`). In a terminal, `harness workspace create` prompts on its own.

First-run setup: `.github/skills/get-started/SKILL.md` (`uv run harness init`).
Vague or large-repo prompts: `.github/skills/workspace-context/SKILL.md` (`uv run harness context`).
Local stack start: `.github/skills/workspace-start/SKILL.md` (`uv run harness start`). Pin a workspace sequence with `--save` (`workspaces/<id>.start.yml`).
For any Jira key, follow `.github/skills/jira-cli/SKILL.md`:

```bash
uv run harness prepare ISSUE-123 --format json
```

Then open `routing.open_command` and plan against those roots. Do not nest git clones inside this repository.

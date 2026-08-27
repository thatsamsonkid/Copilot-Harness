# Agent instructions

This repo is a **Copilot / VS Code harness**, not the product codebase.

Application repositories are cloned as **siblings** of this folder. The full-app list lives in `repositories.yml`. See also `catalog/stack.yaml` and `.github/copilot-instructions.md`.

To add a feature workspace, use `/new-workspace` (or the Workspace Creator agent) and walk the user through id plus `repositories.yml` projects, then run `uv run harness workspace create <id> --projects … --no-prompt`. In a terminal, `harness workspace create` prompts on its own.

For any Jira key, follow `.github/skills/jira-cli/SKILL.md`:

```bash
uv run harness prepare ISSUE-123 --format json
```

Then open `routing.open_command` and plan against those roots. Do not nest git clones inside this repository.

# Agent instructions

This repo is a **Copilot / VS Code harness**, not the product codebase.

Application repositories are cloned as **siblings** of this folder. See `catalog/stack.yaml` and `.github/copilot-instructions.md`.

For any Jira key:

```bash
harness prepare ISSUE-123 --format json
```

Then open `routing.open_command` and plan against those roots. Do not nest git clones inside this repository.

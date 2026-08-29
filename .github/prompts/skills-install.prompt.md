---
name: skills-install
description: List, lift, or pull agent skills into the coboose root for the VS Code Agents window
argument-hint: list, lift, or a git URL of skills
agent: agent
---

The user wants sibling or remote agent skills visible in the VS Code Agents window (multi-root child skills are not scanned). Load `.github/skills/skills-install/SKILL.md`.

1. Run `#tool:runCommands` from the coboose repo: `uv run coboose skills list --format json`. If cwd is a sibling, use `uv run --project "$COBOOSE_ROOT" coboose skills list --format json`.
2. If they asked to copy/lift child-repo skills, run `uv run coboose skills lift --format json` (add `--only` when they named specific `available[].pick` values).
3. If they pasted a git URL, run `uv run coboose skills pull <url> --format json` first. When `needs_selection` is true, show `available[]` and ask which to install, then rerun with `--only name,name` or `--all`.
4. Do not `git clone` into this coboose. Do not commit lifted copies. Do not overwrite first-party coboose skills.

`init`, `prepare`, and `workspace generate` already lift coboose + in-scope sibling skills. Use this prompt for an explicit list, a subset, or a remote skills repo.

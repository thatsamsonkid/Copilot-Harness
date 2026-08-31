---
name: skills-install
description: List, lift, or pull agent skills into the goat root for the VS Code Agents window
argument-hint: list, lift, or a git URL of skills
agent: agent
---

The user wants sibling or remote agent skills visible in the VS Code Agents window (multi-root child skills are not scanned). Load `.github/skills/skills-install/SKILL.md`.

1. Run `#tool:runCommands` from the goat repo: `uv run goat skills list --brief --format json`. If cwd is a sibling, use `uv run --project "$GOAT_ROOT" goat skills list --brief --format json`. Show each skill's `name` and `description` (and `source_id` when two names collide).
2. If they asked to copy/lift child-repo skills, prefer telling them to run `uv run goat skills lift` in their own terminal (numbered list, `all` is valid). From chat, use `uv run goat skills lift --only <pick,pick> --format json` or `--all-skills`. Do not drive the interactive prompt.
3. If they pasted a git URL, run `uv run goat skills pull <url> --format json` first. When `needs_selection` is true, show `available[]` and ask which to install, then rerun with `--only name,name` or `--all`.
4. Do not `git clone` into this goat. Do not commit lifted copies. Do not overwrite first-party goat skills.

`init`, `prepare`, and `workspace generate` already lift goat + in-scope sibling skills. Use this prompt for an explicit list, a subset, or a remote skills repo.

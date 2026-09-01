---
name: python
description: Edit Python in this goat or a sibling repo using that tree's tooling
argument-hint: repo or area
agent: agent
---

The user wants Python work (`.py`, Django, FastAPI, pytest, or this goat CLI). Load `.github/skills/python/SKILL.md` and follow it.

1. Decide which tree: this goat vs a sibling. For a sibling, run `#tool:runCommands` from the goat repo: `uv run goat context --repo <name> --format json`. If cwd is a sibling, use `uv run --project "$GOAT_ROOT" goat context --repo <name> --format json`.
2. Read that tree's instruction files. Those win over goat defaults.
3. Goat uses `uv`. Never `pip install` this repo. Siblings use `tooling.suggested_verify`.
4. Do not read `.env` or print secrets. Do not invent Makefile targets.
5. After edits, run verify (`uv run pytest` here, or the sibling command) and report the result.

Do not copy product Python architecture into this goat.

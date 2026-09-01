---
name: Python
description: How to edit Python in this goat or a sibling repo
applyTo: "**/*.py,**/*.pyi"
---

This goat is a uv package. Product Python lives in sibling clones. Load `.github/skills/python/SKILL.md` before the first edit.

- In a sibling, run `uv run goat context --repo <name> --format json` and follow that repo's instruction files. Those win over goat defaults.
- Goat: `uv run pytest` and `uv run goat …`. Never `pip install` this repo.
- Siblings: use `tooling.suggested_verify` (Poetry, pip, pdm, or uv). Do not invent Makefile targets.
- Add type hints on new public functions. Do not use `Any` to silence the checker.
- Do not read `.env` or print secrets. Do not hand-edit `tooling.generated` paths.
- After edits, run the verify command for that tree. Do not skip a red run.

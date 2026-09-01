---
name: python
description: Write or review Python in this goat or a sibling repo. Use when editing .py, pyproject.toml, Django, FastAPI, or pytest. Prefer that repo's tooling; Goat itself uses uv. Do not pip-install this goat. Do not invent Makefile targets.
---

# Python

This goat is a uv Python package. Product Python lives in sibling clones. Load this skill before editing `.py` in either place. Path-scoped rules live in `.github/instructions/python.instructions.md`.

## Which tree is this?

| Tree | How to tell | Tooling |
| --- | --- | --- |
| This goat | `pyproject.toml` names `goat`, cwd is the kit repo | `uv run pytest`, `uv run goat …` |
| Sibling product | `goat context --repo <name>` lists it | That repo's `tooling.suggested_verify` |

Do not treat a sibling as a uv project just because goat is one. Poetry, pip, pdm, or Hatch in the sibling win.

## Before the first edit (sibling)

1. Run `uv run goat context --repo <name> --format json` from the goat repo (or `uv run --project "$GOAT_ROOT" goat context --repo <name>`). Bare `uv run goat` cannot spawn from a product clone.
2. Read that repo's `instructions`. Those win over anything here.
3. Use `tooling.suggested_verify`. Do not invent `make` targets or `uv` scripts the repo does not have.
4. If `graphify.report` is present and the edit location is unclear, read it before grepping.

## Tooling

| Marker | Default verify when `suggested_verify` is empty |
| --- | --- |
| `pyproject.toml` | `uv run pytest` (goat and uv siblings) |
| `manage.py` | existing Django test command from the repo |
| `pytest.ini` / `tests/` | `pytest` |

- Goat: `uv sync` then `uv run pytest`. Never `pip install` this repo.
- Sibling with Poetry / pip / pdm: use that repo's documented command, not goat's uv workflow.
- After goat CLI changes, run the tests that cover the module you touched. Do not skip a failing lint/test.
- Do not add dependencies to goat unless the feature needs them; prefer the stdlib and existing packages.

## Code rules

Sibling (or goat) conventions beat these defaults. When the file is silent:

- Match the module you are in: imports, dataclasses vs Pydantic, pytest style, typing.
- Add type hints on new public functions. Do not add `Any` to silence the checker.
- Keep functions small and testable. New goat commands belong in `src/` with tests under `tests/`.
- Do not read `.env`, print secrets, or expand `$JIRA_API_TOKEN` / `$FIGMA_ACCESS_TOKEN`.
- Do not hand-edit `tooling.generated` paths.
- Tests: pytest. Put them next to existing test modules. Use the fixtures that file already uses.

## Goat-specific

- Run the CLI as `uv run goat <command>` from this repo, or `uv run --project "$GOAT_ROOT" goat …` / `./scripts/goat.sh` from any cwd.
- JSON on stdout is the Copilot contract. Errors are JSON on stderr with a non-zero exit.
- Do not nest product clones inside this goat.

## Hard rules

- Do not copy product Python architecture into this goat.
- Do not tell anyone to `pip install` Yard Goat.
- Do not `cd` into a sibling and run bare `uv run goat` (Failed to spawn).
- Stop when `tooling.suggested_verify` (or `uv run pytest` here) passes. Do not skip a red run.

## Failures

| Symptom | What to do |
| --- | --- |
| No `suggested_verify` | Look for `pyproject.toml`, `Makefile`, or `pytest.ini`. Use what exists. |
| `pip` vs `uv` confusion | Goat is uv-only. Siblings follow their own installer. |
| Failed to spawn: goat | Cwd is a sibling. Re-run from this repo or `uv run --project "$GOAT_ROOT" goat …` |
| Import errors after goat edits | `uv sync` from this repo, then rerun pytest. |

## Related Copilot customizations

- Vague / large-repo orientation: workspace-context skill or `/orient`
- First-run / uv missing: get-started skill or `/get-started`
- TypeScript siblings: typescript skill or `/typescript`
- Java / Spring siblings: java skill or `/java`

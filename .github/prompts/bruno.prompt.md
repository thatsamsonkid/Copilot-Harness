---
name: bruno
description: Discover Bruno API collections and run or generate a request
argument-hint: collection, request, or workflow
---

The user will name a Bruno collection, service, request, workflow, or environment as `${input:target:Collection, request, workflow, or env}`. Follow `.github/skills/bruno-cli/SKILL.md` for CLI rules.

1. From the coboose repo (do not `cd` into a sibling first), run `#tool:runCommands` with cwd = the coboose folder and `uv run coboose bruno collections --format json`. If cwd is already a product clone, use `uv run --project "$COBOOSE_ROOT" coboose bruno collections --format json` instead — bare `uv run coboose` cannot spawn there.
2. If `uv` is missing, follow `docs/install-uv.md` for the user's OS (macOS/Linux: `./scripts/setup.sh`; Windows: `.\scripts\setup.ps1`), then retry.
3. Use only that CLI JSON to name the Bruno repo path, collections, services, and workflows. Do not curl product APIs or read environment file values.
4. If `${input:target}` looks like a workflow, run `uv run coboose bruno workflows ${input:target} --format json` and execute it as a plan (search → pick → next request with `--env-var`).
5. If they asked to generate a request, run `uv run coboose bruno requests ${input:target} --format json`, read one existing `.bru` in that collection, and write a new file there. Confirm with `uv run coboose bruno run <path> --dry-run`.
6. If they asked to execute, run `uv run coboose bruno run ${input:target} --format json` (add `--env` / `--service` / `--env-var` from the inventory). Prefer `--dry-run` first when the environment is unclear.
7. Name the collection and environment you used. If `bru` is missing, tell them to `npm install -g @usebruno/cli`.

Do not clone into this coboose directory. Do not invent collections that were not returned.

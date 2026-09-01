---
name: bruno-cli
description: Operate Bruno API collections through goat and the bru CLI. Use when the user mentions Bruno, bru, a .bru request, an API collection, Postman-style collections, a multi-step API workflow (search then cart), or asks to generate/run a request against a service environment. Do not curl product APIs, read environment values, or print secrets.
argument-hint: collection or request
---

# Bruno CLI

This workspace talks to git-backed Bruno collections through `goat bruno` (discovery + cwd/env) and the `bru` CLI (HTTP). There is no Bruno MCP server.

`bru run` already executes a request or folder with `--env` and `--env-var`. Yard Goat fills the Copilot gaps: which sibling is the Bruno repo, which collections/requests/environments exist, and how multi-step workflows are described. See `docs/bruno.md`.

## Hard rules

- Run `uv run goat <command>` from the goat repo (or `./scripts/goat.sh` / `.\scripts\goat.ps1`). If you already `cd`'d into a sibling, use `uv run --project "$GOAT_ROOT" goat <command>` — bare `uv run goat` cannot spawn there. If `uv` is missing, follow `docs/install-uv.md` (macOS/Linux: `./scripts/setup.sh`; Windows: `.\scripts\setup.ps1`).
- Default `--format` is `json`. Keep JSON. Read stdout. Errors are JSON on stderr with a non-zero exit.
- Treat CLI JSON as complete. It is already filtered by `catalog/stack.yaml` `bruno.fields` and `bruno.shapes`. Environment **values** are never returned — only names.
- Never read `.env`, Bruno `environments/*.bru` values, or print tokens. If you open a `.bru` request file, that is the request definition, not a secret store.
- Never curl product APIs when `bru` / `goat bruno run` can execute the collection request.
- If the Bruno repo is missing, show `clone_command` and let the user confirm. Never `git clone` into the goat folder.
- If `bru` is missing, discovery still works. Tell the user to `npm install -g @usebruno/cli` before `bruno run` (unless they asked for `--dry-run` only).

## Which command

| User intent | Command |
| --- | --- |
| Where is the Bruno repo / what collections exist (default) | `uv run goat bruno collections` |
| Requests for one API / collection | `uv run goat bruno requests <collection>` |
| One request by name or path | `uv run goat bruno requests search/search-products` |
| Environments for a collection or service | `uv run goat bruno envs [COLLECTION]` |
| List described workflows | `uv run goat bruno workflows` |
| Full plan for one workflow (search → pick → cart) | `uv run goat bruno workflows add-to-cart` |
| Resolve cwd + env, do not hit the API | `uv run goat bruno run REQUEST --env local --dry-run` |
| Execute one request via bru | `uv run goat bruno run REQUEST --env staging` |
| Pass a value from a previous step | add `--env-var productId=abc` (repeatable) |
| Pin a service's default env | add `--service cart` |
| Bru skeleton + allowlist | `uv run goat bruno schema` |
| Catalog / clones / bru on PATH | `uv run goat doctor` |

Prefer `bruno collections` before opening random `.bru` files. Prefer `bruno run` over assembling `bru run` yourself so the collection root and `--env` are correct. `bru run` from the collection cwd is fine after you have read that inventory.

## `bruno collections` JSON

Use these objects only:

- `repos` — sibling Bruno remotes (`name`, `path`, `cloned`, `collections`)
- `collections` — `{id, name, repo, path, relpath, request_count, environments, folders}`
- `services` — `{id, collection, env, description}` (catalog overlay + `goat.services.yml`)
- `workflows` — summaries (`id`, `description`, `env`, `steps[].request`)
- `missing_repos` / `clone_command`
- `default_env` — `catalog/stack.yaml` `bruno.default_env`
- `bru_cli.present` — whether `bru` is on PATH
- `note`

If `repos` is empty, tell the user to tag a `repositories.yml` entry `bruno` (or set `bruno.repos`) and clone it. See `docs/bruno.md`.

## Environments

`bruno envs` lists environment **names** plus variable / secret **names**. Do not invent values. Do not open the environment file to read them.

When running a request, choose `--env` in this order unless the user named one:

1. The `--env` they passed
2. The service default (`--service` or `services[].env`)
3. `default_env` when that name exists on the collection
4. Ask which environment if more than one remains

`--env-var KEY=value` is how the next bru call receives a product id, cart id, or similar. Values appear redacted in goat JSON (`<redacted>`).

## Workflows

A workflow is a **plan**, not an HTTP runner. Typical cart example: run search, pick a product from the response, then run add-to-cart with `--env-var`.

1. `uv run goat bruno workflows <id>`
2. For each `steps[]`, run `goat bruno run <request> --env <step.env>` (or the `bru_command` from the plan, from the collection cwd)
3. Read the response. Use `pick` paths as hints (`body.products[0].id`). If several products match, ask the user which to use.
4. Pass `needs` / `env_vars` into the next step as `--env-var`
5. Stop if a step fails. Do not skip ahead.

Do not invent a workflow YAML in goat. If they want a new workflow, write `goat.workflows.yml` in the Bruno collection (see `docs/bruno.md`).

## Generate a request

When they ask for a new call against an API or service:

1. `bruno collections` then `bruno requests <collection>`
2. Read **one** existing `.bru` in that folder and match its meta / method / `{{vars}}` style
3. Write a new `.bru` next to the related requests. `bruno schema` `request_template` is the skeleton
4. Put secrets in the Bruno environment (`{{token}}`), never in the request file
5. `bruno run <path> --dry-run` to confirm cwd + env, then run for real only if they asked

Do not create a second collections repo. Do not copy `.bru` files into this goat.

## After a successful inventory or run

This skill is the CLI contract, not an implementer.

1. Name the Bruno repo path and the collection you will use
2. Name the environment you will pass to bru
3. For a workflow, list the steps and what you will pick between them
4. If they asked to generate a request, write the `.bru` in the sibling and stop unless they asked to execute
5. If they asked to execute, run one step at a time and show status / errors from the CLI JSON

## Auth and setup failures

| Symptom | What to do |
| --- | --- |
| Empty `repos` / no collections | Tag a `repositories.yml` entry `bruno` and clone it (`docs/bruno.md`) |
| `missing_repos` | Show `clone_command`; do not clone into goat |
| `bru is not on PATH` | `npm install -g @usebruno/cli`. Discovery still works |
| Unknown request / collection | Re-run `bruno collections` or `bruno requests` and use an `id` or relative path |
| Ambiguous request | Pass `--collection` or the relative `.bru` path |
| `uv` missing | `docs/install-uv.md` — macOS/Linux `setup.sh`, Windows `setup.ps1` |
| `Failed to spawn: goat` / no `pyproject.toml` | Cwd is a sibling. Re-run from the goat folder or `uv run --project "$GOAT_ROOT" goat …` |

## Related Copilot customizations

- Always-on rules: `.github/copilot-instructions.md`
- Convention + workflow YAML: `docs/bruno.md`
- First-run setup: get-started skill or `/get-started`
- Ticket routing: jira-cli skill, jira-ticket skill, or `/jira-ticket`
- Figma frames: figma-cli skill or `/figma-frame`
- Local stack start: workspace-start skill or `/start-workspace`
- Implement an agreed plan: Implementer agent
- Review a diff: Reviewer agent or `/review`
- Sibling / remote agent skills: skills-install skill or `/skills-install`

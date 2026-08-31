# Bruno collections

[Bruno](https://www.usebruno.com/) is the git-backed API client (the Postman alternative). Requests live as `.bru` files in a sibling repo. The [bru CLI](https://docs.usebruno.com/bru-cli/overview) already runs a request or folder with `--env` and `--env-var`.

Yard Goat does **not** reimplement HTTP. It tells Copilot:

1. Which sibling is the Bruno repo
2. Which collections, requests, and environments exist
3. How multi-step workflows are described
4. Which `--env` to pass for a service

The **bruno-cli** skill (`.github/skills/bruno-cli/SKILL.md`) is the Copilot contract.

## Point Yard Goat at the repo

Add the collections remote to `repositories.yml` with tag `bruno` (already sketched as `api-collections`):

```yaml
  - name: api-collections
    url: git@github.com:YOUR_ORG/api-collections.git
    tags: [bruno]
    description: Bruno API collections (git-backed)
```

Or list the name explicitly in `catalog/stack.yaml`:

```yaml
bruno:
  repos: [api-collections]
  tags: [bruno]
  default_env: local
```

Then clone it like any other sibling (`goat clone --tag bruno`). Do not nest the git tree inside this goat.

A collection is a folder that contains `bruno.json`. One repo may hold several collections.

## Install bru (optional until you run requests)

Discovery (`goat bruno collections`) only reads files. Execution needs the CLI:

```bash
npm install -g @usebruno/cli
bru --version
```

`goat doctor` reports `bru_cli` as advisory when it is missing.

## Copilot commands

```bash
uv run goat bruno collections          # where the repo is + collections
uv run goat bruno requests [TARGET]    # requests in one collection (or all)
uv run goat bruno envs [COLLECTION]    # environment names + var names (never values)
uv run goat bruno workflows [NAME]     # multi-step plans
uv run goat bruno run REQUEST --env local --dry-run
uv run goat bruno schema
```

`bruno run` sets cwd to the collection root and invokes `bru run <path> --env …`. Environment variable **values** are redacted on stdout. Prefer `--dry-run` until you mean to hit an API.

## Environments

Bruno already stores environments as `environments/*.bru` inside a collection. Yard Goat lists **names** of vars and secrets, never values.

Resolution order for `bruno run`:

1. `--env` on the command
2. `--service` → that service's `env`
3. `catalog/stack.yaml` `bruno.default_env` when that name exists in the collection
4. The first environment file in the collection

Per-service defaults can live in the Bruno repo (preferred) as `goat.services.yml` next to `bruno.json` or at the repo root (`coboose.services.yml` is still read if the goat file is missing):

```yaml
services:
  - id: cart
    collection: cart-api
    env: staging
    description: Cart and checkout
  - id: search
    collection: search-api
    env: staging
```

A thin overlay is also allowed under `catalog/stack.yaml` `bruno.services`. Keep product URLs and tokens out of goat.

Pass step-specific values to bru as `--env-var KEY=value` (repeatable). That is how a cart call receives the product id from a search step.

## Workflows

Bruno can run a folder of requests in sequence, but it does not describe “search, pick a product, then add it to the cart” for Copilot. That plan lives in the Bruno repo as `goat.workflows.yml` (filename overridable via `bruno.workflows_file`; `coboose.workflows.yml` is still read if the goat file is missing):

```yaml
workflows:
  - id: add-to-cart
    description: Search the catalog, pick a product, add it to the cart
    env: staging
    service: cart
    collection: cart-api
    steps:
      - id: search
        request: search/search-products
        pick:
          product_id: body.products[0].id
      - id: add
        request: cart/add-item
        needs: [product_id]
        env_vars:
          productId: $product_id
```

`goat bruno workflows add-to-cart` prints the plan and a `bru_command` per step. Copilot (or you) still **picks** the product from the search response. Yard Goat does not auto-chain HTTP.

`pick` paths are documentation for Copilot, not a JSONPath engine.

## Generate a request

When someone asks for a new call against a service:

1. `goat bruno collections` / `bruno requests <collection>`
2. Open one existing `.bru` in that collection and match its meta/method/vars style
3. Write a new `.bru` beside the related requests
4. Use `{{envVar}}` placeholders — do not bake secrets into the file
5. `goat bruno run <path> --env local --dry-run` to confirm cwd + env

`goat bruno schema` includes `request_template`, a Bru skeleton. The [Bru language](https://docs.usebruno.com/bru-lang/overview) is the file format.

## What stays in bru vs goat

| Need | Who |
| --- | --- |
| Run one request or folder | `bru run` (or `goat bruno run` so cwd/env are resolved) |
| Select an environment | `bru --env` / `--env-var` |
| Know which sibling holds collections | goat catalog tag `bruno` |
| List collections / requests / env names | `goat bruno collections` / `requests` / `envs` |
| Multi-step “pick a product, then cart” | `goat.workflows.yml` + the bruno-cli skill |
| Service → default env | `goat.services.yml` or `bruno.services` |
| Generate a new `.bru` file | Copilot, following the skill + an existing request |

Do not curl product APIs from goat. Do not copy collection bodies into this repo.

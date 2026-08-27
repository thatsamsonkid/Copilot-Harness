# Copilot Harness

Tooling for using **GitHub Copilot in Visual Studio Code** against a multi-repo stack.

Product code does **not** live here. This repo holds:

1. A `repositories.yml` manifest of every product repo, plus feature-focused Code workspaces
2. A `templates.yml` list of starter remotes used to bootstrap **new** projects
3. A clone script that places product remotes **next to** this harness (flat siblings or grouped folders)
4. A `harness` CLI Copilot can run to list/bootstrap templates and pull Jira Cloud tickets over basic auth (no Jira MCP)

```text
parent/
  Copilot-Harness/     ← this repo
  frontend/            ← default: a flat sibling named after the repo
  backend/
  mobile/
  infra/
```

Or group clones under folders such as `frontend`, `backend`, `infra`, and `shared`:

```text
parent/
  Copilot-Harness/
  frontend/
    shop-web/
    admin/
  backend/
    api/
  infra/
    terraform/
  shared/
    design-tokens/
```

Clones stay **outside** this repository so we never nest git trees here. `group: frontend` (or `path: frontend/shop-web`) only organizes folders under `parent_dir`.

Put this repo inside a project folder (for example `~/src/Copilot-Harness`), not at the filesystem root. `parent_dir: ..` must resolve to that project folder so clones land next to the harness.

## Quick start

```bash
# macOS / Linux
./scripts/setup.sh

# Windows (PowerShell)
.\scripts\setup.ps1
```

If `uv` is not installed yet, `/get-started` and `harness init` will say so and point at [docs/install-uv.md](docs/install-uv.md) for the macOS or Windows command.

Then:

1. Edit `repositories.yml` — add each product repo (`name`, GitHub `url`, `tags`).
2. Edit `templates.yml` — add starter remotes you want Copilot or `harness bootstrap` to offer.
3. Copy `.env.example` to `.env` and set Jira Cloud values.
4. Clone product repos: `./scripts/clone-repos.sh`
5. Generate workspaces: `harness workspace generate`
6. Or create a new feature workspace and pick projects from `repositories.yml`:
   `harness workspace create` (or `/new-workspace` in chat). Choose **shared** for the team catalog, or **personal** for a local-only file under `workspaces/personal/` (gitignored).
7. Open a feature workspace, for example `workspaces/frontend.code-workspace`
8. In Copilot Chat, run **`/get-started`**, then **Jira Planner**, `/jira-ticket PROJ-123`, `/orient`, `/jira-cli`, or `/bootstrap-project`

`setup.sh` / `setup.ps1` install [uv](https://docs.astral.sh/uv/) if needed, sync `uv.lock` into `.venv`, and install this package in editable mode. Prefer `uv` over pip. Run the CLI from this repo. After `cd` into a sibling clone, `uv run harness` cannot spawn — use `--project` or the wrapper script:

```bash
uv run harness doctor
uv run --project "$HARNESS_ROOT" harness doctor   # any cwd
./scripts/harness.sh doctor                       # macOS / Linux, any cwd
.\scripts\harness.ps1 doctor                      # Windows, any cwd
```

## Repository manifest

`repositories.yml` is the source of truth for every git repo in the app:

```yaml
parent_dir: ..
repositories:
  - name: shop-web
    url: git@github.com:YOUR_ORG/shop-web.git
    tags: [ui, frontend, web]
    group: frontend
  - name: api
    url: git@github.com:YOUR_ORG/api.git
    tags: [api, backend]
    path: backend/api
```

| Field | Required | Purpose |
| --- | --- | --- |
| `name` | yes | Stable id used by workspaces, `clone --only`, and `prepare`. Not a folder path. |
| `url` | yes | GitHub clone URL (`clone_url` / `git` also accepted) |
| `tags` | yes | Labels used to clone or compose workspaces (`harness clone --tag ui`) |
| `group` | no | Organize the clone under `parent_dir/<group>/<name>` (`frontend`, `backend`, `infra`, `shared`) |
| `path` | no | Exact destination under `parent_dir`. May be nested (`frontend/shop-web`). Defaults to `name`, or `group/name` when `group` is set |
| `default_branch` | no | Defaults to `main` |
| `graphify` | no | `{ out: graphify-out }` or `false` to disable discovery |

`catalog/stack.yaml` only describes feature workspaces and Jira routing. Workspace `folders` are repository **names**, not clone paths. Workspace `tags` pull in every manifest repo with those tags. Clone, context, doctor, prepare, and generated `.code-workspace` files all resolve `group` / `path` to the real folder.

One clone cannot live inside another (`frontend` and `frontend/shop-web` together is an error). Do not point `path` at a folder inside this harness.

```bash
harness repos
harness templates
harness clone --tag api
```

One workspace should set `fallback: true` for tickets that do not match a feature set. After catalog edits, run `harness workspace generate`.

To add a workspace without editing YAML by hand:

- **Chat:** run **Workspace Creator** or `/new-workspace`. Copilot lists `repositories.yml` projects, asks for an id and which to include, then runs the CLI with flags.
- **Terminal:** `harness workspace create` prompts for the same things.

Non-interactive / after Copilot has the answers:

```bash
harness workspace create checkout --projects frontend,backend --no-prompt
harness workspace create mobile-api --tag mobile,api --name "Mobile + API"
```

That writes `catalog/stack.yaml` and `workspaces/<id>.code-workspace`. Use `--force` to replace an existing id, `--dry-run` to preview, or `--no-prompt` when flags must be complete.

For a scratch mix you do not want to commit, pass `--personal` (or choose **personal** at the prompt):

```bash
harness workspace create scratch --projects frontend,backend --personal --no-prompt
```

Personal workspaces go in `workspaces/personal/` and are gitignored. They are not added to `catalog/stack.yaml` and do not participate in Jira routing. Shared workspaces stay the default so the team catalog does not change unless you ask.

Workspace files always include this harness as the first root so Copilot still sees the CLI and instructions.

## Project templates

`templates.yml` is separate from the product stack. Use it when someone needs a new repo rather than a clone of an existing app.

```yaml
templates:
  - name: spartan-stack
    url: git@github.com:thatsamsonkid/spartan-stack-starter.git
    tags: [frontend, fullstack, angular]
    description: Opinionated Spartan / Analog fullstack starter
    language: typescript
    kind: fullstack
```

| Field | Required | Purpose |
| --- | --- | --- |
| `name` | yes | Stable id passed to `--template` |
| `url` | yes | GitHub clone URL of the starter |
| `tags` | yes | Labels used to filter (`harness templates --tag mobile`) |
| `description` | no | Shown in the template list |
| `language` | no | Primary language hint for Copilot |
| `kind` | no | `frontend`, `backend`, `mobile`, `fullstack`, … |
| `default_branch` | no | Defaults to `main` |

```bash
harness templates
harness templates --tag mobile
harness templates react-native
harness bootstrap --template react-native --name shop-mobile
harness bootstrap --template spartan-stack --name shop-web --https --dry-run
```

`bootstrap` clones the listed starter under `parent_dir` (never inside this harness), then renames `origin` to `template` so you do not push back to the starter. Optional flags:

| Flag | Effect |
| --- | --- |
| `--name` | Project id, or a destination under `parent_dir` such as `frontend/shop-web` (defaults to the template name) |
| `--group` | Place the clone at `parent_dir/<group>/<name>` |
| `--https` | Rewrite `git@github.com:` URLs to HTTPS |
| `--fresh-git` | Replace template history with one bootstrap commit |
| `--keep-remote` | Leave `origin` pointing at the template |
| `--remote` | Set `origin` on the new project |
| `--register` | Append the project to `repositories.yml` |
| `--tags` | Tags to store when registering |
| `--dry-run` | Print the plan without cloning |

Copilot uses the same commands. If you ask it to bootstrap a new project, it should run `harness templates` and then `harness bootstrap --template <name> --name <folder>` instead of scaffolding from scratch. The `/bootstrap-project` prompt follows that loop.

## Jira CLI (basic auth)

Jira Cloud MCP is not available here. Copilot talks to Jira by running `harness`. The **jira-cli** skill (`.github/skills/jira-cli/SKILL.md`) is the on-demand contract for those commands.

Create an API token using [docs/jira-api-token.md](docs/jira-api-token.md) (or the [Atlassian token page](https://id.atlassian.com/manage-profile/security/api-tokens)) and set:

```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=...
```

```bash
uv run harness init
uv run harness jira schema
uv run harness jira whoami
uv run harness jira get PROJ-123
uv run harness jira context PROJ-123
uv run harness jira search 'project = PROJ AND status != Done'
uv run harness prepare PROJ-123
uv run harness context
uv run harness start --workspace frontend
uv run harness start run --repo backend --dry-run
```

The CLI never prints the raw Jira REST payload. `catalog/stack.yaml` `jira.fields` is an allowlist of keys Copilot sees. Add custom fields with `extra_fields` + `field_aliases`, then list the alias in `fields`.

The API token stays in `.env`. The CLI loads it in-process for Basic auth. Copilot instructions forbid reading `.env`, curling Atlassian, or using a Jira MCP server.

`prepare` is the Copilot entry point: fetch the filtered issue, score feature workspaces, list required sibling repos, and print the `code` command that opens the matching workspace.

`harness start` is the local-stack entry point: inspect the workspace siblings and print a start **plan** (kind, command, port hint, Angular proxy files, redacted `launch.json` names and env keys). It does not launch processes. After the first good plan, pin it next to the workspace with `harness start --workspace <id> --save`. That writes `workspaces/<id>.start.yml` (or `workspaces/personal/<id>.start.yml`). Later starts prefer that sequence over rediscovery; pass `--refresh` to inspect clones again. Copilot uses `/start-workspace` to start backends one at a time, read the live port, rewrite frontend proxies, then start UIs. When a repo keeps args or secrets in `.vscode/launch.json`, the plan sets `run_via: harness` and Copilot runs `harness start run --repo <name>` so those values stay in-process (or the user uses VS Code **Run Without Debugging**). Do not put `start:` on `repositories.yml` entries — edit the workspace plan when discovery is wrong.

Stdout is JSON by default (`--format markdown` or `text` if you want a human view). Errors are JSON on stderr.

## Clone script

```bash
./scripts/clone-repos.sh
./scripts/clone-repos.sh --only frontend,backend
./scripts/clone-repos.sh --update
./scripts/clone-repos.sh --https --dry-run
```

Clones always land in `parent_dir` from `repositories.yml` (default `..`), including grouped paths such as `frontend/shop-web`. Placeholder URLs that still contain `YOUR_ORG` are refused so a half-edited manifest cannot create junk remotes.

## Copilot in VS Code

| File | Role |
| --- | --- |
| `.github/skills/get-started/SKILL.md` | First-run walkthrough (`/get-started`) |
| `.github/skills/workspace-context/SKILL.md` | Graphify + sibling standards (`/orient`) |
| `.github/skills/workspace-start/SKILL.md` | Local stack plan + sequential start (`/start-workspace`) |
| `.github/skills/jira-cli/SKILL.md` | On-demand Jira CLI contract (`/jira-cli`) |
| `.github/copilot-instructions.md` | Always-on workspace rules |
| `AGENTS.md` | Same rules for other agents |
| `.github/prompts/jira-ticket.prompt.md` | `/jira-ticket` |
| `.github/prompts/new-workspace.prompt.md` | `/new-workspace` |
| `.github/prompts/orient.prompt.md` | `/orient` |
| `.github/prompts/start-workspace.prompt.md` | `/start-workspace` |
| `.github/prompts/bootstrap-project.prompt.md` | `/bootstrap-project` |
| `.github/agents/jira-planner.agent.md` | Plan from a ticket |
| `.github/agents/workspace-creator.agent.md` | Create a workspace from chat |
| `.github/agents/implementer.agent.md` | Implement an agreed plan |

The **jira-cli** skill is the CLI contract: which command to run, JSON shapes, and the no-MCP / no-token rules. Copilot can load it automatically or you can invoke `/jira-cli`. Jira Planner and `/jira-ticket` stay the planning workflow; they now point at the skill instead of restating the command catalog.

`/get-started` is the human onboarding path. It runs `harness init` and points at the token doc. Copilot must never ask anyone to paste the API token into chat.

`/orient` is for vague prompts against large repos. It runs `harness context`, reads any sibling `graphify-out/GRAPH_REPORT.md`, and loads that repo's own instructions instead of inventing standards here.

`/start-workspace` is for booting the local apps in the open feature workspace. It runs `harness start`, prefers a saved `workspaces/<id>.start.yml` when present, then starts one process at a time in **one VS Code terminal per app** (reuse that app’s terminal if it is already running) so Angular proxies can point at live backend ports. Apps with launch.json env/args are started through `harness start run` or Run Without Debugging so Copilot never sees those values.

Product feature notes and ADRs stay in the sibling repos (`docs/features/`, `docs/adr/`). The harness only discovers them. Convention: [docs/knowledge.md](docs/knowledge.md). More ideas: [docs/ideas.md](docs/ideas.md).

Typical loop:

1. New machine: `/get-started` (or `uv run harness init --interactive` in a terminal)
2. You paste `PROJ-123` into chat, Jira Planner, `/jira-ticket`, or `/jira-cli`
3. Copilot runs `harness prepare PROJ-123`
4. You open the recommended `.code-workspace` so every needed repo is a root
5. To run the local apps: `/start-workspace` (or `uv run harness start --workspace <id>`). Save the sequence once with `--save` so later chats reuse `workspaces/<id>.start.yml`.
6. Copilot writes a plan (using Graphify reports and each repo's instructions when present), then hands off to Implementer when you are ready

To add a workspace from chat, run **Workspace Creator** or `/new-workspace` instead of editing YAML.

## Tests

```bash
uv sync
uv run pytest
```

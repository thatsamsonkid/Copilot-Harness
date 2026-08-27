# Copilot Harness

Tooling for using **GitHub Copilot in Visual Studio Code** against a multi-repo stack.

Product code does **not** live here. This repo holds:

1. A `repositories.yml` manifest of every product repo, plus feature-focused Code workspaces
2. A clone script that places those remotes as **siblings** of this harness
3. A `harness` CLI Copilot can run to pull Jira Cloud tickets over basic auth (no Jira MCP)

```text
parent/
  Copilot-Harness/     ← this repo
  frontend/            ← sibling clone
  backend/
  mobile/
  infra/
```

Keeping clones beside the harness avoids nested git trees and keeps this repository free of application history.

Put this repo inside a project folder (for example `~/src/Copilot-Harness`), not at the filesystem root. `parent_dir: ..` must resolve to that project folder so siblings land next to the harness.

## Quick start

```bash
./scripts/setup.sh
```

Then:

1. Edit `repositories.yml` — add each product repo (`name`, GitHub `url`, `tags`).
2. Copy `.env.example` to `.env` and set Jira Cloud values.
3. Clone siblings: `./scripts/clone-repos.sh`
4. Generate workspaces: `harness workspace generate`
5. Open a feature workspace, for example `workspaces/frontend.code-workspace`
6. In Copilot Chat, run **`/get-started`**, then **Jira Planner**, `/jira-ticket PROJ-123`, or `/orient`

`setup.sh` installs [uv](https://docs.astral.sh/uv/) if needed, syncs `uv.lock` into `.venv`, and installs this package in editable mode. Prefer `uv` over pip:

```bash
uv run harness doctor
```

## Repository manifest

`repositories.yml` is the source of truth for every git repo in the app:

```yaml
parent_dir: ..
repositories:
  - name: frontend
    url: git@github.com:YOUR_ORG/frontend.git
    tags: [ui, frontend, web]
  - name: backend
    url: git@github.com:YOUR_ORG/backend.git
    tags: [api, backend]
```

| Field | Required | Purpose |
| --- | --- | --- |
| `name` | yes | Stable id and default sibling folder name |
| `url` | yes | GitHub clone URL (`clone_url` / `git` also accepted) |
| `tags` | yes | Labels used to clone or compose workspaces (`harness clone --tag ui`) |
| `path` | no | Override the sibling folder name |
| `default_branch` | no | Defaults to `main` |
| `graphify` | no | `{ out: graphify-out }` or `false` to disable discovery |

`catalog/stack.yaml` only describes feature workspaces and Jira routing. Workspace `folders` are repository names. Workspace `tags` pull in every manifest repo with those tags.

```bash
harness repos
harness clone --tag api
```

One workspace should set `fallback: true` for tickets that do not match a feature set. After catalog edits, run `harness workspace generate`.

Workspace files live in `workspaces/` and always include this harness as the first root so Copilot still sees the CLI and instructions.

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
```

The CLI never prints the raw Jira REST payload. `catalog/stack.yaml` `jira.fields` is an allowlist of keys Copilot sees. Add custom fields with `extra_fields` + `field_aliases`, then list the alias in `fields`.

The API token stays in `.env`. The CLI loads it in-process for Basic auth. Copilot instructions forbid reading `.env`, curling Atlassian, or using a Jira MCP server.

`prepare` is the Copilot entry point: fetch the filtered issue, score feature workspaces, list required sibling repos, and print the `code` command that opens the matching workspace.

Stdout is JSON by default (`--format markdown` or `text` if you want a human view). Errors are JSON on stderr.

## Clone script

```bash
./scripts/clone-repos.sh
./scripts/clone-repos.sh --only frontend,backend
./scripts/clone-repos.sh --update
./scripts/clone-repos.sh --https --dry-run
```

Clones always land in `parent_dir` from `repositories.yml` (default `..`). Placeholder URLs that still contain `YOUR_ORG` are refused so a half-edited manifest cannot create junk remotes.

## Copilot in VS Code

| File | Role |
| --- | --- |
| `.github/skills/get-started/SKILL.md` | First-run walkthrough (`/get-started`) |
| `.github/skills/workspace-context/SKILL.md` | Graphify + sibling standards (`/orient`) |
| `.github/skills/jira-cli/SKILL.md` | On-demand Jira CLI contract (`/jira-cli`) |
| `.github/copilot-instructions.md` | Always-on workspace rules |
| `AGENTS.md` | Same rules for other agents |
| `.github/prompts/jira-ticket.prompt.md` | `/jira-ticket` |
| `.github/agents/jira-planner.agent.md` | Plan from a ticket |
| `.github/agents/implementer.agent.md` | Implement an agreed plan |

The **jira-cli** skill is the CLI contract: which command to run, JSON shapes, and the no-MCP / no-token rules. Copilot can load it automatically or you can invoke `/jira-cli`. Jira Planner and `/jira-ticket` stay the planning workflow; they now point at the skill instead of restating the command catalog.

`/get-started` is the human onboarding path. It runs `harness init` and points at the token doc. Copilot must never ask anyone to paste the API token into chat.

`/orient` is for vague prompts against large repos. It runs `harness context`, reads any sibling `graphify-out/GRAPH_REPORT.md`, and loads that repo's own instructions instead of inventing standards here.

Product feature notes and ADRs stay in the sibling repos (`docs/features/`, `docs/adr/`). The harness only discovers them. Convention: [docs/knowledge.md](docs/knowledge.md). More ideas: [docs/ideas.md](docs/ideas.md).

Typical loop:

1. New machine: `/get-started` (or `uv run harness init --interactive` in a terminal)
2. You paste `PROJ-123` into chat, Jira Planner, `/jira-ticket`, or `/jira-cli`
3. Copilot runs `harness prepare PROJ-123`
4. You open the recommended `.code-workspace` so every needed repo is a root
5. Copilot writes a plan (using Graphify reports and each repo's instructions when present), then hands off to Implementer when you are ready

## Tests

```bash
uv sync
uv run pytest
```

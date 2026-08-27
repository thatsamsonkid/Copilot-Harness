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
6. In Copilot Chat, run **Jira Planner** or `/jira-ticket PROJ-123`

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

`catalog/stack.yaml` only describes feature workspaces and Jira routing. Workspace `folders` are repository names. Workspace `tags` pull in every manifest repo with those tags.

```bash
harness repos
harness clone --tag api
```

One workspace should set `fallback: true` for tickets that do not match a feature set. After catalog edits, run `harness workspace generate`.

Workspace files live in `workspaces/` and always include this harness as the first root so Copilot still sees the CLI and instructions.

## Jira CLI (basic auth)

Jira Cloud MCP is not available here. Copilot talks to Jira by running `harness`.

Create an API token at [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens) and set:

```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=...
```

```bash
uv run harness jira schema
uv run harness jira whoami
uv run harness jira get PROJ-123
uv run harness jira context PROJ-123
uv run harness jira search 'project = PROJ AND status != Done'
uv run harness prepare PROJ-123
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
| `.github/copilot-instructions.md` | Always-on workspace rules |
| `AGENTS.md` | Same rules for other agents |
| `.github/prompts/jira-ticket.prompt.md` | `/jira-ticket` |
| `.github/agents/jira-planner.agent.md` | Plan from a ticket |
| `.github/agents/implementer.agent.md` | Implement an agreed plan |

Typical loop:

1. You paste `PROJ-123` into Jira Planner or `/jira-ticket`
2. Copilot runs `harness prepare PROJ-123`
3. You open the recommended `.code-workspace` so every needed repo is a root
4. Copilot writes a plan, then hands off to Implementer when you are ready

## Tests

```bash
uv sync
uv run pytest
```

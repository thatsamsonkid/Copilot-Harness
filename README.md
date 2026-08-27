# Copilot Harness

Tooling for using **GitHub Copilot in Visual Studio Code** against a multi-repo stack.

Product code does **not** live here. This repo holds:

1. A catalog of git remotes and feature-focused Code workspaces
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

1. Edit `catalog/stack.yaml` — replace `YOUR_ORG` remotes with your team's repositories.
2. Copy `.env.example` to `.env` and set Jira Cloud values.
3. Clone siblings: `./scripts/clone-repos.sh`
4. Generate workspaces: `harness workspace generate`
5. Open a feature workspace, for example `workspaces/frontend.code-workspace`
6. In Copilot Chat, run **Jira Planner** or `/jira-ticket PROJ-123`

`setup.sh` creates a virtualenv and an editable install so the `harness` command is on PATH inside `.venv`.

```bash
source .venv/bin/activate
harness doctor
```

Without the venv:

```bash
PYTHONPATH=src python3 -m harness doctor
```

## Catalog

`catalog/stack.yaml` is the source of truth.

| Block | Purpose |
| --- | --- |
| `repos` | Remote URL, sibling folder `path`, default branch, tags |
| `workspaces` | Feature multi-root sets (`folders` are repo ids) |
| `workspaces[].match` | Jira project / component / label / keyword routing |
| `jira.extra_fields` | Extra custom field ids to include on issue fetch |

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
harness jira whoami
harness jira get PROJ-123
harness jira context PROJ-123
harness jira search 'project = PROJ AND status != Done'
harness prepare PROJ-123
```

`prepare` is the Copilot entry point: fetch the issue and comments, score feature workspaces, list required sibling repos, and print the `code` command that opens the matching workspace.

Stdout is JSON by default (`--format markdown` or `text` if you want a human view). Errors are JSON on stderr.

## Clone script

```bash
./scripts/clone-repos.sh
./scripts/clone-repos.sh --only frontend,backend
./scripts/clone-repos.sh --update
./scripts/clone-repos.sh --https --dry-run
```

Clones always land in `parent_dir` from the catalog (default `..`). Placeholder URLs that still contain `YOUR_ORG` are refused so a half-edited catalog cannot create junk remotes.

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
python3 -m pip install -e ".[dev]"
pytest
```

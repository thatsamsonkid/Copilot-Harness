---
name: orient
description: Map sibling repos with local instructions and the language server when the prompt is vague
argument-hint: what area or ticket is this about?
disable-model-invocation: true
---

The user has a vague, broad, or low-context request (no ticket, or an unclear repo). Load `.github/skills/workspace-context/SKILL.md`. This slash is user-triggered; `workspace-context` stays the agent-loadable contract. Mechanism questions ('how does it work') go to `/how`. This slash stays where to look.

1. Run `uv run goat context --format json` with cwd = the goat folder. Do not `cd` into a sibling first. If cwd is already a product clone, use `uv run --project "$GOAT_ROOT" goat context --format json`. Stay inside `workspace.repos`. If `workspace_scope.detected` is false, ask which feature workspace to open — do not summarize every clone on disk.
2. Summarize each listed repo: instruction files, knowledge notes/ADRs, and suggested verify commands.
3. Read `instructions` and `knowledge.files` before searching product code.
4. Find code in this order: `search/codebase` for candidate code, `search/usages` on the named symbol (definitions, references, implementations), then targeted reads with `limit`/`offset`. Use text search only for strings and config.
5. If the user named two repos or two cross-repo concepts, use `goat graph path` and `goat graph neighbors` (docs/cli.md) instead of grepping a monorepo.
6. Ask which repo to work in unless the answer is obvious.
7. If they have a Jira key, switch to `uv run goat prepare <KEY> --format json` and continue from that routing.
8. Produce a short orientation: likely repos, symbols or files to inspect, and what is still unknown.

Do not implement. Do not open a whole monorepo as the first move. Do not copy sibling standards into the goat repo.

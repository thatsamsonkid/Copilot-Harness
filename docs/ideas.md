# Harness ideas

The three themes below are the ones we started with. The harness should stay a thin orchestration layer: sibling clones, Jira via CLI, and enough Copilot customizations that a new teammate can get oriented without reading the whole stack.

What we should **not** do: copy product architecture or style guides into this repo. Those live in the product repos and will drift if we fork them here.

## 1. Easy startup

**In this PR**

- `/get-started` walks a human through `.env`, the token doc, `repositories.yml`, and clone/workspace generate.
- `harness init` prints that checklist as JSON. `--interactive` collects email/URL/token in a local TTY only.
- `docs/jira-api-token.md` is the token how-to.
- `docs/install-uv.md` plus `setup.sh` / `setup.ps1` so `/get-started` can send macOS and Windows users to the right uv install.

**Worth adding next**

- `setup.sh` should finish by running `harness init` so the first-run checklist is the last thing a person sees.
- Token expiry in `doctor` (Atlassian tokens die in ≤ 1 year). Warn when `.env` is older than ~10 months; do not try to read the token’s expiry from Atlassian unless we have a safe API for it.
- Two token profiles in the doc: read-only for planning, write scopes only if we later add `harness jira comment` / transition.
- VS Code welcome: keep `/get-started` in `chat.promptFilesRecommendations` so a blank chat offers it.
- A one-page “new laptop” checklist in the README that is only five commands long. Anything longer and people skip it.

## 2. Large repos and Graphify

Workspaces can include very large repos or monorepos. Graphify already lives *in those repos*. The harness should discover and point at those graphs, not rebuild the world from here.

**In this PR**

- Optional `graphify.out` on each `repositories.yml` entry (default `graphify-out`).
- `harness context` reports whether `GRAPH_REPORT.md` / `graph.json` exist, plus query/path/explain commands.
- `prepare` and `/orient` tell Copilot to read the report before grepping.
- Always-on instructions: vague prompt → context/graph first, then ask which community/repo.

**Worth adding next**

- **Do not** run `graphify extract` on a whole monorepo from the harness. If a graph is missing, offer a *scoped* rebuild (`graphify extract --code-only path/to/package`) and only after the user agrees.
- Staleness: compare `graph.json` mtime to `git log -1 --format=%ct` in that sibling. Advisory only.
- Cross-repo tickets (platform workspace): `graphify merge-graphs` into a harness-local file such as `graphify-out/workspace-<id>.json`, namespaced per repo. Keep that output gitignored. Use it for “how does frontend talk to billing?” questions; keep per-repo graphs for implementation.
- After Implementer edits files, remind the user to refresh the *touched* repo’s graph. Do not auto-refresh during the session unless they ask.
- If Graphify is not installed, `doctor` should say so once, then still use any committed `graphify-out/` artifacts.
- For Nx/Turborepo monorepos, prefer Graphify communities + `nx show project` / `turbo run` over opening the whole tree.

## 3. Standards and patterns

Individual repos already have instructions and tooling. The harness should make Copilot *find and obey* those, not invent a second style guide.

**In this PR**

- `harness context` lists `.github/copilot-instructions.md`, `AGENTS.md`, path instructions, skills, and suggested verify commands (`make check`, `pnpm lint`, …).
- Implementer / always-on rules: load those files before editing; run `tooling.suggested_verify` after.
- Harness-level rules stay limited to secrets, sibling clones, and Jira-via-CLI.

**Worth adding next**

- A `/review-standards` prompt that diffs the working tree against the target repo’s linters/formatters only.
- Discover generated-code markers (Nx, OpenAPI, graphql-codegen) and tell Copilot not to hand-edit those outputs.
- Org-wide *invariants* only if they are few and stable: Jira key in the branch name, no secrets, one PR per sibling repo. Put those here. Everything else stays in the product repo.
- A tiny eval folder later: 3–5 golden tickets plus “did the agent read AGENTS.md and run the repo test command?” That is how we enforce behavior without hoping the prompt is enough.

## 4. Product knowledge (not a harness wiki)

**Yes, write it down. No, do not file it here.**

Feature notes and ADRs belong in the product repo that changed (`docs/features/`, `docs/adr/`). Graphify already indexes markdown, ADRs, and `# WHY:` comments. A second knowledge base in this harness will drift the same way a copied style guide would.

**In this PR**

- `harness context` / `prepare` list sibling knowledge dirs and files.
- `templates/feature-note.md` is the short template Copilot copies *into the sibling*.
- `docs/knowledge.md` is the convention.

**Worth adding next**

- Implementer reminder only when the diff adds user-visible behavior, not on every lint fix.
- After a feature note lands, offer a *scoped* Graphify refresh in that repo.
- Optional `knowledge.dirs` override on a `repositories.yml` entry if a monorepo keeps notes somewhere else.
- Confluence later, and only for specs that already live there — never as the implementation source of truth.

## 5. Local stack start

Workspaces mix Java, Angular, and other apps. A single `docker-compose`-style "start everything" command fails for the reasons the stack is messy: start commands differ, some ports are only known after boot, and Angular `proxy.conf` files have to point at those live local backends.

**In this PR**

- `harness start` inspects workspace siblings and prints a JSON plan: kind, command, port hint, proxy files, start order. It does **not** launch processes.
- Optional thin `repositories.yml` `start:` override (`command`, `port`, `role`, `wait`) when discovery is wrong.
- `/start-workspace` plus the workspace-start skill tell Copilot to start **one app at a time**: backends first, read the live port, rewrite frontend proxies in the working tree, then start UIs.

**Worth adding next**

- `harness start status` that probes `listen:<port>` / health URLs after the agent has started things.
- A gitignored `.harness/runtime.json` of last-known ports for the session (never commit it).
- A generated local proxy overlay instead of editing the committed `proxy.conf.json`, if teams do not want dirty trees.
- Compose profiles only when the user asks; do not make compose the default start path.

## Other ideas (when you are ready)

These are separate from the three themes but fit the same harness:

- **`/handoff`** — write a session note under `handoffs/` in the harness (not in product repos) so the next chat can resume without re-fetching the world.
- **Jira write path** — `harness jira comment` / transition, still CLI-only, still no token in chat. Wait until read-only onboarding is boringly reliable.
- **Definition of done** — prepare JSON grows a `done_when` list from the ticket’s acceptance criteria plus each repo’s verify commands.
- **Branch names** — `harness branch PROJ-123` creates the same prefix in each matched sibling.
- **PR body** — a prompt that reads `prepare` JSON and the sibling diff, then opens one PR per repo.
- **Confluence** — only if ticket descriptions are routinely incomplete and the real spec lives there. Same rule as Jira: CLI or MCP, never raw tokens in chat.

When you have the next batch of ideas, we can add them here and promote one slice at a time.

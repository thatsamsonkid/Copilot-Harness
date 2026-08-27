# Harness ideas

The harness should stay a thin orchestration layer: sibling clones, Jira via CLI, and enough Copilot customizations that a new teammate can get oriented without reading the whole stack.

What we should **not** do: copy product architecture or style guides into this repo. Those live in the product repos and will drift if we fork them here.

## 1. Easy startup

**Shipped**

- `/get-started`, `harness init` / `--interactive`, token doc, uv install docs, `setup.sh` / `setup.ps1`.
- Setup scripts finish by running `harness init --format text`.
- `doctor` warns when `.env` is older than ~10 months (Atlassian tokens die in ≤ 1 year). It does not read token expiry from Atlassian.
- Two token profiles in `docs/jira-api-token.md` (planning vs later write).
- VS Code `chat.promptFilesRecommendations` includes `/get-started`, `/handoff`, `/review`.
- README "New laptop" is five commands.

**Worth adding next**

- Nothing urgent here. A VS Code welcome walkthrough page is optional polish.

## 2. Large repos and Graphify

**Shipped**

- Discover `graphify-out/` per sibling. `context` / `prepare` / `status` report `graphify.stale` by comparing `graph.json` mtime to the latest commit.
- `doctor` notes when the Graphify CLI is missing and still uses committed artifacts.
- Instructions: never extract a whole monorepo; offer a scoped rebuild only after the user agrees.

**Worth adding next**

- Cross-repo tickets: `graphify merge-graphs` into a gitignored `graphify-out/workspace-<id>.json`, namespaced per repo.
- After Implementer edits, a one-line reminder is already in the agent. Auto-refresh is still a no.
- For Nx/Turborepo, prefer Graphify communities + `nx show project` / `turbo run` over opening the whole tree.

## 3. Standards and patterns

**Shipped**

- `harness context` lists instruction files, verify commands, and generated-code markers (Nx, OpenAPI, graphql-codegen).
- `/review` + Reviewer agent: diff against `done_when`, local linters, generated-code, and harness invariants.
- Org-wide invariants in always-on instructions: Jira key in the branch, one PR per sibling, no secrets, obey `done_when`.

**Worth adding next**

- Discover more generated-code globs from each repo's own ignore/codegen config instead of a fixed list.
- A tiny eval folder later: 3–5 golden tickets plus “did the agent read AGENTS.md and run the repo test command?”

## 4. Product knowledge (not a harness wiki)

**Shipped**

- Discover sibling `docs/features`, ADRs, and optional `knowledge.dirs` on a `repositories.yml` entry.
- Feature-note template copied *into the sibling*. Implementer reminds only on user-visible changes.

**Worth adding next**

- After a feature note lands, offer a *scoped* Graphify refresh in that repo.
- Confluence later, and only for specs that already live there — never as the implementation source of truth.

## 5. Day-to-day ticket loop (this PR)

This is the slice people feel after onboarding: prepare is not enough once work starts.

**Shipped**

- `harness status` — branch, dirty, ahead/behind, Graphify staleness, “you opened a single folder” hint.
- `harness branch PROJ-123` — same Jira-key branch in each sibling; `--create` only on a clean tree.
- `prepare` `done_when` — ticket acceptance criteria + each repo's verify commands + harness invariants.
- `/handoff` + `harness handoff write/latest` — session notes under `handoffs/` (gitignored).
- `harness jira mine` — unresolved issues assigned to the current user.

**Worth adding next**

- `harness pr PROJ-123` — one draft PR per dirty sibling via `gh`, body from `prepare` JSON + that repo's diff. Still no mega-PR.
- Secret scan of the sibling diff before commit (`.env`, tokens, private keys). Instructions are not a sandbox.

## Other ideas (when you are ready)

These are separate from the themes above but fit the same harness:

- **Jira write path** — `harness jira comment` / transition, still CLI-only, still no token in chat. Wait until read-only onboarding stays boringly reliable.
- **Worktrees** — `harness worktree PROJ-123` so Implementer does not dirty a shared checkout that someone else has open.
- **Personal overlay** — optional gitignored `repositories.local.yml` for extra remotes you do not want to commit.
- **Sparse / partial clone hints** — for a huge monorepo, `clone` can suggest `git clone --filter=blob:none` / sparse-checkout of the package Graphify named. Do not invent the sparse paths here.
- **Pinned SHAs** — a `lock` file of sibling commit SHAs so a Cloud Agent / eval run is reproducible. Optional, not for daily work.
- **CI awareness** — `gh pr checks` per sibling before anyone says “ship it.” GitHub MCP is fine; Jira MCP is not.
- **MCP allowlist in instructions** — say explicitly: GitHub MCP okay, Jira MCP never. Stops a well-meaning teammate from installing Atlassian MCP “to help.”
- **Assignment board in chat** — `/mine` prompt that runs `jira mine` then `prepare` on the chosen key. Thin wrapper; only add if people keep forgetting the command.

When you have the next batch of ideas, we can add them here and promote one slice at a time.

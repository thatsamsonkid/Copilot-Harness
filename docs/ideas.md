# Goat ideas

The three themes below are the ones we started with. The goat should stay a thin orchestration layer: sibling clones, Jira via CLI, and enough Copilot customizations that a new teammate can get oriented without reading the whole stack.

What we should **not** do: copy product architecture or style guides into this repo. Those live in the product repos and will drift if we fork them here.

## 1. Easy startup

**Shipped**

- `/get-started` walks a human through `.env`, the token doc, `repositories.yml`, and clone/workspace generate.
- `goat init` prints that checklist as JSON. `--interactive` collects email/URL/token in a local TTY only.
- Setup scripts finish by running `goat init --format text`.
- `jira login` stores the API token in macOS Keychain or Windows Credential Manager. `.env` is a fallback.
- `doctor` warns when `.env` is older than ~10 months (Atlassian tokens die in ≤ 1 year). That age is advisory: tokens in the OS keychain are not dated by the file. Doctor does not read token expiry from Atlassian.
- Two token profiles in `docs/jira-api-token.md` (planning vs later write).
- VS Code `chat.promptFilesRecommendations` includes `/get-started`, `/handoff`, `/review`, `/skills-install`.
- README "New laptop" is five commands.

**Worth adding next**

- Nothing urgent here. A VS Code welcome walkthrough page is optional polish.

**Temporary VS Code Agents shim**

- Agents does not scan multi-root child skills. `goat skills list` / `lift` / `pull` copy selected `SKILL.md` folders into this goat `.github/skills` (or `parent_dir/.github/skills` with `--parent`). `init`, `prepare`, and `workspace generate` already lift goat + in-scope siblings. Remove the overlay when Agents grows real multi-root support.

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

- `goat context` lists instruction files, verify commands, and generated-code markers (Nx, OpenAPI, graphql-codegen).
- `/review` + Reviewer agent: diff against `done_when`, local linters, generated-code, and goat invariants.
- Org-wide invariants in always-on instructions: Jira key in the branch, one PR per sibling, no secrets, obey `done_when`.
- Language packs for TypeScript, Python, and Java: path-scoped `*.instructions.md`, on-demand skills, `/typescript` `/python` `/java`. `context` / `prepare` infer `language` from `repositories.yml`, tags, or lockfiles. Product style still stays in the sibling.

**Worth adding next**

- Discover more generated-code globs from each repo's own ignore/codegen config instead of a fixed list.
- A tiny eval folder later: 3–5 golden tickets plus “did the agent read AGENTS.md and run the repo test command?”

## 4. Product knowledge (not a goat wiki)

**Shipped**

- Discover sibling `docs/features`, ADRs, and optional `knowledge.dirs` on a `repositories.yml` entry.
- Feature-note template copied *into the sibling*. Implementer reminds only on user-visible changes.
- `docs/knowledge.md` is the convention.

**Worth adding next**

- After a feature note lands, offer a *scoped* Graphify refresh in that repo.
- Confluence later, and only for specs that already live there — never as the implementation source of truth.

## 5. Day-to-day ticket loop

This is the slice people feel after onboarding: prepare is not enough once work starts.

**Shipped**

- `goat status` — branch, dirty, ahead/behind, Graphify staleness, “you opened a single folder” hint.
- `goat branch PROJ-123` — same Jira-key branch in each sibling; `--create` only on a clean tree.
- `prepare` `done_when` — ticket acceptance criteria + each repo's verify commands + goat invariants.
- `/handoff` + `goat handoff write/latest` — session notes under `handoffs/` (gitignored).
- `goat jira mine` — unresolved issues assigned to the current user.

**Worth adding next**

- `goat pr PROJ-123` — one draft PR per dirty sibling via `gh`, body from `prepare` JSON + that repo's diff. Still no mega-PR.
- Secret scan of the sibling diff before commit (`.env`, tokens, private keys). Instructions are not a sandbox.

## 6. Local stack start

Workspaces mix Java, Angular, and other apps. A single `docker-compose`-style "start everything" command fails for the reasons the stack is messy: start commands differ, some ports are only known after boot, and Angular `proxy.conf` files have to point at those live local backends.

**Shipped**

- `goat start` inspects workspace siblings and prints a JSON plan: kind, command, port hint, proxy files, start order. It does **not** launch processes.
- `/start-workspace` plus the workspace-start skill tell Copilot to start **one app at a time**: backends first, read the live port, rewrite frontend proxies in the working tree, then start UIs.
- `goat start --workspace <id> --save` writes `workspaces/<id>.start.yml` next to the `.code-workspace` file. Later starts prefer that sequence. `--refresh` rediscovers. Do not put `start:` on `repositories.yml` entries.
- Java `launch.json` env/args are discovered as names and keys only. `run_via: goat` means Copilot runs `goat start run --repo <name>` (secrets stay in-process). `run_via: vscode` means Run Without Debugging on the named configuration, not Debug.

**Worth adding next**

- `goat start status` that probes `listen:<port>` / health URLs after the agent has started things.
- A gitignored `.goat/runtime.json` of last-known ports for the session (never commit it).
- A generated local proxy overlay instead of editing the committed `proxy.conf.json`, if teams do not want dirty trees.
- Compose profiles only when the user asks; do not make compose the default start path.

## Other ideas (when you are ready)

These are separate from the themes above but fit the same goat:

- **Jira write path** — `goat jira comment` / transition, still CLI-only, still no token in chat. Wait until read-only onboarding stays boringly reliable.
- **Worktrees** — `goat worktree PROJ-123` so Implementer does not dirty a shared checkout that someone else has open.
- **Personal overlay** — optional gitignored `repositories.local.yml` for extra remotes you do not want to commit.
- **Sparse / partial clone hints** — for a huge monorepo, `clone` can suggest `git clone --filter=blob:none` / sparse-checkout of the package Graphify named. Do not invent the sparse paths here.
- **Pinned SHAs** — a `lock` file of sibling commit SHAs so a Cloud Agent / eval run is reproducible. Optional, not for daily work.
- **CI awareness** — `gh pr checks` per sibling before anyone says “ship it.” GitHub MCP is fine; Jira MCP is not.
- **MCP allowlist in instructions** — say explicitly: GitHub MCP okay, Jira MCP never. Stops a well-meaning teammate from installing Atlassian MCP “to help.”
- **Assignment board in chat** — `/mine` prompt that runs `jira mine` then `prepare` on the chosen key. Thin wrapper; only add if people keep forgetting the command.
- **Figma comments / targeted raw nodes** — shipped as `figma comments` (allowlisted) and `figma nodes` (raw Figma node map, depth-capped, targeted frames only). Images stay the visual source of truth. Variable names / tokens stay a later clip if designers actually write them.

## 7. Bruno API collections

**Shipped**

- Tag a sibling `bruno` (example: `api-collections` in `repositories.yml`) or list it in `catalog/stack.yaml` `bruno.repos`.
- `goat bruno collections` / `requests` / `envs` / `workflows` / `run` / `schema`. Discovery reads `bruno.json` and `.bru` files. `run` only wraps `bru` with the collection cwd and `--env`.
- Workflows live in the Bruno repo as `goat.workflows.yml` (search → pick a product → cart). Yard Goat prints the plan; Copilot picks values and passes `--env-var`.
- Service → default env via `goat.services.yml` or `bruno.services`. Environment **values** never appear in CLI JSON.
- bruno-cli skill + `/bruno` prompt. `bru` itself stays the HTTP runner.

**Worth adding next**

- Nothing urgent. A folder of `workflows/*.yml` is optional if one `goat.workflows.yml` gets large.

When you have the next batch of ideas, we can add them here and promote one slice at a time.

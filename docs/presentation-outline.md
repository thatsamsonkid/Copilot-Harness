# Yard Goat — presentation outline

A slide-by-slide outline for introducing this repo to developers. It is a talk plan, not a deck: each section is one or more slides, with speaker notes and optional talking points.

**Audience:** developers who will use Goat with GitHub Copilot (or another agent) in VS Code, on a multi-repo product stack.

**Goal:** they leave knowing (1) this is a Copilot kit, not the product, (2) what it does in a normal ticket loop, and (3) the two or three commands they will actually run.

**Suggested length:** 20–25 minutes talk + 10 minutes demo, or 15 minutes talk-only. Cut marks are noted per section.

**Working title options**

- Yard Goat: lining up a multi-repo stack for Copilot
- One kit, many repos: a developer workflow with `goat`
- Stop opening the wrong folders: feature workspaces and ticket routing

---

## 1. Title

**Slide:** Yard Goat — a Copilot kit for a multi-repo stack

- Subtitle: the locomotive that lines up the cars so the rest of the railroad can run
- CLI name: `goat`
- One line: product code does **not** live here

**Speaker notes:** The yard-goat metaphor is the whole pitch. We do not haul freight (product features). We move repos, tickets, designs, and API collections into the right order so Copilot and a human can do the work.

---

## 2. The problem (why this exists)

**Slide:** Multi-repo work breaks Copilot (and humans) in predictable ways

- Which repos does this ticket actually touch?
- Which folder should I open so the agent sees the right roots?
- How do I give Copilot a Jira ticket without pasting a token or dumping a raw REST payload?
- How do I start Java + Angular + friends when ports are only known after boot?
- How does the next chat pick up where this one stopped?

**Optional second slide — “without a kit”**

- Open the wrong single repo → agent invents the other half
- Open every clone → agent greps the world
- Paste Jira / Figma / `.env` into chat → secrets and noise
- “Just start everything” → proxy files point at dead ports

**Speaker notes:** Stay at pain, not commands. The next slides are the answers.

---

## 3. Overview — what this repo is

**Slide:** Goat is tooling only. Application remotes live next door.

```text
parent/
  goat/          ← this kit (CLI, catalog, Copilot skills)
  frontend/
  backend/
  mobile/
  infra/
```

Clones can also sit in grouped folders (`frontend/shop-web`, `backend/api`). They are never nested inside this git tree.

**Slide:** Three source-of-truth files (the “manifest layer”)

| File | Answers |
| --- | --- |
| `repositories.yml` | What product remotes exist, tags, clone paths |
| `templates.yml` | Starter remotes for **new** projects (not the current stack) |
| `catalog/stack.yaml` | Feature workspaces + Jira / Figma / Bruno allowlists |

Generated `workspaces/*.code-workspace` files are **local and gitignored**. The catalog is what the team commits.

**Speaker notes:** If someone remembers only one architecture fact: Goat discovers and routes; siblings own product knowledge, standards, and tests.

**Cut for 15 min:** skip the directory tree; keep the three-file table.

---

## 4. What it can do for a developer (feature map)

Use this as a one-slide “menu,” then deep-dive only the rows your audience will use this quarter.

| Need | What Goat gives you |
| --- | --- |
| New laptop / new teammate | `goat init`, `/get-started`, clone script, `doctor` |
| Right folders in VS Code | Feature workspaces: generate, open, create, match |
| Start from a ticket | `goat prepare PROJ-123` → workspace, missing clones, `done_when` |
| Orient in a large stack | `goat context`, `/orient`, Graphify per repo, `goat graph` across repos |
| Run the local apps | `goat start` (plan) + `/start-workspace` (one process at a time) |
| Design in context | `goat figma images` / comments / targeted nodes |
| Hit the APIs | `goat bruno` discovery + `bru run` wrap |
| Stay safe | Keychain tokens, field allowlists, never print secrets |
| Pause / resume / review | `/handoff`, `/review`, `goat status`, `goat branch` |
| New service from a starter | `goat templates` + `goat bootstrap` |

**Speaker notes:** This is the “features” slide they asked for. Do not read the table. Pick three rows and tell a story.

---

## 5. Feature workspaces (deep dive)

This is the concept most people need twice.

**Slide:** A workspace is a *feature slice*, not a department

- Catalog starters: e.g. frontend-heavy, API-heavy, mobile + API
- Your own mix: `/new-workspace` or `goat workspace create`
- Always includes this Goat repo as the **first** root (so Copilot still sees the CLI and instructions)
- Folders are repository **names** (or tags), not clone paths
- Opening the matched workspace is what scopes `context`, `status`, `start`, `branch`

**Slide:** Day-one commands

```bash
goat workspace generate          # local .code-workspace files from the catalog
goat workspace list
goat workspace open frontend     # catalog starter
goat workspace create            # add an id; or /new-workspace in chat
goat workspace current           # what window am I in?
goat workspace match PROJ-123    # usually you just run prepare
```

**Slide:** Why `prepare` exists

1. Fetch a field-filtered Jira issue (no raw vendor dump)
2. Score which workspace that ticket belongs to
3. List required siblings and any missing clones
4. Print the `code` command that opens the right window
5. Attach `done_when`: acceptance criteria + each repo’s verify commands + goat invariants

**Demo beat:** paste `PROJ-123` → show `routing.open_command` and `done_when`.

**Speaker notes:** “Open the workspace Goat recommends” is the single habit that makes the rest of the kit work. `GOAT_WORKSPACE` on the generated file is how later commands stay on `workspace.repos` instead of every clone on disk.

---

## 6. A day in the ticket loop (the workflow slide)

**Slide:** Typical loop (keep this on screen during the demo)

1. New machine once: `/get-started` or `goat init`
2. Work appears: `/prepare-jira` (draft) **or** paste `PROJ-123` / `goat jira mine`
3. Copilot runs `goat prepare` + `goat status`
4. You open the recommended `.code-workspace`
5. Optional: `/start-workspace` (save the sequence once with `--save`)
6. Plan (Jira Planner) → Implementer when you say go
7. Pause with `/handoff`. Review with `/review` against `done_when`

**Optional slide — Copilot surfaces (do not dump every prompt)**

| You type / run | What happens |
| --- | --- |
| `/get-started` | First-run checklist |
| Jira Planner / `/jira-ticket` | Plan from a key |
| `/prepare-jira` | Draft a ticket from notes (you paste into Jira) |
| `/new-workspace` | Compact picker → catalog id |
| `/orient` | Vague prompt → scoped map |
| `/start-workspace` | Sequential local start |
| `/figma-frame` | Rendered frames in Simple Browser |
| `/bruno` | Collections / workflows / `bru run` |
| `/handoff` | Session note for the next chat |
| `/review` | Diff vs `done_when` |
| `/bootstrap-project` | New repo from `templates.yml` |

Agents in the kit: **Jira Planner**, **Workspace Creator**, **Implementer**, **Reviewer**.

**Cut for 15 min:** skip the prompt table; keep the seven-step loop.

---

## 7. Local stack start

**Slide:** `goat start` is a plan, not docker-compose

- Inspects the **open workspace** siblings
- Prints kind, command, port hint, Angular proxy files, start order
- Does **not** launch processes
- `/start-workspace` starts **one app at a time**, one VS Code terminal per app
- Backends first → read the live port → rewrite frontend proxies → then UIs
- Apps with `launch.json` env/args: `goat start run --repo <name>` (secrets stay in-process) or VS Code Run Without Debugging
- Pin a good sequence: `goat start --workspace <id> --save` → `workspaces/<id>.start.yml`

**Speaker notes:** A single “start everything” command fails for the reason the stack is messy. This is orchestration with eyes open.

---

## 8. Orientation and architecture (optional deep dive)

Split if the audience is senior / platform; skip if the room is “how do I take a ticket.”

**Slide:** Two maps, different jobs

| Map | Scale | Command |
| --- | --- | --- |
| Graphify | Inside one sibling | `goat context` → `GRAPH_REPORT.md` |
| Workspace graph | How siblings relate (APIs, events, ADRs) | `goat graph build` / `explain` / `neighbors` / `path` |

- Product knowledge stays in the sibling: `docs/features/`, ADRs
- Goat only **discovers** those files (`context` → `knowledge`)
- Inferred edges carry evidence; `REJECTED` means a human already said no

**Speaker notes:** Do not treat Graphify as the workspace graph. Ask the graph *where*, then open that sibling.

---

## 9. Integrations without MCP

**Slide:** Jira, Figma, and Bruno go through `goat`, not chat paste and not MCP

- **Jira:** `prepare`, `jira get/search/mine`, login to OS keychain. CLI cannot create the issue.
- **Figma:** `figma images` (visual source of truth in Simple Browser), optional comments, `nodes` only on a tiny frame.
- **Bruno:** discover collections/envs/workflows; `bru run` still executes HTTP. Env **values** never appear in CLI JSON.

**Slide:** Why the allowlists matter

- `catalog/stack.yaml` clips vendor payloads (`jira.fields`, `figma.fields`, Bruno projector)
- Copilot gets what it needs to plan, not a 40 KB REST object
- Tokens never enter chat; `.env` is a fallback, keychain is preferred

**Speaker notes:** If someone asks “why not Atlassian MCP?” — this kit is CLI-shaped on purpose: one projector, no token in the agent context, same commands for humans and Copilot.

---

## 10. Bootstrap and new projects (short)

**Slide:** Cloning the current stack vs starting a new repo

- Current stack: `repositories.yml` + `./scripts/clone-repos.sh` / `goat clone --tag ui`
- New repo: `goat templates` → `goat bootstrap --template <name> --name <folder>`
- Bootstrap renames `origin` to `template` so you do not push back to the starter
- Optional `--register` appends to `repositories.yml` (ask first)

---

## 11. Guardrails worth saying out loud

**Slide:** A short list of invariants (builds trust)

- Jira key in each sibling branch (`goat branch PROJ-123`)
- One pull request per sibling — no mega-PR
- Never commit `.env` or print secrets
- `done_when` is the stop condition
- Do not hand-edit generated paths (`tooling.generated`, generated `.code-workspace` files)
- Do not nest product clones inside this Goat repo
- Do not copy product architecture or style guides into Goat — they will rot

---

## 12. Live demo script (10 minutes)

Keep a real ticket and a catalog workspace ready. Narrate; do not debug live.

1. **Health:** `goat doctor` (or `goat init --format text`) — catalog, clones, Jira present/absent.
2. **Workspace:** `goat workspace list` → `goat workspace open <id>` (or show `workspace current` if already open).
3. **Ticket:** `goat prepare PROJ-123 --format markdown` — point at routing, missing repos, `done_when`.
4. **Status:** `goat status` — dirty/ahead, Graphify stale, “you opened a single folder” if relevant.
5. **Start plan:** `goat start --format markdown` — order, ports, `run_via`.
6. **Optional one extra:** Figma frame URL → `goat figma images`, **or** `goat bruno collections`, **or** `goat graph explain A B`.

If Copilot Chat is available: paste the Jira key and let Jira Planner run `prepare`, then show the recommended `code` command.

---

## 13. What we are not building (scope slide)

Useful after Q&A starts wandering.

- Not a product monorepo and not a wiki
- Not a Jira/Figma MCP server
- Not a replacement for `bru`, Graphify, or each repo’s test runner
- Not “start the whole company in one process”
- Knowledge and ADRs stay next to the code that changed

---

## 14. Close — what to do Monday

**Slide:** Three actions

1. Clone this kit next to your product remotes; run setup (`./scripts/setup.sh` or `.\scripts\setup.ps1`)
2. Fill `repositories.yml`, run `goat workspace generate`, open a catalog workspace
3. In Copilot Chat: `/get-started`, then take one real ticket through `prepare`

**Leave-behind**

- Human cheat sheet: `docs/cli.md` (`goat commands`)
- First-run: `/get-started` and `.github/skills/get-started/SKILL.md`
- This outline: `docs/presentation-outline.md`

---

## Alternate agendas

### 15-minute overview (no demo)

1. Title + metaphor
2. Problem
3. Overview (three files)
4. Feature map (one slide)
5. Workspaces + `prepare`
6. Ticket loop
7. Monday actions

### 40-minute team onboarding (with demo)

1–6 as above, then Local start, Integrations, Guardrails, live demo, Q&A.

### Platform / staff-plus variant

Swap the start-stack deep dive for **Workspace graph + Graphify + knowledge convention** (`docs/workspace-graph.md`, `docs/knowledge.md`). Add a slide on extractors and evidence classifications (`DECLARED` / `OBSERVED` / `INFERRED` / `REJECTED`).

### Leadership variant (10 minutes)

Stay on: problem, metaphor, “kit not product,” ticket loop diagram, secret-handling, “one PR per repo.” Skip CLI flags.

---

## Extra slide ideas (pick one if time)

- **Before / after:** screenshot of a single-folder Copilot chat vs a four-root feature workspace.
- **Secrets story:** what Copilot is allowed to see (`env list` keys only) vs what stays in keychain / `start run`.
- **Skills lift:** why VS Code Agents cannot see child-folder `SKILL.md` files and how `goat skills lift` copies them into this repo (local-only, do not commit).
- **Planning for a smaller model:** `/goat-plan` writes a zero-context plan under `plans/` from `templates/plan.md`.
- **Roadmap teaser** from `docs/ideas.md`: `goat pr`, start-status / last-known ports, worktrees, Jira write path — only if you want a “what’s next” slide.
- **Command cheat card** (handout, not a slide): `init`, `prepare`, `workspace open`, `start`, `status`, `handoff write`, `doctor`.

---

## Visual suggestions

- One diagram used three times: ticket → `prepare` → workspace → plan → implement → review.
- Directory tree once; do not repeat it on every architecture slide.
- Prefer a real `prepare` JSON (redacted) over a fake architecture cartoon.
- Dark terminal screenshot of `goat start --format markdown` lands better than a bullet list of flags.

---

## Appendix — command one-liners for backup slides

```bash
uv run goat init
uv run goat doctor
uv run goat workspace generate
uv run goat workspace open frontend
uv run goat prepare PROJ-123
uv run goat context
uv run goat status
uv run goat start --save
uv run goat start run --repo backend
uv run goat jira mine
uv run goat figma images 'https://www.figma.com/design/…'
uv run goat bruno collections
uv run goat graph build
uv run goat handoff write --issue PROJ-123 --note "…"
uv run goat bootstrap --template <name> --name <folder>
```

Run from this Goat repo, or `uv run --project "$GOAT_ROOT" goat …` / the PATH shim from `goat install` after you `cd` into a sibling.

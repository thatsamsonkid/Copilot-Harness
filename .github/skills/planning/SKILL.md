---
name: planning
description: Write an implementation plan into the root plans/ directory using templates/plan.md. Use when the user asks to plan work, write a plan, or prepare a task for another (often smaller) model or agent to execute. Plans must be detailed enough for a low-context executor to follow without asking questions. Fan out Bulk Readers for independent survey groups. Group independent steps into parallel waves so /goat-implement can fan out Code Writers. Never spawn Implementer. Start implementation with /goat-implement (Code Writer + Verifier; survives compaction). A new chat with only the plan file writes the code itself.
argument-hint: PROJ-123
---

# Planning

Plans live in this goat (`plans/`), not in product repos. They are gitignored. A plan is the **single input for a new-chat executor** — often a smaller, cheaper model with no access to this conversation. That later chat writes the code itself and must not spawn Implementer, Code Writer, or Verifier. If the same chat that wrote the plan is asked to implement, tell them to run `/goat-implement` (it reloads Code Writer + Verifier after compaction) — that chat becomes Implementer and must not spawn Implementer. If either executor would need to guess, the plan is not done.

## Where plans live

| What | Rule |
| --- | --- |
| Directory | `plans/` at the goat root. Never inside a sibling clone. |
| Filename | `plans/<YYYY-MM-DD>-<issue-key-or-slug>.plan.md` (lowercase slug, e.g. `plans/2026-09-01-shop-1234.plan.md`) |
| Template | Start from `templates/plan.md`. Keep every section; write "None" rather than deleting one. |
| Git | Gitignored by default. Do not commit a plan unless the user asks. |
| One plan per task | Revise the existing file as scope changes. Do not fork `-v2` copies. |

## Gather context before writing

1. If a Jira key is in play, run `uv run goat prepare <KEY> --format json` (jira-cli skill) and plan against `routing.repos`. Copy `done_when` into the plan verbatim. Tickets written from `templates/jira-ticket.md` already have the headings this flow expects.
2. Run `uv run goat context --format json` (workspace-context skill). Read each repo's Graphify `GRAPH_REPORT.md` and `instructions` files before naming file paths or conventions.
3. For survey questions on named product files or symbols, **fan out Bulk Readers**. In the same turn, invoke one `#tool:agent` Bulk Reader per independent group (prefer one group per repo, or disjoint path sets). Each call is stateless — exact question, repo-relative paths, what to skip. Cap a group at a handful of files. Never send the same file to two readers. Skip Bulk Reader for debugging, architectural decisions, or safety-critical analysis — targeted-`Read` those yourself. Record the groups in **Survey groups**.
4. Verify every file path you name actually exists (or mark it explicitly as "new file"). A wrong path derails a small executor completely.
5. Record branch names from `uv run goat branch <KEY>` (or the `routing.suggested_branch`).

## The audience rule

Write for an executor that has: the plan file, the repo checkouts, and nothing else. It has not read the ticket, this chat, or your head.

- Restate the goal and all requirements in the plan itself. Never write "see ticket" or "as discussed".
- Make every decision **in the plan**. No "choose an appropriate name", no "update as needed", no "etc.", no unresolved either/or. If you cannot decide, that is an open question for the user — resolve it before the plan ships.
- Define repo-specific terms and name the exact conventions to follow (with the instruction file that mandates them).
- State what is **out of scope** explicitly, so the executor does not wander.

## The file map

Every plan must contain a **File map**: one table listing every file the executor will create, edit, or delete — the complete set, across all repos. The executor should never have to search the codebase to find where a change goes; the planning model does that research once, here.

| Column | Content |
| --- | --- |
| Repo | Sibling repo name from the workspace |
| File | Exact path from that repo's root. Mark new files `(new)` |
| Action | create / edit / delete |
| Change | One line: what changes in this file and why |
| Steps | Which step numbers touch it |

Rules for the file map:

- **Repo-relative paths only.** Never absolute paths, and never paths relative to the goat or the workspace root — sibling clones sit at different disk locations on every machine (flat siblings or grouped under `parent_dir`). The Repo column plus a path from that repo's root is unambiguous in any multi-root window; an absolute path is wrong everywhere except the planner's machine.
- Verified paths only. Open each file while planning; do not name a path from memory.
- **Anchor by symbol, not line number.** Line numbers drift; point at function/class/config-key names or a short unique code fragment the executor can search for.
- When a repo already has a file that follows the target pattern, name it as **"model after"** — imitating a verified example beats prose instructions for a small executor.
- If a file might plausibly be touched but must not be, put it in **Out of scope** by path.

## Step depth requirements

Every step in the plan must contain:

- **Repo and working directory** the step runs in.
- **Exact file paths** to create or edit (drawn from the file map), and the exact symbols (function, class, config key) to touch.
- **What to change**, concretely: new signatures, field names, route paths, and short code or config snippets whenever the change is non-obvious. For edits, quote the current fragment and the desired fragment so the executor can match by content. Prose like "add validation" is not a step.
- **Exact commands** to run, copy-pasteable, with the cwd they must run from.
- **Expected result**: what output, diff, or behavior proves the step worked.
- **Verify**: the check to run before moving on (test command, lint, curl via a `.bru` request — never raw curl to a product API).
- **Wave** number and **Depends on** (step numbers, or `none`) so `/goat-implement` can fan out Code Writers.

Number steps globally and give each a checkbox (`- [ ]`) so the executor can track progress in the file. Prefer many small verifiable steps over one large step — independent file sets should be separate steps so they can share a wave. If a step fails verification, the executor should stop and report, not improvise — say so in the plan.

## Parallel waves

A **wave** is a set of steps that can run at the same time. `/goat-implement` issues one **Code Writer** per step in a wave, in the same turn, then verifies the wave before starting the next. Sequential Code Writer → Verifier per step is the fallback, not the default. Fill in **Parallel waves** on every plan (keep the section; do not delete it).

Split work so independent file sets become separate numbered steps. Then group those steps into the fewest waves that stay safe:

| Put in the same wave | Put in a later wave |
| --- | --- |
| Disjoint file-map rows (no shared create/edit/delete) | The same file appears in two steps |
| No step consumes a type, route, event, schema, or function another step in the wave produces | Consumer of a new or changed contract |
| Each step's Verify can pass without the other steps' new files existing | Verify needs another step's output |
| Different repos, or the same repo with no overlapping symbols | Shared-contract producer (API, event, schema, generated client) is still unfinished |

Rules:

- Order **waves** by dependency (wave 1, then 2, …). Steps keep their global numbers.
- Two writers must never receive the same file. Same-file work stays one step, or sequential steps in later waves.
- Shared-contract producers finish before consumer waves.
- If independence is uncertain, use a later wave. Do not invent parallelism.
- Write `None — all steps sequential` only when every step depends on the previous one. That is a last resort, not the starting shape.
- A one-step wave is fine when the next change truly needs that output.

The **Parallel waves** table lists wave number, step numbers, and why those steps are independent (or why a single step must wait). Each step repeats its `Wave` and `Depends on` so a compacted Implementer does not have to infer the graph.

## Finish the plan

- Fill in **Survey groups**: independent Bulk Reader groups `/goat-implement` can fan out before a wave (repo, paths/symbols, question, wave). Write `None` when the steps already contain every fragment the writer needs and no survey is required.
- Fill in **Preconditions**: what must already be true before step 1 (services running, dependencies installed, workspace open), each with the command that checks it. An executor that starts in a broken environment will misattribute every failure to its own changes.
- End with **Verification** (the full test/lint commands per repo, from that repo's `tooling.suggested_verify`) and **Done when** (the stop condition; from Jira `done_when` when present).
- Include risks and a rollback note when the change touches shared contracts (APIs, events, schemas).
- Tell the user the plan's relative path. Planning and executing are separate: do not start implementing the plan in the same breath unless the user asks.
- Tell them to start implementation with **`/goat-implement`** (implementing skill). That command survives chat compaction: the chat becomes Implementer, fans out **Code Writer** per independent step in a wave, and invokes **Verifier** after each wave (plus the **Verification** section). A new chat with only the plan file and no `/goat-implement` writes the files itself. Never spawn Implementer. Do not start implementing in this planning turn.

## Who executes this plan

Never spawn Implementer. The Implementer *role* is something the primary chat takes on.

| Who is implementing | What they do |
| --- | --- |
| **`/goat-implement`** (preferred; works after compaction) | You become Implementer. Load the implementing skill. Fan out one **Code Writer** per independent step in a **Parallel waves** row, then **Verifier** for that wave plus the **Verification** section. Code Writer pins Copilot Auto (`Auto (copilot)`) — do not override the model. You still run `goat branch` and write feature notes. Do not spawn Implementer. |
| **Same chat that wrote this plan** (expensive planner continues without the slash command) | Same as `/goat-implement`. After compact, tell them to run `/goat-implement` so the protocol is reloaded — a bare "implement it" is not enough. |
| **New chat handed only the `plans/` file** (often a smaller model; no `/goat-implement`) | You are the executor. Follow the file map and **Parallel waves** for order. Write product files yourself. Do not spawn Implementer, Code Writer, or Verifier. |
| **VS Code Agents dropdown** | User picks Implementer as the primary chat — same as `/goat-implement`. |

- Subagents must not spawn other subagents. If you were yourself started as a subagent, write the files yourself — do not nest Code Writer or Verifier.
- Do not wait for a handoff button unless the user is in VS Code Agents and clicks **Implement plan**.

## Hard rules

- No secrets: never write `.env` values, tokens, or credentials into a plan.
- Plans stay in the goat `plans/` directory. Do not write plans into sibling repos; product knowledge (feature notes, ADRs) still belongs in the sibling's `docs/features`.
- Do not name repos outside the matched workspace (`workspace.repos` / `routing.repos`).
- One pull request per sibling repo; the plan must say which branch and PR each step belongs to.
- Do not invent file paths, commands, or conventions you did not verify against the actual repos.

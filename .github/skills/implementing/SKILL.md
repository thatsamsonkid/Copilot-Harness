---
name: implementing
description: Start implementing an agreed plans/ file as Implementer. Use when the user runs /goat-implement, asks to execute a plan, or continues after /goat-plan — especially after chat compaction. Never spawn Implementer. Become Implementer. Fan out Bulk Readers per Survey groups, then Code Writers for independent steps in a Parallel waves row, then Verifier for that wave. One bounded repair per step on first verify fail; second fail is yours to investigate. You still run goat branch and write feature notes.
argument-hint: PROJ-123
---

# Implementing

`/goat-implement` is the compaction-proof start. Conversation compaction drops the planning-turn reminder to use **Code Writer** and **Verifier**. This skill re-injects that protocol. Load it even if an earlier turn in this chat wrote the plan.

Plans live in this goat (`plans/`), not in product repos. They are gitignored.

Never spawn Implementer. The Implementer *role* is something the primary chat takes on.

## Why this command exists

A bare "implement it" after compact often writes product files in the parent chat and skips verify. `/goat-implement` forbids that when you are the primary chat.

| Must do | Must not |
| --- | --- |
| Become Implementer in this chat | Spawn the Implementer agent |
| Invoke **Code Writer** (`#tool:agent`) for every product-file write — one call per independent step in a wave, issued together | Edit product files yourself with `#tool:edit` |
| Invoke **Verifier** (`#tool:agent`) after each wave and for the final **Verification** section. You own the retry counter | Run those verify commands only in the parent and call the work done. Do not let Verifier retry or patch |
| Run `goat branch`, write feature notes / ADRs yourself | Treat Code Writer or Verifier as a second Implementer |
| Stop when `done_when` holds | Pick Orchestrator from the agents dropdown |

## Who you are

| How this chat started | What you do |
| --- | --- |
| **`/goat-implement`** (this skill) | You become Implementer. Fan out Code Writers per wave. Verifier after each wave (one bounded repair per step, then you investigate). You: `goat branch`, feature notes, ADRs. Compaction does not change this. |
| **Same chat that wrote the plan** (`/goat-plan`) and the user asked to continue | Same as `/goat-implement`. Prefer they run `/goat-implement` after compact so this file is reloaded. |
| **VS Code Agents dropdown** — user picked Implementer | Same as `/goat-implement`. |
| **New chat handed only the `plans/` file** (no `/goat-implement`) | You are the executor. Follow **Parallel waves** for order. Write the listed files yourself. Do not invoke Implementer, Code Writer, or Verifier. |
| **You were started as a subagent** | Write files yourself. Run verify yourself. Do not nest Code Writer, Verifier, Bulk Reader, or Implementer. |

Subagents must not spawn other subagents. If `#tool:agent` cannot nest, fall back to `#tool:edit` and parent-run verify — say that you fell back.

## Find the plan

1. If the user named a `plans/…plan.md` path, use that file.
2. Else if they named an issue key, use `plans/<YYYY-MM-DD>-<key>.plan.md` (lowercase key).
3. Else list `plans/*.plan.md` and take the only match, or the newest match for the open ticket, or ask which file.
4. If there is no plan file, stop. Tell them to run `/goat-plan` first. Do not invent steps from a compacted chat.

Read the plan's **File map**, **Survey groups**, **Parallel waves**, **Steps**, **Verification**, and **Done when**. Those are the spec. Do not search the codebase for where a change goes unless a named path is missing. If **Parallel waves** is missing (older plan), treat each step as its own wave and stay sequential. If **Survey groups** is `None` or missing, group that wave's `Model after` / reference paths by repo yourself.

## Workflow

1. Run `uv run goat status --format json` from the goat folder. Stay inside the plan's repos and `workspace.repos` from `uv run goat context --format json`. If a Jira key is in play, run `uv run goat prepare <KEY> --format json` and treat `done_when` as the stop condition.
2. Before the first product edit, run `uv run goat branch <KEY>` so each touched sibling is on the Jira-key branch. Refuse to create the branch when the tree is dirty.
3. Follow each sibling's `instructions` / `tooling` from that JSON. Prefer `tooling.suggested_verify` over inventing npm/make targets.
4. Walk **Parallel waves** in order (wave 1, then 2, …). Sequential Code Writer → Verifier per step is only for a one-step wave or an older plan with no waves table.
   - Targeted-`Read` (`limit`/`offset`) every section that wave will change. Do not edit from Bulk Reader line numbers.
   - When you are the primary chat, **fan out Bulk Readers** for that wave's **Survey groups** (or, if `None`/missing, the wave's `Model after` / reference paths grouped by repo). In the same turn, invoke **Bulk Reader** with `#tool:agent` once per group. Each call is stateless — exact question, repo-relative paths, what to skip. Cap a group at a handful of files. Never send the same file to two readers. Do not send debugging, architectural decisions, or safety-critical analysis to Bulk Reader. Wait for every reader in the wave to return, then targeted-read the slices you will change.
   - **Fan out Code Writers.** In the same turn, invoke **Code Writer** with `#tool:agent` once per step in the wave. Agent name is case-sensitive: `Code Writer`. Its profile pins Copilot Auto (`Auto (copilot)`) — do not override the model. Each call is stateless — put that step's spec, target paths, and reference paths in that one prompt. Ask it to match existing patterns and to output only the code. Write only the files in that step's file-map rows. Never send two writers the same file.
   - If a wave lists overlapping files (planner error), serialize those steps instead of fanning out. Do not invent extra waves that skip a listed dependency.
   - A one-step wave is a single Code Writer call.
   - Use `#tool:edit` yourself for goat catalog, feature notes, and ADRs. Never send those to Code Writer.
   - Wait for every writer in the wave to return. Then invoke **Verifier** with `#tool:agent`. Agent name is case-sensitive: `Verifier`. Pass each step's **Verify** command, cwd, and expected result. Fan out Verifiers when commands use different repos or cwds; if they share one command, invoke Verifier once. Let every Verifier in the wave finish before you act on a fail. Follow **Bounded verify** — do not start the next wave until every step in this wave is `pass` or you have escalated a second fail.
5. After all waves, invoke **Verifier** again with the plan **Verification** section and each touched repo's `tooling.suggested_verify`. Same **Bounded verify** rule: one repair only when the failure names a file-map step; otherwise investigate on the first fail. Do not mark the plan done until Verifier reports pass and `done_when` holds.
6. If the change adds user-visible or non-obvious behavior, add or update `docs/features/<slug>.md` in that sibling using `templates/feature-note.md`. Write an ADR in the sibling for a real design choice. Do not store product knowledge in the goat.
7. Say which sibling repo each commit belongs to. One pull request per sibling. Do not squash unrelated repos together.

## Bounded verify

Verifier is a reporter. It does not retry, patch, or spawn Code Writer. You own the retry counter (one repair per step).

A Verify is delegable only when it is a copy-pasteable command, a cwd, and an expected result. If the plan's Verify is prose ("make sure it works"), treat it as `missing`.

On a Verifier result:

| Result | What you do |
| --- | --- |
| `pass` | Continue. |
| `missing`, or Verify was not a real command | Investigate now. Do not auto-retry. |
| `fail` on a shared contract (API, event, schema, generated client) or safety-critical code (auth, payments, concurrency, data loss) | Investigate now. Do not auto-retry. |
| `fail` whose output is infrastructure (timeout, cache lock, network) | Re-invoke **Verifier** once with the same command (no Code Writer). If that re-run fails, investigate — do not loop flakes. |
| Any other first `fail` | **One bounded repair** for that step only: invoke **Code Writer** with the original step spec plus the Verifier error, then **Verifier** again for that step. Do not start the next wave. Do not repair other steps in the wave unless they also failed. |
| Second `fail` on that step (after the repair) | **You investigate.** Targeted-`Read` the failing slice. Do not send a third Code Writer. Do not invoke Bulk Reader. Do not invoke Verifier again on that step. Stop the wave and report. |

A Code Writer that fails to write (illegal path, refused files) is not a verify fail — stop and report; do not burn the repair on it.

Do not paste Code Writer output back unless the user asked. Do not paste Verifier logs unless a check failed or the user asked.

## Hard rules

- Compaction is not a new-chat executor path. `/goat-implement` keeps you on the Code Writer + Verifier path.
- Do not clone repositories into the goat folder.
- Do not write `.env`, tokens, or secrets. Do not hand-edit `tooling.generated` paths.
- Do not name repos outside the matched workspace (`workspace.repos` / `routing.repos`) unless a blocker forces a documented detour.
- If `graphify.stale` is true after edits, remind the user to refresh that repo's graph; do not auto-extract a monorepo.
- `/review` (Reviewer) is a later human review of the diff. It does not replace Verifier during implementation.

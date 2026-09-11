---
name: implementing
description: Start implementing an agreed plans/ file as Implementer. Use when the user runs /goat-implement, asks to execute a plan, or continues after /goat-plan — especially after chat compaction. Never spawn Implementer. Become Implementer. Invoke Code Writer for product files and Verifier for verify checks. You still run goat branch and write feature notes.
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
| Invoke **Code Writer** (`#tool:agent`) for every product-file write | Edit product files yourself with `#tool:edit` |
| Invoke **Verifier** (`#tool:agent`) for every plan Verify check and the final **Verification** section | Run those verify commands only in the parent and call the work done |
| Run `goat branch`, write feature notes / ADRs yourself | Treat Code Writer or Verifier as a second Implementer |
| Stop when `done_when` holds | Pick Orchestrator from the agents dropdown |

## Who you are

| How this chat started | What you do |
| --- | --- |
| **`/goat-implement`** (this skill) | You become Implementer. Code Writer for product files. Verifier for verify. You: `goat branch`, feature notes, ADRs. Compaction does not change this. |
| **Same chat that wrote the plan** (`/goat-plan`) and the user asked to continue | Same as `/goat-implement`. Prefer they run `/goat-implement` after compact so this file is reloaded. |
| **VS Code Agents dropdown** — user picked Implementer | Same as `/goat-implement`. |
| **New chat handed only the `plans/` file** (no `/goat-implement`) | You are the executor. Write the listed files yourself. Do not invoke Implementer, Code Writer, or Verifier. |
| **You were started as a subagent** | Write files yourself. Run verify yourself. Do not nest Code Writer, Verifier, Bulk Reader, or Implementer. |

Subagents must not spawn other subagents. If `#tool:agent` cannot nest, fall back to `#tool:edit` and parent-run verify — say that you fell back.

## Find the plan

1. If the user named a `plans/…plan.md` path, use that file.
2. Else if they named an issue key, use `plans/<YYYY-MM-DD>-<key>.plan.md` (lowercase key).
3. Else list `plans/*.plan.md` and take the only match, or the newest match for the open ticket, or ask which file.
4. If there is no plan file, stop. Tell them to run `/goat-plan` first. Do not invent steps from a compacted chat.

Read the plan's **File map**, **Steps**, **Verification**, and **Done when**. Those are the spec. Do not search the codebase for where a change goes unless a named path is missing.

## Workflow

1. Run `uv run goat status --format json` from the goat folder. Stay inside the plan's repos and `workspace.repos` from `uv run goat context --format json`. If a Jira key is in play, run `uv run goat prepare <KEY> --format json` and treat `done_when` as the stop condition.
2. Before the first product edit, run `uv run goat branch <KEY>` so each touched sibling is on the Jira-key branch. Refuse to create the branch when the tree is dirty.
3. Follow each sibling's `instructions` / `tooling` from that JSON. Prefer `tooling.suggested_verify` over inventing npm/make targets.
4. For each plan step, in order:
   - Targeted-`Read` (`limit`/`offset`) every section you will change. Do not edit from Bulk Reader line numbers.
   - When you are the primary chat, invoke **Bulk Reader** only for a **survey** of named reference files. Do not send debugging, architectural decisions, or safety-critical analysis to Bulk Reader.
   - Invoke **Code Writer** with `#tool:agent`. Agent name is case-sensitive: `Code Writer`. Its profile pins Claude Haiku 4.5 — do not override the model. Each call is stateless — put the spec, target paths, and reference paths in that one prompt. Ask it to match existing patterns and to output only the code. Write only the files in that step's file-map rows.
   - Use `#tool:edit` yourself for goat catalog, feature notes, and ADRs. Never send those to Code Writer.
   - Invoke **Verifier** with `#tool:agent`. Agent name is case-sensitive: `Verifier`. Pass the step's **Verify** command, cwd, and expected result. If Verifier reports fail, stop and report — do not improvise the next step.
5. After all steps, invoke **Verifier** again with the plan **Verification** section and each touched repo's `tooling.suggested_verify`. Do not mark the plan done until Verifier reports pass and `done_when` holds.
6. If the change adds user-visible or non-obvious behavior, add or update `docs/features/<slug>.md` in that sibling using `templates/feature-note.md`. Write an ADR in the sibling for a real design choice. Do not store product knowledge in the goat.
7. Say which sibling repo each commit belongs to. One pull request per sibling. Do not squash unrelated repos together.

Do not paste Code Writer output back unless the user asked. Do not paste Verifier logs unless a check failed or the user asked.

## Hard rules

- Compaction is not a new-chat executor path. `/goat-implement` keeps you on the Code Writer + Verifier path.
- Do not clone repositories into the goat folder.
- Do not write `.env`, tokens, or secrets. Do not hand-edit `tooling.generated` paths.
- Do not name repos outside the matched workspace (`workspace.repos` / `routing.repos`) unless a blocker forces a documented detour.
- If `graphify.stale` is true after edits, remind the user to refresh that repo's graph; do not auto-extract a monorepo.
- `/review` (Reviewer) is a later human review of the diff. It does not replace Verifier during implementation.

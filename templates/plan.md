# Plan: <task name>

- Issue: <PROJ-123 or "none">
- Workspace: <catalog workspace id>
- Repos / branches: <repo> → `<branch>` (one line per repo, one PR per repo)
- Status: draft | approved | in progress | done
- Last updated: YYYY-MM-DD

## Objective

What must be true when this plan is complete, in two or three sentences. Restate the requirements here — the executor has not read the ticket or the chat.

## Context for the executor

Never spawn Implementer. Which path you are on:

- **`/goat-implement`** (preferred after compaction): you become Implementer. Fan out one Code Writer per independent step in a Parallel waves row, then Verifier for that wave. Do not spawn Implementer.
- **New chat** (this file is your only brief; no `/goat-implement`): you are the executor. Follow Parallel waves for order. Write the listed files yourself. Do not invoke Implementer, Code Writer, or Verifier. Subagents must not spawn other subagents.
- **Same chat that wrote this plan** (no slash command): same as `/goat-implement`. After compact, run `/goat-implement` so the protocol is reloaded.

Everything a model with zero prior context needs before step 1: what the feature/bug is, how the involved repos relate, which instruction files to read first (exact paths), and any terms of art defined in one line each.

## Out of scope

Explicit non-goals. Anything listed here must not be touched, even if it looks related. List by file path any files an executor might plausibly edit but must not.

## Preconditions

What must be true before step 1, each with the command that checks it (services running, dependencies installed, feature workspace open). Write "None" if there are none.

## File map

Every file this plan creates, edits, or deletes — the complete set. Paths are relative to each repo's root (the Repo column disambiguates); never absolute, never relative to the goat or workspace root. Verified against the actual repos; mark new files `(new)`. The executor must never have to search for where a change goes.

| Repo | File | Action | Change | Steps |
| --- | --- | --- | --- | --- |
| <repo> | `src/…` | edit | <one line: what and why> | 1, 3 |
| <repo> | `src/… (new)` | create | <one line> | 2 |

## Survey groups

Independent Bulk Reader groups so `/goat-implement` (and this planning turn) can fan out one reader per group in the same turn. Prefer one group per repo, or disjoint path sets. Cap a group at a handful of files. Never list the same file in two groups. Write `None` when no survey is required.

| Group | Repo | Paths / symbols | Question | Wave |
| --- | --- | --- | --- | --- |
| <id> | <repo> | `src/…` | <what to locate> | 1 |
| <id> | <repo> | `src/…` | <model-after pattern> | 1 |

## Parallel waves

Group independent steps so `/goat-implement` can fan out one Code Writer per step in a wave, then verify the wave before the next. A new-chat executor still follows waves for order but writes files itself. Same file, or a consumer of a new type/route/event/schema, belongs in a later wave. Write `None — all steps sequential` only when every step depends on the previous one.

| Wave | Steps | Why independent |
| --- | --- | --- |
| 1 | 1, 2 | <disjoint files / different repos; no shared contract> |
| 2 | 3 | <consumes the output of steps 1–2> |
| 3 | 4, 5 | <same repo, disjoint files; both need step 3> |

## Steps

Number every step. Each step must name the repo and cwd, wave, dependencies, exact file paths and symbols, the concrete change (snippets when non-obvious), exact commands, expected result, and a verify check. If a verify check fails, stop and report — do not improvise. Do not start the next wave until this wave's verify checks pass.

- [ ] **Step 1 — <short name>**
  - Repo / cwd:
  - Wave: 1
  - Depends on: none
  - Files: (from the file map)
  - Locate: (symbol name or a short unique fragment to search for — never a line number)
  - Model after: (an existing file in the repo that already follows the target pattern, or "none")
  - Change: (concrete: signatures, field names, snippets; for edits quote current → desired fragments)
  - Commands:
  - Expected result:
  - Verify:

- [ ] **Step 2 — <short name>**
  - …

## Verification

The full per-repo verify commands (from that repo's `tooling.suggested_verify`) to run after all steps, and what passing looks like.

## Done when

The stop condition, copied from Jira `done_when` when there is a ticket. Do not mark the plan done until every item holds.

## Risks and rollback

Only for changes to shared contracts (APIs, events, schemas): what could break downstream and how to back out.

Keep this file in the **goat** (`plans/<YYYY-MM-DD>-<key-or-slug>.plan.md`). It is gitignored; do not commit it unless asked. Never put secrets or `.env` values in a plan.

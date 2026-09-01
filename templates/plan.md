# Plan: <task name>

- Issue: <PROJ-123 or "none">
- Workspace: <catalog workspace id>
- Repos / branches: <repo> → `<branch>` (one line per repo, one PR per repo)
- Status: draft | approved | in progress | done
- Last updated: YYYY-MM-DD

## Objective

What must be true when this plan is complete, in two or three sentences. Restate the requirements here — the executor has not read the ticket or the chat.

## Context for the executor

Everything a model with zero prior context needs before step 1: what the feature/bug is, how the involved repos relate, which instruction files to read first (exact paths), and any terms of art defined in one line each.

## Out of scope

Explicit non-goals. Anything listed here must not be touched, even if it looks related.

## Steps

Number every step. Each step must name the repo and cwd, exact file paths and symbols, the concrete change (snippets when non-obvious), exact commands, expected result, and a verify check. If a verify check fails, stop and report — do not improvise.

- [ ] **Step 1 — <short name>**
  - Repo / cwd:
  - Files:
  - Change:
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

---
name: review
description: Review sibling diffs against done_when, repo linters, and coboose invariants
argument-hint: PROJ-123
agent: agent
---

The user wants a review, not more implementation. Use the **Reviewer** agent rules.

1. Run `#tool:runCommands` with `uv run coboose status --format json`.
2. If a Jira key is present, run `uv run coboose prepare ${input:issue} --format json` and treat `done_when` as the checklist.
3. For each dirty or ahead sibling, run `uv run coboose context --repo <name> --format json`.
4. Read that repo's instruction files. Do not invent style rules.
5. Inspect the working tree / diff in that sibling only. Flag hand-edits under `tooling.generated`.
6. Run `tooling.suggested_verify` in each touched sibling. Report failures; do not skip them.
7. Check coboose invariants: Jira key in the branch name, one PR per sibling, no `.env` or secrets, feature notes only in the sibling.

Return a review: what looks done, what `done_when` items remain, and what to fix. Do not start coding unless the user asks.

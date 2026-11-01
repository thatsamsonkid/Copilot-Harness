---
name: swarm
description: Fan out read-only coverage across disjoint slices and return one report.
argument-hint: coverage question or slices
disable-model-invocation: true
---

# Swarm

Cover a question with read-only slices and return one report. Do not edit files. Do not apply fixes.

Do not read `.env`, print a token, or ask anyone to paste a token. Do not clone a repo into this goat folder. Do not invent a command or flag. The catalog is `docs/cli.md`.

## Who reads

If you were started as a subagent other than Orchestrator, do every read yourself and do not invoke Bulk Reader. Only the hidden Orchestrator may delegate while it is a subagent. Bulk Reader never delegates.

Workers are Bulk Reader only.

Never invoke Code Writer, Verifier, or any writer.

## Paths

When a slice needs a sibling repo, do not `cd` into that clone first. Stay in the Goat folder. Run `uv run goat context --format json` and take `<repo-path>` from that repo's `repos[].path`. That field is the absolute clone path. Stay inside `workspace.repos`. Do not use `relpath`. If the user names a repo, run `uv run goat context --repo <name> --format json`. If `repos[].cloned` is false, say that sibling is not on disk. Do not clone it.

Every git command is `git -C <repo-path>`. Bulk Reader has no shell. Run git in this chat. Do not ask Bulk Reader to run git.

## Frame

State a done predicate, and the report this run returns, before any call.

Choose one shape. Split the work into disjoint (non-overlapping) slices, or run a read-only race on one shared brief. A race declares its ranking rule before any call. Use first `PASS`, or rank every arm. When rank-every-arm ties, ties go to the arm with more distinct `path:line` evidence; if still tied, report both. One brief per slice. A race copies that same brief to every arm and includes the ranking rule. If slices overlap, re-split before fanning out.

At most 4 slices, matching `/how` (`.github/skills/how/SKILL.md`), which uses up to 4 parallel Bulk Reader calls. Each slice is a handful of files. If the question is larger, merge slices until 4 remain and name what did not fit.

Each brief stands alone. Include the done predicate, the exact slice or race arm, the paths or symbols, and that the reply needs `path:line` evidence.

## Fan out

Invoke **Bulk Reader** (`.github/agents/bulk-reader.agent.md`) once per slice, at most 4 calls, with `#tool:agent`, and make every call in the same turn. The name is case-sensitive. Its profile pins Copilot Auto (`Auto (copilot)`). Do not override the model. Each call is stateless. Pass that one brief only.

Do not promise speed. VS Code docs only say subagents can run in parallel when the harness supports concurrent subagents. Promise coverage, not speed.

Ask for locations only, as `path:line` bullets. Stay inside `workspace.repos`. Do not ask Bulk Reader to edit, to run git, or to explain architecture.

## Aggregate

This chat sets each slice to `PASS`, `ISSUES`, or `BLOCKED` from its `path:line` evidence. `PASS` means the evidence meets the done predicate. `ISSUES` means the evidence shows it does not. `BLOCKED` means the slice could not be read. A slice with no evidence is re-invoked once, then recorded as a gap. A gap does not count as a pass.

Every required slice needs a result. For a race, apply the ranking rule declared up front. Do not paste raw worker dumps.

## Report

Return one consolidated table with one row per slice:

| Slice | Result | Evidence | Gaps |
| --- | --- | --- | --- |
| <name> | `PASS`, `ISSUES`, or `BLOCKED` | `path:line` | gap, or none |

Under the table, one line per issue, each gap, and the ranking rule when the shape was a race.

Code-change judgment stays in `.github/instructions/engineering-principles.instructions.md`. This skill reports.

Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md

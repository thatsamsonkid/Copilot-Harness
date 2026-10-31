---
name: tdd
description: Write a failing regression test for a bug, then the smallest fix that makes that test pass.
argument-hint: bug or behavior to lock
disable-model-invocation: true
---

# TDD

When fixing a bug with a clear, cheap test path, make the broken behavior executable before changing production code. The goal is a focused regression test that fails before the fix and passes after it.

Do not force a test when it would be impractical. If the available test would require broad harness setup, brittle mocks, slow end-to-end infrastructure, production-only state, vague reproduction steps, or large unrelated fixture churn, skip adding a new test and use the closest useful verification instead.

Do this as one sequence in this chat. Behavior-vs-implementation judgment is in `.github/instructions/engineering-principles.instructions.md`. Do not read `.env`, print a token, or ask anyone to paste a token. Do not clone a repo into this goat folder.

## Who writes

When this chat is the primary Implementer (`/goat-implement`, `.github/skills/implementing/SKILL.md`, or the user picked Implementer), product-file edits go through **Code Writer** (`.github/agents/code-writer.agent.md`) with `#tool:agent`. That is the new test and the production fix. Do not edit those files yourself. The name is case-sensitive. Its profile pins Copilot Auto (`Auto (copilot)`) — do not override the model. Each call is stateless: pass the spec, target paths, and reference paths. Code Writer matches existing patterns and does not run the test.

A plain chat that is not on that path writes the files directly. If you were started as a subagent, write them yourself and do not invoke Code Writer. Only the hidden Orchestrator may delegate while it is a subagent. Code Writer and Verifier never delegate.

## Workflow

1. **Understand the bug.** Identify the intended behavior, current behavior, affected path, and smallest observable reproduction. This is debugging: stay in this chat and targeted-`Read` the section (`limit` / `offset`). Do not send it to Bulk Reader (`.github/skills/bulk-reader/SKILL.md`).
2. **Choose the narrowest executable check.** Prefer the closest unit, component, integration, or regression test already used for that codepath. If no practical test path is obvious, do not create one from scratch just to satisfy the workflow.
3. **Write the failing test first.** Add the smallest focused test that would have caught the bug. The test should encode intended behavior, not mirror the current implementation.
4. **Run the new test before fixing.** The first run is expected to fail. Confirm it fails for the intended reason (the bug). If it passes, or fails for an unrelated reason, correct the test before editing the implementation.
5. **Fix the bug.** Make the smallest production change that satisfies the intended behavior while preserving nearby contracts.
6. **Check diagnostics, then rerun.** `read/problems` on the edited files is early feedback only. Code Writer checks that on files it wrote. Rerun the same check and confirm it now passes.

## Which command

From this Goat repo, run `uv run goat context --repo <name> --format json` and use that repo's `tooling.suggested_verify`. When the list is the whole suite and that repo already has a way to run one test, run the new test. Do not invent npm or make targets. Do not pass a flag that `docs/cli.md` does not list.

When this chat is the primary Implementer, invoke **Verifier** (`.github/agents/verifier.agent.md`) with `#tool:agent`, the exact command, the cwd, and the expected result.

- First run: `expected: fail on test X`. A per-command `fail` that matches that sentence is the expected red. Verifier's summary for a matched expectation is `result: pass`. That is not the stop in `.github/skills/goat-implement/SKILL.md` (Verifier `result: fail`).
- After the fix: `expected: pass`. A `fail` here, or any run that does not match what you passed, is `result: fail`. Stop and report.

Otherwise run the command in this chat. The first run is still expected to fail. If you were started as a subagent, run it yourself. Verifier never delegates.

## If a failing test is impractical

Use the closest executable regression check instead: a targeted script, manual reproduction command, browser check, snapshot comparison, log assertion, or focused integration check.

Prefer no new test over a bad test. A bad test is one that mostly tests mocks, encodes current implementation details, depends on timing or unrelated global state, needs expensive infrastructure for a small fix, or would be deleted immediately after proving the fix.

## Guardrails

- Do not change tests merely to match a wrong implementation.
- Do not weaken existing assertions unless the expected behavior has genuinely changed and the reason is clear.
- Keep the regression test focused on the bug. Avoid broad fixture churn or unrelated coverage expansion.
- If the bug is flaky, make the test deterministic where possible and document the signal being locked down.
- If the bug exposes a broader class of failures, first land the focused regression path, then consider additional sibling coverage.

## Final response

Report the evidence, not just the outcome:

- Name the failing-before test or executable check and the failure it produced.
- Name the passing-after test run and any nearby validation performed.
- If failing-before evidence could not be demonstrated, state why and describe the closest regression check used instead.

Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md

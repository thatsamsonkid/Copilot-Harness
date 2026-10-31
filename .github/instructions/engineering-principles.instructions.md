---
name: Engineering principles
description: Use when planning work, drafting a Jira ticket, editing code, answering a how-to question, or deciding whether a change is done.
applyTo: "**"
---

# Engineering principles

When this file conflicts with `AGENTS.md`, `.github/copilot-instructions.md`, or a loaded skill, follow those. A sibling's own instructions still win inside that repo.

## Laziness protocol

Make the smallest change that solves the problem. Record a repeated decision once, in the catalog, skill, or instruction file that already owns it, and point at it. Do not add a layer, a new flag, or a second copy of a rule.

## Subtract before you add

Remove dead code, redundant checks, and content-free stubs before adding behavior. Skip speculative validators and unused parsers. Do not delete Jira, Figma, or Bruno hard rules to shorten a prompt.

## Fix root causes

Reproduce first. Fix the first wrong decision, not the line where it became visible. Handle a state at the symptom only when that state is legitimate; otherwise find what produced it. Read the actual error. Do not print secrets or read `.env`.

## Prove it works

Check the command output, the value on disk, or the diff. "It compiles", a timestamp, or a self-report is not proof. `read/problems` is early feedback only. Use `tooling.suggested_verify` from `goat context`. On `/goat-implement`, **Verifier** runs the named checks and reports pass or fail. A new chat that only has the plan file runs those commands itself and does not spawn Verifier. Do not invent npm or make targets.

## Never block on the human

Decide reversible in-scope details without asking, then show the result. Product direction stays with the human.

Harness approval points still wait. Jira stays read-only: do not create or update an issue, and do not ask for a token. `/goat-plan` does not implement in that turn. `/prepare-jira` still asks every missing field, including an unknown issue type, in one batched message, and does not implement. Any other ask already written in `AGENTS.md`, `.github/copilot-instructions.md`, or the loaded skill also waits. Confirm force-push, data deletion, and outbound messages.

## Guard the context window

Keep raw file text out of the main thread. For a survey of named files, load `.github/skills/bulk-reader/SKILL.md` (or the user runs `/bulk-reader`). Debugging, architecture, safety, and edits stay in this chat: targeted `Read` with `limit`/`offset`. Hooks in `.github/hooks` deny a whole-file `Read` and `cat` / `head` / `tail` / `less` / `more` on large files. Do not edit from Bulk Reader line numbers. Only the hidden Orchestrator may delegate while it is a subagent. Its workers (Bulk Reader, Code Writer, and Verifier) never delegate.

## Sequence verifiable units

Each unit ends in a green check before the next starts. Stop and report on red; do not improvise the next step.

A small task the user already asked for needs no written `plans/` file. A ticket still gets a plan of repos, files, risks, and tests in the chat, and waits until they ask to implement. Write `plans/<YYYY-MM-DD>-<slug>.plan.md` from `templates/plan.md` when they ask to plan, when another chat will execute, or when an executor would have to guess. `/goat-implement` stops if that file is missing. One pull request per sibling. Order commits inside that PR so each is checkable.

## Test behavior, not implementation

Assert what a caller can observe: a return value, exit code, error type, or an outside effect. The test fails when that behavior breaks and still passes when only internals change. Drive the public interface and derive the expected value from the requirement. Do not pin private helpers or call order.

## Migrate callers, then delete legacy APIs

When no external caller needs the old internal API, move callers and tests to the new contract and delete the old API in the same change. Do not leave a compatibility shim. A command listed by `goat commands` or `docs/cli.md` is public; drop it only when the user asked for that break. Do not invent commands or flags.

## Boundary discipline

Validate where data enters: CLI args, catalog YAML, config parse, and external responses. Inside the system, trust typed values and do not re-check them. Keep logic in pure functions and the shell thin. Follow the sibling's own instructions before editing it.

Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md

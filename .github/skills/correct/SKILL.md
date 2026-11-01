---
name: correct
description: Make a repeated mistake impossible in a sibling repo, at the highest level that works.
argument-hint: mistake class or sibling repo
disable-model-invocation: true
---

# Correct

The same mistake keeps showing up in a sibling product repo. Change that repo so the next agent cannot make it. Never edit this harness.

Do this in this chat. If you were started as a subagent other than Orchestrator, do every read yourself and do not invoke Bulk Reader. Only the hidden Orchestrator may delegate while it is a subagent. Bulk Reader never delegates. Do not send the investigation to Bulk Reader.

Do not read `.env`, print a token, or ask anyone to paste a token. Do not clone a repo into this goat folder. Do not nest a product clone inside this repo. Do not invent a command or flag. The catalog is `docs/cli.md`.

Do not store the lesson in this repo. `docs/knowledge.md` keeps product knowledge in the sibling.

## Target

The target is a sibling product repo. Never this Goat repo. Never edit this harness.

Do not `cd` into a sibling first. Stay in the Goat folder. Run `uv run goat context --format json` and take `<repo-path>` from that repo's `repos[].path`. That field is the absolute clone path. Stay inside `workspace.repos`. Do not use `relpath`. If the user names a repo, run `uv run goat context --repo <name> --format json`.

If `repos[].cloned` is false, say that sibling is not on disk. Do not clone it. If the user did not name a repo and more than one product repo remains, name them and stop. Do not guess.

Every git command is `git -C <repo-path>`.

```bash
git -C <repo-path> log --oneline -n 40
git -C <repo-path> status --porcelain
```

## Mistake class

A mistake class needs at least two pieces of evidence. One correction is not a class. Evidence is two commits, two review notes, two failing runs, or two times the user corrected the same move. Read recent history with `git -C <repo-path>`, the sibling's instruction file, and comments that explain a workaround. Group them. Skip a class that does not clear two pieces of evidence.

## Fix ladder

Use the highest level that works. Try them in this order. Stop at the first level that makes the class impossible. Say which level you picked and why each higher level did not work.

1. **Architecture.** Give each piece of state one owner and each task one supported way. Hide internals so the wrong import fails. Replace a hand-synced list with one source of truth. Delete an old way an agent would copy.
2. **Types.** Shape the types so the bad state cannot be written. If the bad code still type-checks, add a lint whose error message names the fix.
3. **Test.** Lock the behavior with a test. Fix or delete a test that still passes when the behavior breaks, or that fails when only internals change.
4. **Docs last.** Write docs or an agent rule only for a judgment call. Nothing fails when an agent skips them. Docs are last.

## Prove it

Show each new check failing on a real past mistake before it lands. Reconstruct that mistake (the old revision, or the code while it is still broken) and run the check. The run must fail because of that mistake. Record the command and the output. Then make the check pass on the current tree. Do not land a check that you did not see fail.

Take the command from `tooling.suggested_verify` in that `goat context` JSON. Do not invent npm or make targets. `read/problems` is early feedback, not the proof.

One commit per check, in the sibling at `<repo-path>`, is fine. The commit includes the check and its table row, and it is green. Never push.

## Rule table

Keep a rule -> enforcer table in that product repo's own instruction file. That file is the sibling's `AGENTS.md` or its `.github/copilot-instructions.md`. Never put that table in this harness.

| Rule | Enforcer |
| --- | --- |
| <one sentence> | the architecture, the types, the lint, or the test |

When the user corrects you and the rule is already in the table with nothing enforcing it, that is a repeat. Fix it at the highest level in the same change. Drop a rule once its mistake cannot happen.

## Who writes

This skill waits for approval before writing. Show the class, the two pieces of evidence, the level, and the check. Do not write a file, and do not commit, until the user approves. If the user does not approve, add nothing.

After approval, writes stay inside `<repo-path>`. Never edit this harness.

When this chat is the primary Implementer (`/goat-implement`, `.github/skills/implementing/SKILL.md`, or the user picked Implementer), those product-file edits go through **Code Writer** (`.github/agents/code-writer.agent.md`) with `#tool:agent`. Do not edit those files yourself. The name is case-sensitive. Its profile pins Copilot Auto (`Auto (copilot)`). Do not override the model. Each call is stateless: pass the spec, the target paths, and the reference paths. Invoke **Verifier** (`.github/agents/verifier.agent.md`) with `#tool:agent` for the failing run and the rerun. Pass `expected: fail` for the proof against the past mistake, then `expected: pass` once the check is green.

A plain chat that is not on that path writes the files directly and runs the commands in this chat. If you were started as a subagent, write them yourself and run the commands yourself. Do not invoke Code Writer or Verifier. Only the hidden Orchestrator may delegate while it is a subagent. Code Writer and Verifier never delegate.

## What to hand back

For each class: the evidence, the level you picked, why a higher level did not work, the command that failed on the past mistake, and the commit you made in the sibling. Say that you did not push. Say that this harness was not edited.

Code-change judgment stays in `.github/instructions/engineering-principles.instructions.md`.

Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md

---
name: no-comments
description: Delete comments outside the keep-list after Comment Reviewer reports them, and wait before encoding a constraint.
argument-hint: files, symbol, or diff
disable-model-invocation: true
---

# No comments

Remove comments that carry no keep-list exception. Invoke Comment Reviewer for the proposal. This chat audits that report, then deletes only the accepted comments.

Do not read `.env`, print a token, or ask anyone to paste a token. Do not clone a repo into this goat folder. Do not invent a command or flag. The catalog is `docs/cli.md`.

## Who reviews

If you were started as a subagent other than Orchestrator, do every read yourself and do not invoke Bulk Reader. Review in this chat and do not invoke Comment Reviewer. Only the hidden Orchestrator may delegate while it is a subagent. Comment Reviewer never delegates.

Otherwise invoke **Comment Reviewer** (`.github/agents/comment-reviewer.agent.md`) with `#tool:agent`. The name is case-sensitive. Its profile pins Copilot Auto (`Auto (copilot)`). Do not override the model. The call is stateless: pass the repo path, the files in the diff, and ask for `path:line` bullets only. Comment Reviewer has no shell. Do not ask it to run git.

## Scope

The scope is what the user names. Otherwise it is the branch diff from the merge base, through the working tree, in the sibling product repo. Never this Goat repo.

Do not `cd` into a sibling first. Stay in the Goat folder. Run `uv run goat context --format json` and take `<repo-path>` from that repo's `repos[].path`. That field is the absolute clone path. Stay inside `workspace.repos`. Do not use `relpath`. If the user names a repo, run `uv run goat context --repo <name> --format json`.

Run `uv run goat status --format json` and read `repos[].cloned`, `repos[].git.present`, and `repos[].git.default_branch`. Skip a repo whose `cloned` is false or whose `repos[].git.present` is false. Say that sibling is not on disk. Do not clone it. If the user did not name a repo, use each remaining workspace repo whose `repos[].git.branch` is not `repos[].git.default_branch`, or whose `repos[].git.dirty` is true. If none qualify, say there is no branch diff and stop. Every git command is `git -C <repo-path>`.

```bash
git -C <repo-path> merge-base HEAD <default-branch>
git -C <repo-path> diff <merge-base>
```

`<default-branch>` is `repos[].git.default_branch`. If that ref is missing locally, use `origin/<default-branch>` in the same `git -C <repo-path>` form. Deletions stay inside that diff. Do not edit a file in this harness.

## Audit

Read the report before deleting anything.

- Reject a bullet whose path is outside the scoped diff, or inside this Goat repo.
- Reject any change that is not a comment deletion. Application code stays. A `MUST KILL` line is a report, not an edit.
- A skip survives only with proof. The proof is the keep-list clause and the line that shows it: a license header, behavior forced by an external dependency, a formatter or linter directive such as `prettier-ignore`, a public API doc comment, or an issue or RFC link. Restore a deletion only with that proof. If the proof is missing, leave the comment deleted.
- For each `NEEDS /why <symbol>` bullet, run `/how` or `/why` yourself in this chat. Load `.github/skills/how/SKILL.md` or `.github/skills/why/SKILL.md` and follow it for that symbol. Do not hand that question to Comment Reviewer.

If the audit rejects the report, invoke Comment Reviewer once more and name the failure. If that second report is also rejected, do not invoke it again. Fail `/no-comments` and hand back the report. When you are already reviewing in this chat, do not spawn Comment Reviewer to retry. Fail with the report.

## Who deletes

When this chat is the primary Implementer (`/goat-implement`, `.github/skills/implementing/SKILL.md`, or the user picked Implementer), the accepted comment deletions go through **Code Writer** (`.github/agents/code-writer.agent.md`) with `#tool:agent`. Pass only those comment lines. Do not change application code. The name is case-sensitive. Its profile pins Copilot Auto (`Auto (copilot)`). Do not override the model.

A plain chat that is not on that path deletes the comments directly. If you were started as a subagent, delete them yourself and do not invoke Code Writer. Only the hidden Orchestrator may delegate while it is a subagent. Code Writer never delegates.

Delete only accepted comments, and only inside the scoped diff of the sibling at `<repo-path>`. Never edit this harness.

A finding that needs a redesign is reported, not built. Name the `MUST KILL` symbol and its `path:line`. Do not make that change.

## Encodings

When `/why` shows a constraint comment is real (`do not remove`, `do not change`, or `talk to X before changing`), offer the cheapest encoding that can replace it. The choices are a type, a runtime check, a test, or a lint rule. This skill waits for approval before adding any encoding. If the user does not approve, add nothing. Leave the open constraint in the report. Do not delete a comment the keep-list still protects.

## Report

- Deletion count, and each `path:line`.
- Comments restored, with the proof.
- Whether Comment Reviewer was rerun once, and whether `/no-comments` failed on the second report.
- `MUST KILL` symbols left unbuilt.
- Encodings offered, encodings added, and constraints still open.

Code-change judgment stays in `.github/instructions/engineering-principles.instructions.md`.

Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md

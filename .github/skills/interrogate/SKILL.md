---
name: interrogate
description: Stress-test a change with three adversarial lenses. A finding survives only when proven by a run.
argument-hint: change, design, or diff
disable-model-invocation: true
---

# Interrogate

Adversaries try to break a change or a design. A finding survives only when it is proven by a run. Report the findings. Do not apply fixes.

`/review` (`.github/skills/review/SKILL.md`) checks a diff against `done_when`. This skill tries to break the change. A question about what else the change could break is `/blast-radius` (`.github/skills/blast-radius/SKILL.md`).

Do this in this chat, one lens after another. If you were started as a subagent other than Orchestrator, do every read yourself and do not invoke Bulk Reader. Only the hidden Orchestrator may delegate while it is a subagent. Bulk Reader never delegates. Do not send these lenses to Bulk Reader. It cannot run a command, and a finding has to be proven by a run.

Do not read `.env`, print a token, or ask anyone to paste a token. Do not clone a repo into this goat folder. Do not invent a command or flag. The catalog is `docs/cli.md`.

One model runs these three lenses. A second opinion can come from rerunning `/interrogate` after switching the model picker.

## Scope

The scope is what the user names. Otherwise it is the branch diff from the merge base, through the working tree, in the sibling product repo.

Do not `cd` into a sibling first. Stay in the Goat folder. Run `uv run goat context --format json` and take `<repo-path>` from that repo's `repos[].path`. That field is the absolute clone path. Stay inside `workspace.repos`. Do not use `relpath`. If the user names a repo, run `uv run goat context --repo <name> --format json` for that name.

Run `uv run goat status --format json` and read `repos[].cloned`, `repos[].git.present`, `repos[].git.branch`, `repos[].git.default_branch`, and `repos[].git.dirty`. Skip a repo whose `cloned` is false or whose `repos[].git.present` is false. Say that sibling is not on disk. Do not clone it. When the user did not name a repo, use each remaining workspace repo whose `repos[].git.branch` is not `repos[].git.default_branch`, or whose `repos[].git.dirty` is true. Skip this Goat repo. If none qualify, say there is no branch diff and stop.

Every git command is `git -C <repo-path>`.

```bash
git -C <repo-path> merge-base HEAD <default-branch>
git -C <repo-path> diff <merge-base>
git -C <repo-path> status --porcelain
```

`<default-branch>` is `repos[].git.default_branch`. If that ref is missing locally, use `origin/<default-branch>` in the same `git -C <repo-path>` form. `git -C <repo-path> diff <merge-base>` is the branch plus the working tree against the merge base. `git -C <repo-path> status --porcelain` lists untracked files in that tree. If the user named files, symbols, or a design, that named scope replaces the diff.

## Intent

Restate the intent first, in this chat, before any lens. Use the user's message and the commit messages:

```bash
git -C <repo-path> log --format=%B <merge-base>..HEAD
```

Read a pull-request number out of those subjects, such as `(#1234)`. If `gh` is on PATH, run `git -C <repo-path> remote get-url origin`, take `owner/repo` from that URL, and run `gh pr view <number> -R owner/repo`. `-R` is gh's `--repo` flag. If `gh` is missing, or no number is in the subjects, say the pull-request body was not read. Do not describe it as searched.

If the intent is still unclear, say what you think it is, then continue. The user can redirect.

## Three lenses

Run these in this chat, in order. Finish one before the next starts.

1. **Correctness.** Does the code do what the restated intent says? Run that behavior.
2. **Edges and inputs.** Empty, boundary, invalid, and repeated inputs. Run the cases that could break the intent.
3. **State and integration.** State that crosses a later call, a shared store, or another sibling repo. When the scope names two repos, run `uv run goat graph explain`, `goat graph path`, or `goat graph neighbors` (`docs/workspace-graph.md`). If the graph is not built yet, run `uv run goat graph build` first. Each repo still has its own `repos[].path` for `git -C <repo-path>`.

A finding survives only when a command was actually run and its output proves the failure. Record the command, the actual output, and the expected output. Leave out style, naming, and anything you did not run. No findings is a valid result.

Take product test commands from `tooling.suggested_verify` in that `goat context` JSON. Do not invent npm or make targets. A repro script goes in a temp directory created with `mktemp -d`. That directory must sit outside this repo and outside every `repos[].path`. Never commit it. Never copy it into a repo.

## Verify

Before the report, rerun the command for each finding you would keep. Keep it when the rerun shows the same failure and that failure breaks the intent. Drop the rest. Merge findings that share a root cause into one finding, and name each command you ran.

## What to hand back

### Intent

The restatement.

### Findings

For each kept finding: the title, the command, the actual output, the expected output, and how it breaks the intent. When two findings merged, one entry names both commands. Write "no verified findings" when none survive.

### Dropped

What you checked and did not keep, and why: no command was run, the rerun did not reproduce it, it does not break the intent, or it merged into another finding.

Code-change judgment stays in `.github/instructions/engineering-principles.instructions.md`. This skill reports. Do not apply fixes.

Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md

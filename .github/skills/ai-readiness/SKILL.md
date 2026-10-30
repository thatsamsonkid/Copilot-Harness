---
name: ai-readiness
description: Audit product repos in the open workspace for AI-agent readiness. Read-only; does not edit.
argument-hint: workspace id or repo name
disable-model-invocation: true
---

The user wants an AI-readiness audit, not edits. Follow `.github/agents/readiness-auditor.agent.md` — the **Readiness Auditor** agent rules.

1. Run `uv run goat status --format json` and `uv run goat context --format json` from this Goat repo. Run `uv run goat doctor` the same way. After `cd` into a sibling, use `uv run --project "$GOAT_ROOT" python -m goat status --format json`, `uv run --project "$GOAT_ROOT" python -m goat context --format json`, and `uv run --project "$GOAT_ROOT" python -m goat doctor`.
2. Add `--workspace <id>` or `--repo a,b` only when the user names that workspace or those repos. Stay inside `workspace.repos` (`workspace_scope.repos` and the context `repos` array). If `workspace_scope.detected` is false, ask which feature workspace to open. Do not inspect sibling clones that are only on disk.
3. Score the checklist yourself (pass / partial / fail) with `path:line` or goat-context-field evidence. Invoke **Bulk Reader** only for a broad survey, one level; it must not spawn agents. Do the judgment in this chat.
4. Return a per-repo scorecard, a ranked fix list (highest impact first; each fix names the product repo and the file to add or change), and a one-line verdict.

Do not edit, create, or delete files. Do not write findings into this harness. Do not audit this harness. Do not nest clones. Do not read `.env`, keychain output, or print secrets/tokens. Do not ask anyone to paste a token. Do not auto-fix. Do not invent commands or flags.

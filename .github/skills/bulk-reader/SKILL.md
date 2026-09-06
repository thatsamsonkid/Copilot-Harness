---
name: bulk-reader
description: Read large files as structured bullets instead of dumping source. Use when a Read or cat/head/tail/less/more of a file over the line threshold is blocked, the user asks for /bulk-reader, or many-file context is needed without flooding chat.
argument-hint: question and file paths
---

# Bulk reader

Whole-file reads of large files are blocked by the `check-file-size` and `check-bash-read` hooks (default 350 lines, `GOAT_BULK_READ_MAX_LINES` or `.github/hooks/read-guard.json`). Do not retry `Read` or `cat`/`head`/`tail`/`less`/`more` on that path. Answer from an isolated read.

## How to run

1. Invoke the **Bulk Reader** agent with `#tool:agent`. Agent names are case-sensitive.
2. Each call is stateless. Include the exact question, repo-relative paths or symbols, and what to skip.
3. Ask for structured bullets only (name, type, or `path:line`). No source dump.
4. Parallelize independent file groups. Cap a call at a handful of files.
5. Stay inside `workspace.repos` from `goat context` / `prepare`. Never read `.env` or tokens.

If you must open a slice yourself, use `Read` with a `limit` (and `offset` when you know the start). Piped shell (`cat file | grep …`) is allowed; whole-file `cat`/`less`/`more` is not.

## Output you should expect

- `ClassName` (class, `repo/path.py:12`)
  - `method` (`:40`) — one-line fact
- `MISSING path — not found`

Synthesize those bullets. Do not paste the file into chat.

## Related Copilot customizations

- Feature planning: Jira Planner or `/jira-ticket`
- Hooks: `.github/hooks/check-file-size.json`, `.github/hooks/check-bash-read.json`

---
name: orchestrate
description: Gather context via Bulk Reader, then generate files via Code Writer
argument-hint: question, ticket, or files to generate
agent: agent
---

The user wants many-file context or generated files without flooding this chat. Use the **Orchestrator** agent rules.

1. Run `uv run goat context --format json` (or `goat prepare <KEY>` if a Jira key is present). Stay inside `workspace.repos`.
2. Decide which files or symbols to inspect from Graphify reports and instruction paths — do not grep a monorepo first.
3. Delegate every file read to **Bulk Reader** (`#tool:agent`). Each call is stateless: exact question, repo-relative paths, what to skip. Parallelize independent groups.
4. When they want code generated, call **Code Writer** (`#tool:agent`) with the spec, target paths, and reference paths from the reader. Do not write files yourself.
5. Synthesize. Quote paths and symbols. Do not dump source unless they asked.

Do not implement verify/branch/docs here. Hand off to Implementer when the user is ready.

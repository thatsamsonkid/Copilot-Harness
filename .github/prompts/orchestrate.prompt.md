---
name: orchestrate
description: Gather codebase context via Bulk Reader, then answer or plan
argument-hint: question, ticket, or area to inspect
agent: agent
---

The user wants context from many files without flooding this chat. Use the **Orchestrator** agent rules.

1. Run `uv run goat context --format json` (or `goat prepare <KEY>` if a Jira key is present). Stay inside `workspace.repos`.
2. Decide which files or symbols to inspect from Graphify reports and instruction paths — do not grep a monorepo first.
3. Delegate every file read to **Bulk Reader** (`#tool:agent`). Each call is stateless: exact question, repo-relative paths, what to skip. Parallelize independent groups.
4. Synthesize the structured bullets. Quote paths and symbols. Do not dump source.

Do not implement. Do not edit product code. Hand off to Implementer when the user is ready.

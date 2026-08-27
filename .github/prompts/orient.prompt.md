---
name: orient
description: Map sibling repos with Graphify and local instructions when the prompt is vague
argument-hint: what area or ticket is this about?
agent: plan
---

The user has a vague, broad, or low-context request (no ticket, unclear repo, or "how does this work?"). Load `.github/skills/workspace-context/SKILL.md`.

1. Run `#tool:runCommands` with `uv run harness context --format json`.
2. Summarize each cloned repo: Graphify report present or not, instruction files, knowledge notes/ADRs, suggested verify commands, and `readiness.gaps` if `alignment.ok` is false.
3. If any `graphify.report` or `knowledge.files` exist, read those Markdown files before searching product code.
4. If the user named two concepts, prefer `graphify path` / `graphify query` from the JSON over grepping a monorepo.
5. Ask which repo or Graphify community to work in unless the answer is obvious.
6. If they have a Jira key, switch to `uv run harness prepare <KEY> --format json` and continue from that routing.
7. Produce a short orientation: likely repos, files or communities to inspect, and what is still unknown.

Do not implement. Do not rebuild a Graphify graph unless the user asked. Do not copy sibling standards into the harness repo.

---
name: goat-implement
description: Start implementing an agreed plans/ file — Code Writer for product files, Verifier for checks (survives chat compaction)
argument-hint: PROJ-123
agent: agent
tools: ['agent', 'edit', 'runCommands']
---

The user wants to start implementing an agreed plan. Chat compaction may have dropped the planning-turn reminder. Load `.github/skills/implementing/SKILL.md` and follow it even if this chat wrote the plan earlier.

Never spawn Implementer. You become Implementer in this chat.

1. Find the plan file (`plans/<YYYY-MM-DD>-<key-or-slug>.plan.md`, or `${input:issue:}` / the path they named). If none exists, stop and tell them to run `/goat-plan` first.
2. Run `#tool:runCommands` with `uv run goat status --format json`. If a Jira key is present, run `uv run goat prepare <KEY> --format json` and treat `done_when` as the stop condition. Stay inside the plan repos and `workspace.repos` from `uv run goat context --format json`.
3. Before the first product edit, run `uv run goat branch <KEY>`. Refuse to create the branch on a dirty tree.
4. For every product-file write, invoke **Code Writer** (`#tool:agent`) with the spec, target paths, and reference paths. Do not `#tool:edit` product files yourself. Do not spawn Implementer. You still write goat catalog, feature notes, and ADRs yourself.
5. After each step's writes, invoke **Verifier** (`#tool:agent`) with that step's Verify command, cwd, and expected result. After all steps, invoke Verifier with the plan **Verification** section and each repo's `tooling.suggested_verify`. If Verifier reports fail, stop and report — do not improvise.
6. Stop when `done_when` holds. Add sibling feature notes / ADRs when the change is user-visible or a real design choice.

A new chat that was handed only the plan file and did **not** run `/goat-implement` is the executor and writes the files itself (no Code Writer or Verifier). That is not this command.

Do not pick Orchestrator. Do not read `.env` or print tokens.

---
name: goat-implement
description: Start implementing an agreed plans/ file — fan out Bulk Readers per Survey groups, Code Writers per Parallel waves row, then Verifier (survives chat compaction)
argument-hint: PROJ-123
agent: agent
tools: ['agent', 'edit', 'runCommands']
---

The user wants to start implementing an agreed plan. Chat compaction may have dropped the planning-turn reminder. Load `.github/skills/implementing/SKILL.md` and follow it even if this chat wrote the plan earlier.

Never spawn Implementer. You become Implementer in this chat.

1. Find the plan file (`plans/<YYYY-MM-DD>-<key-or-slug>.plan.md`, or `${input:issue:}` / the path they named). If none exists, stop and tell them to run `/goat-plan` first.
2. Run `#tool:runCommands` with `uv run goat status --format json`. If a Jira key is present, run `uv run goat prepare <KEY> --format json` and treat `done_when` as the stop condition. Stay inside the plan repos and `workspace.repos` from `uv run goat context --format json`.
3. Before the first product edit, run `uv run goat branch <KEY>`. Refuse to create the branch on a dirty tree.
4. Walk **Parallel waves** in order. Before writes, fan out **Bulk Reader** (`#tool:agent`) once per **Survey groups** row for that wave (or group `Model after` / reference paths by repo). Then for every product-file write, invoke **Code Writer** (`#tool:agent`) — one call per independent step in the wave, issued together in the same turn — with that step's spec, target paths, and reference paths. Do not send two writers or two readers the same file. Do not `#tool:edit` product files yourself. Do not spawn Implementer. You still write goat catalog, feature notes, and ADRs yourself. If **Parallel waves** is missing, treat each step as its own wave.
5. After every writer in a wave returns, invoke **Verifier** (`#tool:agent`) with that wave's Verify commands, cwds, and expected results (fan out Verifiers when repos/cwds differ; let every Verifier in the wave finish). You own the retry counter. First `fail` may bounce that step through one bounded repair (Code Writer + Verifier once); a second `fail` is yours to investigate (targeted-`Read`, no third writer). `missing`, shared-contract, and safety-critical fails skip the repair. After all waves, invoke Verifier with the plan **Verification** section and each repo's `tooling.suggested_verify`. Do not start the next wave until every step is `pass` or you have escalated.
6. Stop when `done_when` holds. Add sibling feature notes / ADRs when the change is user-visible or a real design choice.

A new chat that was handed only the plan file and did **not** run `/goat-implement` is the executor and writes the files itself (no Code Writer or Verifier). That is not this command.

Do not pick Orchestrator. Do not read `.env` or print tokens.

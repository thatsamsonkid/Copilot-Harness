---
name: typescript
description: Edit TypeScript, Angular, React, or Node in a sibling repo using that repo's tooling
argument-hint: repo or area
agent: agent
---

The user wants TypeScript work (`.ts` / `.tsx`, Angular, React, Node) in a product sibling. Load `.github/skills/typescript/SKILL.md` and follow it.

1. Run `#tool:runCommands` from the goat repo: `uv run goat context --repo <name> --format json` (or `uv run goat context --format json` for the open workspace). If cwd is a sibling, use `uv run --project "$GOAT_ROOT" goat context --repo <name> --format json`.
2. Read that repo's instruction files. Those win over goat defaults. Do not invent style rules.
3. Use `tooling.suggested_verify` and the lockfile runner. Do not add package.json scripts unless asked.
4. Keep TypeScript strict. Do not add `any` or hand-edit generated clients.
5. After edits, run the suggested verify commands and report the result.

Do not copy product TypeScript standards into this goat.

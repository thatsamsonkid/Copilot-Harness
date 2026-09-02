---
name: TypeScript
description: How to edit TypeScript in sibling product repos
applyTo: "**/*.ts,**/*.tsx,**/*.mts,**/*.cts"
---

TypeScript product code lives in sibling clones. Load `.github/skills/typescript/SKILL.md` before the first edit.

- Run `uv run goat context --repo <name> --format json` and follow that repo's instruction files. Those win over goat defaults.
- Use `tooling.suggested_verify` and the lockfile runner (`pnpm` / `yarn` / `bun` / `npm`). Do not invent package.json scripts.
- Keep types strict. Do not add `any`, `@ts-ignore`, or weaken `tsconfig` to silence errors.
- Reuse existing types and generated clients. Do not hand-edit `tooling.generated` paths.
- Match the stack already in the file (Angular, React, Analog, Node). Do not introduce a new state or CSS library.
- After edits, run that repo's lint / test / typecheck. Do not skip a red command.

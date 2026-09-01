---
name: typescript
description: Write or review TypeScript, Angular, React, or Node in a sibling repo. Use when editing .ts/.tsx, package.json, or a TypeScript frontend. Follow that repo's instructions and tooling.suggested_verify. Do not invent npm scripts or copy product style into goat.
---

# TypeScript

Product TypeScript lives in sibling clones, not this goat. Load this skill before editing `.ts` / `.tsx` in a workspace repo. Path-scoped rules live in `.github/instructions/typescript.instructions.md`.

## Before the first edit

1. Run `uv run goat context --repo <name> --format json` from the goat repo (or `uv run --project "$GOAT_ROOT" goat context --repo <name>`). Bare `uv run goat` cannot spawn from a product clone.
2. Read that repo's `instructions` (`AGENTS.md`, `copilot-instructions.md`, path-specific `*.instructions.md`). Those win over anything here.
3. Use `tooling.suggested_verify` and `tooling.package_scripts`. Do not invent `npm` / `pnpm` / `yarn` scripts.
4. If `graphify.report` is present and the edit location is unclear, read it before grepping.

## Tooling

Detect the package manager from lockfiles. `goat context` already does this for `suggested_verify`.

| Lockfile | Runner |
| --- | --- |
| `pnpm-lock.yaml` | `pnpm` |
| `yarn.lock` | `yarn` |
| `bun.lock` / `bun.lockb` | `bun run` |
| otherwise | `npm run` |

- Prefer `tooling.suggested_verify` (`lint`, `test`, `typecheck`) after edits.
- In an Nx / Turborepo, run the package Graphify named (`nx test <project>`, `turbo run test --filter=…`). Do not typecheck the whole monorepo first.
- Do not add a new script to `package.json` unless the user asked or no existing script fits.
- Do not commit `node_modules/`. Do not bump lockfiles unless the change needs a dependency.

## Code rules

Sibling conventions beat these defaults. When the repo is silent:

- Match the file you are in: imports, naming, Angular vs React vs Analog vs Node.
- Keep TypeScript strict. Do not add `any`, `@ts-ignore`, or `as unknown as` to silence the compiler.
- Reuse existing types, Zod/io-ts schemas, and generated API clients. Do not hand-edit `tooling.generated` paths (Nx, OpenAPI, graphql-codegen).
- Do not introduce a new state library, CSS approach, or test runner when one already exists.
- Tests live next to existing `*.spec.ts` / `*.test.ts` files, using that repo's runner (Jest, Vitest, Angular TestBed).
- Angular proxies stay a start-workspace concern. Do not hard-code production backend URLs in frontend code.

## Hard rules

- Do not copy this repo's TypeScript habits into goat docs or invent a style guide here.
- Do not `cd` into the sibling and run `uv run goat` (Failed to spawn). Use `--project "$GOAT_ROOT"` or the `goat` shim.
- Do not start the app by reconstructing `.vscode/launch.json`. Use `goat start` / `goat start run`.
- Stop when `tooling.suggested_verify` passes (or report the failure). Do not skip a red lint/typecheck.

## Failures

| Symptom | What to do |
| --- | --- |
| No `suggested_verify` | Read `package.json` scripts. Run the existing `lint` / `test` / `typecheck` with the lockfile runner. |
| `any` / type errors | Fix types. Do not weaken `tsconfig` or add `any`. |
| Generated client is wrong | Regenerate with the repo's OpenAPI / graphql-codegen command. Do not patch the output. |
| Failed to spawn: goat | Cwd is a sibling. Re-run from this repo or `uv run --project "$GOAT_ROOT" goat …` |

## Related Copilot customizations

- Vague / large-repo orientation: workspace-context skill or `/orient`
- Local stack start: workspace-start skill or `/start-workspace`
- Python siblings: python skill or `/python`
- Java / Spring siblings: java skill or `/java`

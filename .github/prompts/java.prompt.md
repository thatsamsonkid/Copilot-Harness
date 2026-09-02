---
name: java
description: Edit Java or Spring Boot in a sibling repo without reading launch.json
argument-hint: repo or area
agent: agent
---

The user wants Java or Spring Boot work in a product sibling. Load `.github/skills/java/SKILL.md` and follow it.

1. Run `#tool:runCommands` from the goat repo: `uv run goat context --repo <name> --format json`. If cwd is a sibling, use `uv run --project "$GOAT_ROOT" goat context --repo <name> --format json`.
2. Read that repo's instruction files. Those win over goat defaults. Do not invent style rules.
3. Prefer `./mvnw` or `./gradlew`. Use `tooling.suggested_verify` when present.
4. Never read `.vscode/launch.json` or product `.env`. Start with `goat start run --repo <name>` or Run Without Debugging.
5. After edits, run the suggested verify commands and report the result.

Do not copy product Java architecture into this goat.

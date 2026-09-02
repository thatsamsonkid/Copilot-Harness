---
name: Java
description: How to edit Java and Spring Boot in sibling product repos
applyTo: "**/*.java"
---

Java product code lives in sibling clones. Load `.github/skills/java/SKILL.md` before the first edit.

- Run `uv run goat context --repo <name> --format json` and follow that repo's instruction files. Those win over goat defaults.
- Prefer `./mvnw` or `./gradlew` for test and boot. Use `tooling.suggested_verify` when present.
- Never read `.vscode/launch.json` or product `.env`. Start with `goat start run --repo <name>` or Run Without Debugging.
- Match the existing package layout and Spring layer. Do not invent a new web stack or hand-edit generated clients.
- Keep secrets out of source. Do not commit `target/` or `build/`.
- After edits, run that repo's tests. Do not skip a red `mvn` / `gradle` command.

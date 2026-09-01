---
name: java
description: Write or review Java or Spring Boot in a sibling repo. Use when editing .java, pom.xml, Gradle, or a Spring service. Never read launch.json. Start with goat start run. Follow that repo's package layout and tooling.suggested_verify.
---

# Java

Product Java lives in sibling clones, not this goat. Load this skill before editing `.java`, `pom.xml`, or Gradle files in a workspace repo. Path-scoped rules live in `.github/instructions/java.instructions.md`.

Java apps often keep VM args and environment variables in `.vscode/launch.json`. Those values must not enter chat. Start those apps with `goat start run --repo <name>` or VS Code **Run Without Debugging**.

## Before the first edit

1. Run `uv run goat context --repo <name> --format json` from the goat repo (or `uv run --project "$GOAT_ROOT" goat context --repo <name>`). Bare `uv run goat` cannot spawn from a product clone.
2. Read that repo's `instructions`. Those win over anything here.
3. Use `tooling.suggested_verify`. Prefer the Maven / Gradle wrapper in that repo (`./mvnw`, `./gradlew`).
4. If `graphify.report` is present and the edit location is unclear, read it before grepping.

## Tooling

| Marker | Default verify when `suggested_verify` is empty | Default start (via `goat start`) |
| --- | --- | --- |
| `mvnw` / `mvnw.cmd` | `./mvnw test` | `./mvnw spring-boot:run` |
| `pom.xml` | `mvn test` | `mvn spring-boot:run` |
| `gradlew` / `gradlew.bat` | `./gradlew test` | `./gradlew bootRun` |
| `build.gradle` / `.kts` | `gradle test` | `gradle bootRun` |

- Prefer wrappers (`mvnw`, `gradlew`) so the repo's toolchain version is used.
- Do not add a Maven/Gradle plugin or Spring starter unless the change needs it.
- Do not commit `target/`, `build/`, or `.idea/` unless that repo already tracks them.
- Do not read `.vscode/launch.json` or product `.env` files. Use `goat start`, `goat start run`, and `goat start env` (keys only).

## Code rules

Sibling conventions beat these defaults. When the repo is silent:

- Match the package and layer you are in (controller, service, repository, config). Do not invent a new package tree.
- Follow existing Spring annotations, constructor injection, and JSON DTOs. Do not introduce a second web stack.
- Reuse existing types and generated API clients. Do not hand-edit `tooling.generated` paths (OpenAPI, etc.).
- Tests: JUnit next to existing `*Test.java` / `*IT.java`. Use the same Spring Boot test annotations that file already uses.
- Keep secrets out of source. Do not hard-code credentials or print env values.

## Hard rules

- Never read `launch.json` env/args into chat. `run_via: goat` means `goat start run --repo <name>`.
- Do not copy product Java architecture into this goat.
- Do not `cd` into the sibling and run `uv run goat` (Failed to spawn). Use `--project "$GOAT_ROOT"` or the `goat` shim.
- Java boots can take minutes. After `goat start run`, wait; do not start the next service yet (see workspace-start).
- Stop when `tooling.suggested_verify` passes. Do not skip a red `mvn` / `gradle` test.

## Failures

| Symptom | What to do |
| --- | --- |
| No `suggested_verify` | Run `./mvnw test` or `./gradlew test` when those wrappers exist. |
| App needs launch.json env | `goat start run --repo <name>` or Run Without Debugging. Do not cat launch.json. |
| Boot is slow | Say so and wait. Do not start frontends until the port is listening. |
| Failed to spawn: goat | Cwd is a sibling. Re-run from this repo or `uv run --project "$GOAT_ROOT" goat …` |

## Related Copilot customizations

- Local stack start: workspace-start skill or `/start-workspace`
- Vague / large-repo orientation: workspace-context skill or `/orient`
- TypeScript siblings: typescript skill or `/typescript`
- Python siblings: python skill or `/python`

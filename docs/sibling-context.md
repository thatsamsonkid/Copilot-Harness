# Sibling Copilot context

The harness does not own product style guides. It **does** expect each listed
clone to have enough local context that Copilot can find how to work and how
to verify.

`harness context` discovers that context. `harness context --check` fails when
a **cloned** repo is missing the required pieces. `harness doctor` reports the
same gaps as advisories so first-run stays green.

## Required in each product repo

| Piece | Where we look | Why |
| --- | --- | --- |
| Agent / Copilot instructions | `AGENTS.md` or `.github/copilot-instructions.md` | How to edit this repo |
| Verify command | Makefile / `package.json` / justfile / `pyproject.toml`, or `verify:` in `repositories.yml` | What to run after edits |

`CONTRIBUTING.md`, path-specific `*.instructions.md`, and skills still get
listed when present. They do not satisfy the instruction check by themselves.

## How verify is discovered

In order, first match wins within each source, then sources are combined
(declared first):

1. `verify:` on the `repositories.yml` entry (existing or ad hoc repos)
2. Makefile targets: `verify`, `check`, then `lint` / `test` / `format`
3. justfile recipes with the same names
4. `package.json` scripts: `verify`, `check`, then `lint` / `test` / `typecheck` / `format`
5. If nothing else matched and `pyproject.toml` exists: `uv run pytest`

Set `verify:` when the real command is something discovery will miss
(`./gradlew check`, `just ci`, a monorepo package script). Do not copy the
product's lint rules into this harness.

```yaml
  - name: billing
    url: git@github.com:YOUR_ORG/billing.git
    tags: [api, backend]
    verify:
      - ./gradlew check
```

## Optional

| Piece | Where we look |
| --- | --- |
| Graphify | `graphify-out/` (or `graphify.out`). Set `graphify: false` to skip |
| Feature notes / ADRs | `docs/features/`, `docs/adr/` — see [knowledge.md](knowledge.md) |

## Aligning an existing repo

1. Clone it and add it to `repositories.yml` (`name`, `url`, `tags`).
2. Run `uv run harness context --repo <name> --check`.
3. Add the missing instruction file **in that sibling**, and either a
   conventional verify target there or `verify:` on the manifest entry.
4. Re-run the check. Do not invent a test command in chat.

`/orient` and Implementer should report `readiness.gaps` instead of guessing.

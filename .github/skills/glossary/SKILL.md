---
name: glossary
description: Look up or add workplace words and acronyms so Copilot uses the team's language. Use when a prompt has unknown jargon, someone asks what a term means, or they want to grow the shared or personal dictionary. Always ask whether a new term is public or private. Short definitions only — not product architecture.
argument-hint: TERM
---

# Workplace glossary

Two dictionaries, merged on lookup:

| File | Visibility | Git |
| --- | --- | --- |
| `catalog/glossary.yml` | public (team) | committed |
| `catalog/glossary.local.yml` | private (personal) | gitignored |
| `<sibling>/docs/glossary.yml` | public (one product) | committed in that repo |

This is how people talk, not how the code works.

## Commands

Run these from the goat repo. After `cd` into a sibling, `uv run goat` cannot spawn — use `uv run --project "$GOAT_ROOT" goat …` or `./scripts/goat.sh`.

| User intent | Command |
| --- | --- |
| List the dictionary | `uv run goat glossary list --format json` |
| Only public or only private | `uv run goat glossary list --visibility public\|private --format json` |
| Only acronyms | `uv run goat glossary list --kind acronym --format json` |
| Look up one word or alias | `uv run goat glossary get TERM --format json` |
| Search names and meanings | `uv run goat glossary search QUERY --format json` |
| Add a team term | `uv run goat glossary add TERM --meaning "…" --visibility public --format json` |
| Add a personal term | `uv run goat glossary add TERM --meaning "…" --visibility private --format json` |
| Add aliases / related terms | `uv run goat glossary add TERM --meaning "…" --visibility public --also "A,B" --see "C" --kind acronym` |
| Update an existing term | `uv run goat glossary add TERM --meaning "…" --visibility public\|private --replace` |
| Product-only term in a sibling | `uv run goat glossary add TERM --meaning "…" --visibility public --repo <name>` |
| Preview a write | `uv run goat glossary add TERM --meaning "…" --visibility public\|private --dry-run` |

`get` matches the `term` field and `also` aliases (case-insensitive). Unmatched lookups still return JSON (`matched: false`) plus `suggestions`. Do not treat a miss as a crash. The same word can exist as both public and private; show both and say which is personal.

## When to load this

1. The user uses an acronym, project nickname, or process word you do not already know from this glossary.
2. They ask "what does X mean here?" or "we call that Y".
3. They want to start or grow a shared or personal vocabulary so later chats are not confused.

Do not dump `glossary list` into every chat. Look up the specific term. If `goat context` is already in play, its `glossary` field is only a count and the get command — not the definitions.

## Add

1. Confirm the short meaning with the user if they did not give one. `--meaning` is required from chat.
2. **Ask whether the term is public or private** before writing. Do not default. Public is the committed team catalog. Private is this person's overlay and will not be committed.
3. Org language everyone should share: `--visibility public` (omit `--repo`).
4. A nickname or shorthand only this person uses: `--visibility private`.
5. Product language that belongs to one sibling: `--visibility public --repo <name>` (writes that repo's `docs/glossary.yml`). Never combine `--repo` with `--visibility private`.
6. Keep definitions to one or two sentences. No feature walkthroughs, no ADRs.
7. Tell them the `relative` path. Public files are committed team catalog — they should review the diff. Private files are gitignored; say so.

## Hard rules

- Do not invent a definition. If `get` misses, say so, show `suggestions`, and offer `glossary add`.
- Do not write a term without `--visibility public` or `--visibility private`.
- Do not copy product architecture into the glossary. Feature notes stay in sibling `docs/features`.
- Do not read `.env` or print tokens.
- Do not nest clones inside the goat.
- Do not commit `catalog/glossary.local.yml`.

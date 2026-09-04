---
name: glossary
description: Look up or add workplace words and acronyms so Copilot uses the team's language. Use when a prompt has unknown jargon, someone asks what a term means, or they want to grow the shared dictionary. Short definitions only — not product architecture.
argument-hint: TERM
---

# Workplace glossary

Org-wide language lives in this goat (`catalog/glossary.yml`). Product-specific acronyms may live in a sibling `docs/glossary.yml`. The CLI merges both. This is a dictionary of how people talk, not a wiki of how the code works.

## Commands

Run these from the goat repo. After `cd` into a sibling, `uv run goat` cannot spawn — use `uv run --project "$GOAT_ROOT" goat …` or `./scripts/goat.sh`.

| User intent | Command |
| --- | --- |
| List the dictionary | `uv run goat glossary list --format json` |
| Only acronyms | `uv run goat glossary list --kind acronym --format json` |
| Look up one word or alias | `uv run goat glossary get TERM --format json` |
| Search names and meanings | `uv run goat glossary search QUERY --format json` |
| Add an org-wide term | `uv run goat glossary add TERM --meaning "…" --format json` |
| Add aliases / related terms | `uv run goat glossary add TERM --meaning "…" --also "A,B" --see "C" --kind acronym` |
| Update an existing term | `uv run goat glossary add TERM --meaning "…" --replace` |
| Product-only term in a sibling | `uv run goat glossary add TERM --meaning "…" --repo <name>` |
| Preview a write | `uv run goat glossary add TERM --meaning "…" --dry-run` |

`get` matches the `term` field and `also` aliases (case-insensitive). Unmatched lookups still return JSON (`matched: false`) plus `suggestions`. Do not treat a miss as a crash.

## When to load this

1. The user uses an acronym, project nickname, or process word you do not already know from this glossary.
2. They ask "what does X mean here?" or "we call that Y".
3. They want to start or grow a shared vocabulary so later chats are not confused.

Do not dump `glossary list` into every chat. Look up the specific term. If `goat context` is already in play, its `glossary` field is only a count and the get command — not the definitions.

## Add

1. Confirm the short meaning with the user if they did not give one. `--meaning` is required from chat.
2. Org language (process, teams, tools everyone uses) goes in `catalog/glossary.yml` (omit `--repo`).
3. Product language that belongs to one sibling goes in that repo's `docs/glossary.yml` (`--repo <name>`).
4. Keep definitions to one or two sentences. No feature walkthroughs, no ADRs.
5. Tell them the `relative` path. The file is committed team catalog — they should review the diff.

## Hard rules

- Do not invent a definition. If `get` misses, say so, show `suggestions`, and offer `glossary add`.
- Do not copy product architecture into the glossary. Feature notes stay in sibling `docs/features`.
- Do not read `.env` or print tokens.
- Do not nest clones inside the goat.

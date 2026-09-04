---
name: glossary
description: Look up or add workplace words and acronyms so Copilot shares the team's language
argument-hint: TERM
agent: agent
---

The user wants a workplace term, acronym, or shared vocabulary. Load `.github/skills/glossary/SKILL.md`.

If they are **looking up** a word (or used jargon you do not know):

1. Run `#tool:runCommands` with `uv run goat glossary get ${input:term} --format json`. If they gave a phrase rather than a single token, use `uv run goat glossary search "${input:term}" --format json`.
2. If `matched` is true, use those definitions. Quote `meaning`. Mention `also` aliases when present.
3. If `matched` is false, show `suggestions` and ask whether to add the term. Do not invent a definition.

If they are **adding** a word:

1. Confirm a one- or two-sentence meaning if they did not give one.
2. Org-wide language: `uv run goat glossary add TERM --meaning "…" --format json` (add `--also`, `--see`, `--kind` when they named those).
3. Product-only language: add `--repo <name>` so it lands in that sibling `docs/glossary.yml`.
4. Tell them the `relative` path. Do not commit unless they ask.

Do not dump the full glossary. Do not write feature notes here — those stay in sibling `docs/features`.

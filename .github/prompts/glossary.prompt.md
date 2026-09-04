---
name: glossary
description: Look up or add workplace words and acronyms so Copilot shares the team's language
argument-hint: TERM
agent: agent
---

The user wants a workplace term, acronym, or shared vocabulary. Load `.github/skills/glossary/SKILL.md`.

If they are **looking up** a word (or used jargon you do not know):

1. Run `#tool:runCommands` with `uv run goat glossary get ${input:term} --format json`. If they gave a phrase rather than a single token, use `uv run goat glossary search "${input:term}" --format json`.
2. If `matched` is true, use those definitions. Quote `meaning`. Mention `also` aliases and whether each hit is `public` or `private`.
3. If `matched` is false, show `suggestions` and ask whether to add the term. Do not invent a definition.

If they are **adding** a word:

1. Confirm a one- or two-sentence meaning if they did not give one.
2. Ask whether the term is **public** (committed team catalog) or **private** (personal, gitignored). Do not assume. Do not write until they answer.
3. Public org-wide language: `uv run goat glossary add TERM --meaning "…" --visibility public --format json` (add `--also`, `--see`, `--kind` when they named those).
4. Private personal language: same command with `--visibility private`.
5. Product-only language: `--visibility public --repo <name>` so it lands in that sibling `docs/glossary.yml`.
6. Tell them the `relative` path. Do not commit a private file. Do not commit a public file unless they ask.

Do not dump the full glossary. Do not write feature notes here — those stay in sibling `docs/features`.

# Product knowledge

Yes, we should write down features and decisions as people build them. No, that knowledge should not live in this goat.

A central wiki here would be a third source of truth (code, Jira, goat docs). It will rot, and Copilot will start trusting a stale copy over the repo that actually changed.

Workplace **vocabulary** is the exception. Terms and acronyms (how people talk) belong in `catalog/glossary.yml` (public, committed) or `catalog/glossary.local.yml` (private, gitignored) so every chat can look them up with `goat glossary get`. Those files are a dictionary, not a feature wiki. Product behavior still lives next to the code.

## Where knowledge lives

| Kind | Put it here | When |
| --- | --- | --- |
| How a feature works today | `<repo>/docs/features/<slug>.md` | User-visible or non-obvious behavior |
| Why we chose A over B | `<repo>/docs/adr/` or `docs/decisions/` | A real alternative was rejected |
| How the code is shaped | Graphify `graphify-out/` plus `# WHY:` / `# NOTE:` comments | Always; Graphify already indexes these |
| Ticket intent | Jira, via `goat prepare` | The work item, not the architecture |
| How we say it at work | `catalog/glossary.yml` (public org) or `catalog/glossary.local.yml` (private) or `<repo>/docs/glossary.yml` (one product) | An acronym or nickname that confuses Copilot |

The goat only **discovers** feature notes (`goat context` → `knowledge`). It does not store product facts. If a monorepo keeps notes somewhere else, set `knowledge.dirs` on that `repositories.yml` entry.

`goat glossary list` / `get` / `search` / `add` is the vocabulary CLI. When adding, say whether the term is public or private. Keep each `meaning` to one or two sentences. Do not paste a feature note into the glossary. Do not commit `catalog/glossary.local.yml`.

## What to write

Short notes, in the same PR as the code.

Use `templates/feature-note.md`. Aim for half a page: what it does, where it lives, how to verify. Skip a note for a one-line bugfix. Write an ADR instead of a feature note when the interesting part is the decision, not the behavior.

Do not require a novel on every ticket. People will stop writing, and Copilot will ignore the folder.

## How Copilot should use it

1. Vague prompt → `goat context` → read Graphify reports **and** `knowledge.files`.
2. Unknown jargon → `goat glossary get TERM` (or `search`). Do not guess team language.
3. After a feature change → update or add `docs/features/<slug>.md` in that sibling.
4. Next Graphify extract in that repo picks up the new markdown.

Confluence (or any company wiki) is optional later, and only if the **product spec** already lives there. Implementation knowledge still belongs next to the code.

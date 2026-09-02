---
name: prepare-jira
description: Walk the user through drafting a Jira ticket from dumped notes, format it with templates/jira-ticket.md, and write a copy-paste file under jira-tickets/. Use when they say /prepare-jira, draft a ticket, write a Jira description, or dump feature context to format. Do not call Jira write APIs, read .env, or implement the feature.
argument-hint: paste notes, Figma links, or a one-line ask
---

# Prepare a Jira ticket

This is **not** `goat prepare` (fetch an existing key). This skill turns messy notes into the description shape `prepare` and the planner already consume. The Jira CLI is read-only — never create or update the issue in Jira.

Drafts live in this goat (`jira-tickets/`), not in product repos. They are gitignored, same idea as `plans/`.

## Where drafts live

| What | Rule |
| --- | --- |
| Directory | `jira-tickets/` at the goat root. Never inside a sibling clone. |
| Filename | `jira-tickets/<YYYY-MM-DD>-<slug>.md` (lowercase hyphen slug, e.g. `jira-tickets/2026-09-02-checkout-declined-card.md`) |
| Template | Start from `templates/jira-ticket.md`. Keep every description heading. |
| Git | Gitignored by default. Do not commit a draft unless the user asks. |
| One draft per ask | Revise the existing file as they add detail. Do not fork `-v2` copies. |

If they already have a key they will paste into, include it in the slug (`2026-09-02-shop-1234-declined-card.md`).

## Interview, then format

If they dumped enough context, **skip the interview** and format immediately. Only ask for gaps that would break `goat prepare` or the planner. Ask the missing items in **one** batched message, not a serial quiz.

Need before writing (do not invent these):

1. **Context** or **Goal** — at least one real paragraph of what is true today / what must be true.
2. **Acceptance Criteria** — at least one `- [ ]` checkbox that is an observable fact. No "as discussed", no "etc."
3. **Out of scope** — a short list, or the word `None`.

Ask only if missing or unlabeled:

- **Surfaces** — product areas (checkout page, cart API). Used for routing keywords. Not clone folder names.
- **Constraints** — testable NFRs, or `None`.
- **Verification** — human / product checks, not `pnpm test`.
- **Figma** — if they pasted URLs without a **Role** and **Context**, ask for those. If they pasted a page link, ask for frame URLs (`?node-id=`).
- **Related keys / Bruno** — optional pointers.

Read `catalog/stack.yaml` `workspaces[].match` and suggest **labels** and **components** that fit the surfaces. Do not list `repositories.yml` folder names as the work.

Do not invent acceptance criteria, Figma URLs, or related issue keys. If a section is unknown, write `None` (or omit Figma blocks) after they said so.

## Write the draft

Keep every description heading from `templates/jira-ticket.md`:

`## Context` · `## Goal` · `## Surfaces` · `## Acceptance Criteria` · `## Out of scope` · `## Constraints` · `## Verification` · `## Pointers` · `### Figma frames`

Rules that `done.py` / `prepare` already enforce:

- `- [ ]` **only** under `## Acceptance Criteria`. Goat lifts every checkbox in the description into `done_when`.
- That section is checkboxes only — no leftover prose.
- Figma states are **Role** / **Frame** / **Context** blocks (see the filled example in the template). `figma images` returns `{id, url}` only.
- Do not prescribe file paths or implementation steps.

File shape:

```markdown
# Draft: <short name>

- Written: YYYY-MM-DD
- Suggested summary: <one line, product outcome + a routing word>
- Suggested labels: <from catalog match, comma-separated>
- Suggested components: <from catalog match, or None>
- Related: <keys or None>

## Description

## Context
…

## Goal
…

## Surfaces
…

## Acceptance Criteria
- [ ] …

## Out of scope
…

## Constraints
…

## Verification
…

## Pointers
…

### Figma frames
- **Role:** …
  **Frame:** …
  **Context:** …
```

## After writing

1. Tell them the relative path (`jira-tickets/…`) and that it is gitignored.
2. In chat, print three copy-paste blocks so a small model / the user can drop them into Jira without opening the file:
   - **Summary**
   - **Labels** (and components if any)
   - **Description** (from `## Context` through the end — the body only, no `# Draft` header)
3. Remind them to paste into Jira themselves. The CLI cannot update a ticket. After the issue exists, `/jira-ticket PROJ-123` is the planning path.
4. Do not start `/goat-plan` or implement unless they ask.

## Hard rules

- No secrets: never write `.env` values, tokens, or credentials into the draft.
- Do not curl Jira, call a Jira MCP, or use a write API. `goat jira` is fetch-only.
- Do not read `.env` or print tokens.
- Do not nest clones inside the goat.
- Do not name sibling clone folders as the work — Surfaces + labels only.

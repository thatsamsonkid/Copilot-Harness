---
name: prepare-jira
description: Walk the user through drafting a Jira ticket from dumped notes. Resolve templates/jira/local/<type>.md, then templates/jira/<type>.md, else templates/jira-ticket.md, and write a copy-paste file under jira-tickets/. Use when they say /prepare-jira, draft a ticket, write a Jira description, or dump feature context to format. Do not call Jira write APIs, read .env, or implement the feature.
argument-hint: paste notes, Figma links, or a one-line ask
disable-model-invocation: true
---

# Prepare a Jira ticket

This is **not** `goat prepare` (fetch an existing key). This skill turns messy notes into the description shape `prepare` and the planner already consume. The Jira CLI is read-only — never create or update the issue in Jira.

Drafts live in this goat (`jira-tickets/`), not in product repos. They are gitignored, same idea as `plans/`.

## Where drafts live

| What | Rule |
| --- | --- |
| Directory | `jira-tickets/` at the goat root. Never inside a sibling clone. |
| Filename | `jira-tickets/<YYYY-MM-DD>-<slug>.md` (lowercase hyphen slug, e.g. `jira-tickets/2026-09-02-checkout-declined-card.md`) |
| Template | One file from the resolution order below. Keep every description heading it has. |
| Git | Gitignored by default. Do not commit a draft unless the user asks. |
| One draft per ask | Revise the existing file as they add detail. Do not fork `-v2` copies. |

If they already have a key they will paste into, include it in the slug (`2026-09-02-shop-1234-declined-card.md`).

## Which template

Team files live in `templates/jira/` (`story.md`, `bug.md`, `spike.md`). Personal overrides live in `templates/jira/local/` (gitignored except `.gitkeep`).

Resolution order. Open the first file that exists:

1. `templates/jira/local/<type>.md`
2. `templates/jira/<type>.md`
3. `templates/jira-ticket.md`

`<type>` is a filename stem from the table, or the stem of a file the user added under `templates/jira/local/`. A new file there adds a type: `templates/jira/local/incident.md` is Incident. A local `story.md` replaces `templates/jira/story.md`. Task, Sub-task, and Epic do not use a stem; they always use the fallback `templates/jira-ticket.md`. If a stem is missing in both directories, use that same fallback.

| Issue type (case-insensitive) | Stem |
| --- | --- |
| Story, User Story | `story` |
| Bug, Defect | `bug` |
| Spike, Research | `spike` |
| Task, Sub-task, Subtask, Epic | fallback file above (do not look up `task.md`) |
| Any other name | that name lowercased; spaces become hyphens (`Service Request` → `service-request`) |

State the path you opened in chat and on the draft header (`- Template:`).

Warn if that file has no recognised acceptance heading, or has checkboxes outside it. Recognised headings (the set `done.py` uses): `Acceptance Criteria`, `Definition of Done`, `Done when`, `AC`. A checkbox is a line whose list marker is followed by `[ ]` or `[x]`. Those lines must appear only under that heading. Goat lifts every checkbox in the description into `done_when`. Name the file and which problem you found. Do not silently move checkboxes.

How to pick the type:

- From the notes when they name one (story, bug, spike, incident, …).
- If they gave an existing key and the notes do not name a type, run `uv run goat jira get <KEY> --format json` and read `issue_type`. `--format` is a shared flag (default `json`; `docs/cli.md`). You need `issue_type` only. Never print tokens or `.env`.
- If there is no key and the notes do not name a type, ask for the type in the **one** batched question below. Do not add a second message.

Never list issue types from Jira. Do not call a command to enumerate them, and do not invent a type catalog from the project. The table plus filenames in `templates/jira/local/` are the source.

## Interview, then format

If they dumped enough context, **skip the interview** and format immediately. Only ask for gaps that would break `goat prepare` or the planner. Ask the missing items in **one** batched message, not a serial quiz. The issue type, when still unknown, belongs in that same message.

Need before writing (do not invent these):

1. **Context** or **Goal** — at least one real paragraph of what is true today / what must be true. A spike also needs **Question** and **Timebox** when those headings are in the template.
2. **Acceptance heading** — at least one `- [ ]` checkbox that is an observable fact (a spike: a deliverable). No "as discussed", no "etc."
3. **Out of scope** — a short list, or the word `None`.

Ask only if missing or unlabeled, and only when the chosen template has that heading:

- **Surfaces** — product areas (checkout page, cart API). Used for routing keywords. Not clone folder names.
- **Constraints** — testable NFRs, or `None`.
- **Verification** — human / product checks, not `pnpm test`.
- **Figma** — story and bug only (`### Figma frames`). If they pasted URLs without a **Role** and **Context**, ask for those. If they pasted a page link, ask for frame URLs (`?node-id=`). Do not add this section to a spike.
- **Steps to reproduce** — bug only. Numbered steps (`1.` `2.` `3.`). Not checkboxes.
- **Expected vs actual** and **Environment** — bug only.
- **Related keys / Bruno** — optional pointers.

Read `catalog/stack.yaml` `workspaces[].match` and suggest **labels** and **components** that fit the surfaces. Do not list `repositories.yml` folder names as the work.

Do not invent acceptance criteria, Figma URLs, or related issue keys. If a section is unknown, write `None` (or omit Figma blocks) after they said so.

## Write the draft

Keep every description heading from the template file you resolved. Do not drop a heading that file has, and do not add a heading it does not have.

Rules that `done.py` / `prepare` already enforce:

- `- [ ]` **only** under the acceptance heading (`## Acceptance Criteria`, `## Definition of Done`, `## Done when`, or `## AC`). Goat lifts every checkbox in the description into `done_when`.
- That section is checkboxes only — no leftover prose.
- Bug **Steps to reproduce** stay a numbered list. Numbered lines are not checkboxes.
- Figma states are **Role** / **Frame** / **Context** blocks when the template has `### Figma frames` (story and bug). `figma images` returns `{id, url}` only.
- Do not prescribe file paths or implementation steps.

File shape (description headings come from the template; this header is always the same):

```markdown
# Draft: <short name>

- Written: YYYY-MM-DD
- Type: <issue type name>
- Template: <path you opened>
- Suggested summary: <one line, product outcome + a routing word>
- Suggested labels: <from catalog match, comma-separated>
- Suggested components: <from catalog match, or None>
- Related: <keys or None>

## Description

<every heading from the template, filled from the notes>
```

## After writing

1. Tell them the relative path (`jira-tickets/…`), the template path (same value as `- Template:`), and that the draft is gitignored.
2. If the chosen template has no recognised acceptance heading, or has checkboxes outside it, repeat that warning here.
3. In chat, print three copy-paste blocks so a small model / the user can drop them into Jira without opening the file:
   - **Summary**
   - **Labels** (and components if any)
   - **Description** (from the first description heading through the end — the body only, no `# Draft` header)
4. Remind them to paste into Jira themselves. The CLI cannot update a ticket. After the issue exists, `/jira-ticket PROJ-123` is the planning path.
5. Do not start `/goat-plan`, `/goat-implement`, or implement unless they ask.

## Hard rules

- No secrets: never write `.env` values, tokens, or credentials into the draft.
- Do not curl Jira, call a Jira MCP, or use a write API. `goat jira` is fetch-only. `jira get` is only how you read `issue_type` when a key is already known.
- Do not read `.env` or print tokens.
- Do not nest clones inside the goat.
- Do not name sibling clone folders as the work — Surfaces + labels only.

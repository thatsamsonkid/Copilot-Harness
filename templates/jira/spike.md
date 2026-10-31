# Spike

Typed description for a Jira **Spike** (alias: Research). `/prepare-jira` fills these headings into `jira-tickets/<date>-<slug>.md`. A file at `templates/jira/local/spike.md` replaces this one. Task, epic, and unknown types stay on `templates/jira-ticket.md`.

`goat prepare` parses `## Done when` (also `Acceptance Criteria`, `Definition of Done`, or `AC`) into `done_when`. Checkboxes belong only in that section. They are deliverables, not product behavior. Goat lifts every checkbox in the description into the stop list. One deliverable each. No "as discussed", no "etc.", no leftover prose in that section.

This template has no Figma frames section. Do not add one here.

Do not list clone folder names. Workspace routing uses **summary keywords**, **labels**, and **components** from `catalog/stack.yaml`. Repos and lint/test commands are attached by `prepare`, not by this ticket.

Leave file maps and implementation steps out. The spike answers a question; it does not ship the change.

Copy everything below this line into the Jira **Description**. Keep the headings.

## Context

What is unknown today, and why a story or bug cannot be planned until it is answered. One paragraph. No implementation.

Checkout can show a declined card as a blank page or as an inline error. Design and the cart API disagree, and a story would guess.

## Question

The single question this spike answers. One or two sentences.

Which declined-card treatment should web checkout ship: inline error with the cart unchanged, or a full-page error with a retry link?

## Goal

What must be true when the timebox ends, in 2–3 sentences. A written answer, not the feature.

The ticket has a written recommendation, the options that were rejected, and the follow-up story or bug to open. No product code is changed.

## Timebox

One focused session. Stop when the question is answered or the box ends, whichever comes first.

## Surfaces

Shop checkout page; cart API.

Product areas the question is about. Not repo folder names. Used for routing keywords only.

## Done when

- [ ] The question is answered in a short note on the ticket
- [ ] The note names one option to pursue and the options rejected
- [ ] Any follow-up story or bug is named, not started

## Out of scope

- Implementing the chosen error state
- Mobile app
- Saved payment methods

Name tempting nearby work. Anything listed here must not be planned.

## Verification

- Read the note: it answers the question, names the rejected options, and points at a follow-up key or a "not yet filed" line
- Confirm no product change shipped under this spike

Product / human checks only. Do not paste `pnpm test` — `prepare` already appends each repo's `tooling.suggested_verify`.

## Pointers

- Related: SHOP-1201 (story blocked on this answer)
- Bruno: `cart-api` / `pay-order` (`--env` staging) if a sample decline response would settle the question

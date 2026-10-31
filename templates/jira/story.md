# Story

Typed description for a Jira **Story** (alias: User Story). `/prepare-jira` fills these headings into `jira-tickets/<date>-<slug>.md`. A file at `templates/jira/local/story.md` replaces this one. Task, epic, and unknown types stay on `templates/jira-ticket.md`.

`goat prepare` parses the acceptance heading (`Acceptance Criteria`, `Definition of Done`, `Done when`, or `AC`) into `done_when`. Checkboxes belong only in that section. Goat lifts every checkbox in the description into the stop list. One observable fact each. No "as discussed", no "etc.", no leftover prose in that section.

Do not list clone folder names. Workspace routing uses **summary keywords**, **labels**, and **components** from `catalog/stack.yaml`. Repos and lint/test commands are attached by `prepare`, not by this ticket.

Leave file maps and implementation steps out. That is the planner's job after it reads the sibling repos.

Copy everything below this line into the Jira **Description**. Keep the headings.

## Context

What is true today, who feels the pain, and why this story exists. One paragraph. No implementation.

Guests who decline a card see a blank page, so they abandon the cart instead of retrying.

## Goal

What must be true when this ships, in 2–3 sentences. Restate the ask so a model that never saw Slack can plan.

A guest can pay without an account. A declined card shows an inline error and leaves the cart unchanged. A successful payment shows the order confirmation.

## Surfaces

Shop checkout page; cart API; receipt email.

Product areas and routing keywords. Not repo folder names.

## Acceptance Criteria

- [ ] Guest can complete payment without an account
- [ ] Receipt email is sent within 1 minute of success
- [ ] Failed card shows the inline error, not a blank page

## Out of scope

- Saved payment methods
- Admin refunds
- Mobile app (web only)

Name tempting nearby work. Anything listed here must not be planned.

## Constraints

- Keep the existing cart API contract unless a breaking change is called out here
- p95 checkout submit < 400ms on staging
- WCAG 2.2 AA for the new error state

Non-functional requirements. Keep them testable.

## Verification

- Happy path: guest card success → order confirmation + email
- Failure path: declined card → inline error, cart unchanged

Product / human checks only. Do not paste `pnpm test` — `prepare` already appends each repo's `tooling.suggested_verify`.

## Pointers

- Related: SHOP-1201 (parent), SHOP-1188 (blocks)
- Bruno: `cart-api` / `pay-order` (`--env` staging)

### Figma frames

`goat figma images` returns `{id, url}` only — **no frame names**. Label every linked node with **Role**, **Frame**, and **Context**. Link the frame (`?node-id=`), not the page. One block per state. Stay under `figma.max_ids` (12).

Name the frames in Figma the same way (`Checkout / Success`) so designers stay aligned. Frames may live in different files; still give each one its own block.

Blank shape (copy, then fill):

- **Role:** default | loading | success | error | empty | …
  **Frame:** https://www.figma.com/design/FILE/Name?node-id=12-34
  **Context:** When this state is shown, and what in the image must be true (copy, enabled/disabled, what replaced what).

Example:

- **Role:** default
  **Frame:** https://www.figma.com/design/AbCdEfGh/Checkout?node-id=12-34
  **Context:** Guest checkout, first visit. Promo field empty. Pay is enabled. No banner. This is the screen before submit.

- **Role:** error / declined
  **Frame:** https://www.figma.com/design/XyZ999aa/Checkout-errors?node-id=4-12
  **Context:** Card declined. Inline error under the card number: "Card declined. Try another card." Pay stays enabled. Totals unchanged.

Do not dump a whole page or file. Do not run `figma nodes` on a page — only on a small targeted control (a button, input, chip).

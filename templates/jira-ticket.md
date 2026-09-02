# Jira ticket (LLM planning)

Copy the **Description** body into the Jira issue. Keep the headings.
`goat prepare` parses `## Acceptance Criteria` (also `Definition of Done`, `Done when`, or `AC`) into `done_when`. Use `- [ ]` **only** under that heading — Goat lifts every checkbox in the description into the stop list. Keep that section as checkboxes only: one observable fact each, no "as discussed", no "etc.", no leftover prose.

Do not list clone folder names. Workspace routing uses **summary keywords**, **labels**, and **components** from `catalog/stack.yaml`. Repos and lint/test commands are attached by `prepare`, not by this ticket.

## Jira fields (not the description)

| Field | What to put |
| --- | --- |
| Summary | Product outcome plus a routing word: `Checkout: show declined-card error on the pay button` |
| Labels / components | Values that match a workspace `match` block (`frontend`, `api`, `mobile`, …) |
| Parent / links | Related tickets. They already flow through `issuelinks` |

Leave file maps and implementation steps out. That is the planner's job after it reads the sibling repos.

Copy everything below this line into the Jira **Description**. Keep the headings.

## Context

What is true today, who feels the pain, and why this change exists. One paragraph. No implementation.

## Goal

What must be true when this ships, in 2–3 sentences. Restate the ask so a model that never saw Slack can plan.

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

Name the frames in Figma the same way (`Checkout / Success`) so designers stay aligned. A pinned Figma comment that restates the role is optional. Frames may live in different files; still give each one its own block.

Blank shape (copy, then fill):

- **Role:** default | loading | success | error | empty | …
  **Frame:** https://www.figma.com/design/FILE/Name?node-id=12-34
  **Context:** When this state is shown, and what in the image must be true (copy, enabled/disabled, what replaced what).

Example with several frames (two files):

- **Role:** default
  **Frame:** https://www.figma.com/design/AbCdEfGh/Checkout?node-id=12-34
  **Context:** Guest checkout, first visit. Promo field empty. Pay is enabled. No banner. This is the screen before submit.

- **Role:** loading
  **Frame:** https://www.figma.com/design/AbCdEfGh/Checkout?node-id=12-56
  **Context:** User tapped Pay. Same form, fields still filled. Button shows a spinner and is disabled. Do not navigate away.

- **Role:** success
  **Frame:** https://www.figma.com/design/AbCdEfGh/Checkout?node-id=12-78
  **Context:** Payment accepted. Pay form is gone. Confirmation shows order number, email, and "Continue shopping". Not a toast on the pay form.

- **Role:** error / declined
  **Frame:** https://www.figma.com/design/XyZ999aa/Checkout-errors?node-id=4-12
  **Context:** Different file (error explorations). Card declined. Inline error under the card number: "Card declined. Try another card." Pay stays enabled. Totals unchanged.

- **Role:** empty
  **Frame:** https://www.figma.com/design/AbCdEfGh/Checkout?node-id=12-12
  **Context:** No line items. Hide the pay form. Show "Your cart is empty" and a catalog CTA.

Do not dump a whole page or file. Do not run `figma nodes` on a page — only on a small targeted control (a button, input, chip).

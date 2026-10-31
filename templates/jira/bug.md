# Bug

Typed description for a Jira **Bug** (alias: Defect). `/prepare-jira` fills these headings into `jira-tickets/<date>-<slug>.md`. A file at `templates/jira/local/bug.md` replaces this one. Task, epic, and unknown types stay on `templates/jira-ticket.md`.

`goat prepare` parses the acceptance heading (`Acceptance Criteria`, `Definition of Done`, `Done when`, or `AC`) into `done_when`. Checkboxes belong only in that section. Goat lifts every checkbox in the description into the stop list. One observable fact each. No "as discussed", no "etc.", no leftover prose in that section.

**Steps to reproduce** stay a numbered list. Numbered lines are not checkboxes, and they must not become checkboxes.

Do not list clone folder names. Workspace routing uses **summary keywords**, **labels**, and **components** from `catalog/stack.yaml`. Repos and lint/test commands are attached by `prepare`, not by this ticket.

Leave file maps and implementation steps out. That is the planner's job after it reads the sibling repos.

Copy everything below this line into the Jira **Description**. Keep the headings.

## Context

What is broken today, who hits it, and why it is a defect rather than new scope. One paragraph. No implementation.

A guest who submits a declined card on web checkout gets a blank page. The cart is cleared. Refreshing does not bring the line items back.

## Goal

What must be true when the fix ships, in 2–3 sentences.

A declined card shows the inline error and leaves the cart unchanged. A successful card still reaches order confirmation. The blank page is gone for this decline.

## Surfaces

Shop checkout page; cart API.

Product areas and routing keywords. Not repo folder names.

## Steps to reproduce

1. Open guest checkout in Chrome on staging with one item in the cart.
2. Enter a card the processor declines.
3. Submit payment.

Number these steps in order. Do not turn them into checkboxes.

## Expected vs actual

- **Expected:** Inline error under the card number. Cart and totals stay as they were. Pay stays enabled.
- **Actual:** Blank page. Cart is empty after refresh.

## Environment

- Web checkout, Chrome, staging
- Account: guest (no saved card)
- Not the mobile app

## Acceptance Criteria

- [ ] Declined card shows the inline error and leaves the cart unchanged
- [ ] Successful card still reaches order confirmation
- [ ] The blank page no longer appears for this decline

## Out of scope

- Saved payment methods
- Admin refunds
- Other payment errors (insufficient funds, 3-D Secure)

Name tempting nearby work. Anything listed here must not be planned.

## Constraints

- Keep the existing cart API contract unless a breaking change is called out here
- Do not change the success-path copy

Non-functional requirements. Keep them testable.

## Verification

- Failure path: declined card → inline error, cart unchanged, no blank page
- Happy path: guest card success → order confirmation (unchanged)

Product / human checks only. Do not paste `pnpm test` — `prepare` already appends each repo's `tooling.suggested_verify`.

## Pointers

- Related: SHOP-1188 (the story this regresses)
- Bruno: `cart-api` / `pay-order` (`--env` staging)

### Figma frames

`goat figma images` returns `{id, url}` only — **no frame names**. Label every linked node with **Role**, **Frame**, and **Context**. Link the frame (`?node-id=`), not the page. One block per state. Stay under `figma.max_ids` (12).

Blank shape (copy, then fill):

- **Role:** default | loading | success | error | empty | …
  **Frame:** https://www.figma.com/design/FILE/Name?node-id=12-34
  **Context:** When this state is shown, and what in the image must be true.

Example:

- **Role:** error / declined
  **Frame:** https://www.figma.com/design/XyZ999aa/Checkout-errors?node-id=4-12
  **Context:** Card declined. Inline error under the card number: "Card declined. Try another card." Pay stays enabled. Totals unchanged. This is the expected state.

- **Role:** empty
  **Frame:** https://www.figma.com/design/AbCdEfGh/Checkout?node-id=12-12
  **Context:** Wrong outcome for this bug. Cart emptied and the pay form is gone. The fix must not land here after a decline.

Do not dump a whole page or file. Do not run `figma nodes` on a page — only on a small targeted control (a button, input, chip).

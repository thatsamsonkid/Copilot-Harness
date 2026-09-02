---
name: prepare-jira
description: Walk through drafting a Jira ticket from dumped notes and write a copy-paste file under jira-tickets/
argument-hint: paste notes, Figma links, or a one-line ask
agent: agent
---

The user wants a Jira ticket drafted from notes (or a walkthrough of the missing pieces), formatted for easy paste into Jira. Load `.github/skills/prepare-jira/SKILL.md` and follow it. Start from `templates/jira-ticket.md`.

This is **not** `goat prepare` and **not** `/jira-ticket`. Do not fetch or write Jira. The CLI cannot create or update issues.

1. If they already dumped context in `${input:notes:Notes, Figma links, or a one-line ask}`, use it. Only ask for gaps that would break `prepare` / the planner (Context or Goal, at least one observable Acceptance Criteria checkbox, Out of scope or `None`). Ask those gaps in one batched message.
2. Suggest labels/components from `catalog/stack.yaml` `workspaces[].match`. Do not list clone folder names.
3. If they pasted Figma URLs without a Role and Context, ask. Format frames as **Role** / **Frame** / **Context** blocks. Link frames (`?node-id=`), not pages.
4. Write `jira-tickets/<YYYY-MM-DD>-<slug>.md`. Keep every description heading from the template. Checkboxes only under `## Acceptance Criteria`.
5. Tell them the relative path (gitignored). In chat, print copy-paste blocks for Summary, Labels, and Description (body only).
6. Remind them to paste into Jira themselves. After the issue exists they can run `/jira-ticket PROJ-123`.

Do not implement. Do not call Jira write APIs. Do not read `.env` or print tokens.

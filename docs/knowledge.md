# Product knowledge

Yes, we should write down features and decisions as people build them. No, that knowledge should not live in this harness.

A central wiki here would be a third source of truth (code, Jira, harness docs). It will rot, and Copilot will start trusting a stale copy over the repo that actually changed.

## Where knowledge lives

| Kind | Put it here | When |
| --- | --- | --- |
| How a feature works today | `<repo>/docs/features/<slug>.md` | User-visible or non-obvious behavior |
| Why we chose A over B | `<repo>/docs/adr/` or `docs/decisions/` | A real alternative was rejected |
| How the code is shaped | Graphify `graphify-out/` plus `# WHY:` / `# NOTE:` comments | Always; Graphify already indexes these |
| Ticket intent | Jira, via `harness prepare` | The work item, not the architecture |

The harness only **discovers** those files (`harness context` → `knowledge`). It does not store product facts. If a monorepo keeps notes somewhere else, set `knowledge.dirs` on that `repositories.yml` entry.

## What to write

Short notes, in the same PR as the code.

Use `templates/feature-note.md`. Aim for half a page: what it does, where it lives, how to verify. Skip a note for a one-line bugfix. Write an ADR instead of a feature note when the interesting part is the decision, not the behavior.

Do not require a novel on every ticket. People will stop writing, and Copilot will ignore the folder.

## How Copilot should use it

1. Vague prompt → `harness context` → read Graphify reports **and** `knowledge.files`.
2. After a feature change → update or add `docs/features/<slug>.md` in that sibling.
3. Next Graphify extract in that repo picks up the new markdown.

Confluence (or any company wiki) is optional later, and only if the **product spec** already lives there. Implementation knowledge still belongs next to the code.

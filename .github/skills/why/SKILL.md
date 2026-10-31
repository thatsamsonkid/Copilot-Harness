---
name: why
description: Explain why code is shaped this way, using git history, decision notes, and tickets.
argument-hint: decision or regression
disable-model-invocation: true
---

# Why

Explain what forces led to this shape. `/how` answers what the code does. This skill answers why it is that way. Be careful about what the record says and what you are inferring.

Do the code anchor and the investigation in this chat. Bulk Reader has no shell, so do not send this work to it. Do not discover external evidence servers, and do not spawn parallel investigators.

If you were started as a subagent other than Orchestrator, do every read yourself and do not invoke Bulk Reader. Only the hidden Orchestrator may delegate while it is a subagent.

Do not read `.env`, print a token, or ask anyone to paste a token. Do not clone a repo into this goat folder. Do not invent a command or flag. The catalog is `docs/cli.md`.

If the target is vague, say what you think it refers to, then proceed.

## Confidence

Every claim sits in one tier. The tier picks the section and the wording.

- **Direct.** An author wrote the reason (a commit message, a PR body, a ticket, an ADR, a code comment). Cite it. "This exists because X."
- **Supported.** Several indirect items converge, and none states it alone. Cite each. "The evidence points to X."
- **Inferred.** Your reading, not a fact in the record. Hedge it. "Given A and B, C seems likely because D."
- **Speculative.** Another story fits as well. "One possibility is X, but there is no direct evidence." These go in Competing Hypotheses.
- **Unknown.** You looked and did not find it. Name what you searched.

What We Found holds Direct and Supported claims only. What We Can Reasonably Infer holds Inferred claims only. Do not use "because", "the reason is", or "the team decided" on an inference.

Do not cite the code as evidence of its own intent. Do not treat the newest commit as the whole reason. Do not confirm a hypothesis the user embedded in the question until the record supports it. Do not turn a missing source into "they did not care." A contradiction stays a contradiction. Show both sides.

## Code anchor

Build this before you conclude. File paths and line ranges, the key symbols, and the commits that touched them.

```bash
git log --follow -- <file>
git blame -L <start>,<end> <file>
git log -1 --format=%B <commit>
```

`git log --follow` is the history through renames. `git blame -L` is who last touched the lines. `git log -1 --format=%B` is the full message of a commit you cite. Read PR numbers out of those subjects, such as `(#1234)`.

If `gh` is on PATH, run `gh pr view <number>` for each of those PRs. If `gh` is missing, write that pull-request bodies were not read. Do not describe them as searched.

ADRs and feature notes: run `uv run goat context --format json` and read the paths under `knowledge.files` (`docs/knowledge.md`). When the question names two repos or two concepts, run `uv run goat graph explain`, `goat graph path`, or `goat graph neighbors` and read nodes of type `adr` (`docs/workspace-graph.md`). If the graph is not built yet, run `uv run goat graph build` first.

Tickets: when an issue key appears in the question, a commit message, or a PR body, run `uv run goat jira context ISSUE`. If no key appears, say the issue tracker was not queried. Do not invent a search that did not happen.

## What to hand back

### The Question

The user's question in one or two sentences.

### The Code in Question

Paths, line ranges, and key symbols. Two or three lines.

### What We Found

Direct and Supported claims, each cited (commit, PR, ticket, file:line, or note). Quote or paraphrase the source.

### What We Can Reasonably Infer

Inferred claims only, hedged, with the chain visible. Omit this section when there is nothing to infer.

### Competing Hypotheses

Stories the record does not decide between. For each: the hypothesis, the evidence for it, and the evidence against it or missing. Omit this section when one account is clear.

### What We Don't Know

The gaps, named. What you searched, what was not queried, and who would know.

### Sources Consulted

One line per category. Say what was actually searched.

- **Source control:** the files, the commits you opened, and any PRs whose bodies you read. Or that `gh` was missing and pull-request bodies were not read.
- **Issue tracker:** the keys passed to `goat jira context`. Or that no issue key was in the anchor, so Jira was not queried.
- **In-repo notes:** the `knowledge.files` paths and any `adr` nodes you opened.

These five have no source in this harness. Write each as skipped. Do not imply they were searched, empty, or unavailable after a query:

- **Real-time team chat:** skipped. No chat source in this harness.
- **Docs platforms:** skipped. No Notion, Confluence, or similar source in this harness. In-repo ADRs and feature notes are not this category.
- **Infrastructure observability:** skipped. No observability source in this harness.
- **Error and exception tracking:** skipped. No error-tracker source in this harness. Defensive code does not add this search.
- **Product analytics:** skipped. No analytics source in this harness.

### Confidence Summary

One or two sentences. What is direct, what is inferred, and what is unknown.

When the user plans a change, add a constraint set after Sources Consulted:

- **Preserve.** What the record says must stay.
- **Change.** What the evidence supports changing.
- **Avoid.** Alternatives the record rejected.
- **Risk.** Gaps and contradictions a change could get wrong.

Code-change judgment stays in `.github/instructions/engineering-principles.instructions.md`. This skill investigates. It does not implement.

Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md

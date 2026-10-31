---
name: how
description: Explain how a subsystem works, including its flow, where it lives, and which package owns it.
argument-hint: subsystem, flow, or placement
disable-model-invocation: true
---

# How

Explain how something works. The reader should leave with a working mental model of the flow, the main types, and where the code lives. A motivation question ("why is it this way") is `/why`.

Where to look is `/orient` (`.github/skills/orient/SKILL.md`). This skill does not repeat those steps. It answers the mechanism.

Do this in this chat. Do not read `.env`, print a token, or ask anyone to paste a token. Do not clone a repo into this goat folder. Do not invent a command or flag. The catalog is `docs/cli.md`.

## Who reads

If you were started as a subagent other than Orchestrator, do every read yourself and do not invoke Bulk Reader. Only the hidden Orchestrator may delegate while it is a subagent. Bulk Reader never delegates.

## Knowledge before code

Run these before any code search. From this Goat repo. Do not `cd` into a sibling first. If cwd is already a product clone, use `uv run --project "$GOAT_ROOT" goat context --format json`.

1. Run `uv run goat context --format json`. Read `instructions` and `knowledge.files` (feature notes and ADRs, per `docs/knowledge.md`). Stay inside `workspace.repos`.
2. For an unfamiliar workplace word, run `uv run goat glossary get TERM`. Do not guess team language.
3. When the question names two repos or two concepts, run `uv run goat graph explain`, `goat graph path`, or `goat graph neighbors` (`docs/workspace-graph.md`). That is the cross-repo link, including `adr` nodes. If the graph is not built yet, run `uv run goat graph build` first.

Then find the code: `search/codebase` for candidate code, `search/usages` on the named symbol, then a targeted `Read` (`limit` / `offset`). Text search is for strings and config only.

## Simple or complex

State your interpretation when the scope is ambiguous, then continue. The user can redirect. When in doubt, take the simple path.

- **Simple.** One module, one function, or a narrow question. This chat reads the code itself. Do not call Bulk Reader.
- **Complex.** A subsystem across files or services. Split it into 2 to 4 angles, one distinct slice each. In a single message, invoke up to 4 parallel **Bulk Reader** calls (`.github/skills/bulk-reader/SKILL.md`), one per angle, with `#tool:agent`. The name is case-sensitive. Its profile pins Copilot Auto (`Auto (copilot)`). Do not override the model. Each call is stateless: pass the angle, the paths or symbols, and what to skip. Stay inside `workspace.repos`.

Ask Bulk Reader only for components, flow hops, and boundaries, as `path:line` bullets. Do not ask it to explain architecture. `.github/agents/bulk-reader.agent.md` forbids that. It reports locations only.

When the calls return, re-read the key slices yourself with a targeted `Read` (`limit` / `offset`). Write the explanation in this chat. The bullets are a map, not the answer.

## What to hand back

Use these sections. Drop a section that does not apply. Prose, not a source dump. Name the file and the function. Say what you could not trace.

### Overview

One or two paragraphs. What it is, what it does, and why it exists. A reader can stop here.

### Key Concepts

The types, services, or abstractions needed to follow the rest. Short definitions.

### How It Works

The flow: what starts it, what happens step by step, where the data goes, and the decision points. This is the longest section. A mermaid diagram belongs here when several components talk to each other. Skip the diagram when prose is enough.

### Where Things Live

The files someone needs to start working here, which package owns them, and which layer they sit in now. Describe the current layout. Do not ask Bulk Reader to pick a new design.

### Gotchas

Non-obvious behavior, surprising edges, and history that changes how you read the code. Omit this section when there is nothing to say.

Code-change judgment stays in `.github/instructions/engineering-principles.instructions.md`. This skill explains. It does not implement.

Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md

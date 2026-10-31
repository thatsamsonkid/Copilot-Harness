---
name: blast-radius
description: "Find what a change could break somewhere else before it ships, beyond the diff, and prove the one fact it's safe because of by running real code instead of writing it up. Use for 'blast radius of X', 'what could this break', or reviewing a small diff you don't trust."
argument-hint: change, symbol, or diff
disable-model-invocation: true
---

# Blast radius

Find what a change breaks somewhere else, before it ships. Use for "blast radius of X", "what could this break", or a small diff you don't trust yet.

Listing the callers is not the job. `search/usages` lists those. The job is the breakage a search will not show.

A full `done_when` review is `/review` and `.github/agents/reviewer.agent.md`. This skill is the breakage check.

Do this as one pass in this chat. Do not ask a second model the same question and merge the answers. Safety analysis stays here: do not send it to Bulk Reader (`.github/skills/bulk-reader/SKILL.md`). Do not read `.env`, print a token, or ask anyone to paste a token. Do not clone a repo into this goat folder. The command catalog is `docs/cli.md`. Do not invent a command or flag.

## Don't trust your own writeup

A blast-radius writeup that sounds right is worthless. It reads as convincing whether or not it's true. Find the one or two facts the whole thing depends on and prove them by running code.

### How sure are you

For each fact the change's safety depends on, get it as far down this list as is cheap, and say where it stopped.

1. You said so. Worthless on its own.
2. You pointed at the line. A real `file:line`, or the library's own source.
3. You showed the bad case can't happen. You walked the failure step by step and it doesn't reach.
4. You ran it. A script or test that calls the real code and fails loud if you're wrong.
5. You reproduced it in the running app.

Step 4 is usually one small script or test that imports the same library the app ships and calls the exact function you're worried about.

## Steps

1. Read the change. Run `uv run goat status --format json` from this Goat repo. Read the diff, the symbols it adds, changes, and deletes, and what it now does differently, including the part the diff doesn't spell out. Targeted-`Read` those sections (`limit` / `offset`).
2. Find the one fact it's safe because of. Most changes that look risky are safe because of a single fact, like "this call only drops already-dead cache entries and does nothing else". Find that fact. If it holds, most risky cases are cleared at once. Spend your time here, not on a long list of maybes.
3. Look where search stops. Read the source of the library you call, and check its pinned version and any local patch. Work out when things run: microtasks, unmount and teardown, and which UI runtime. Follow what a symbol search misses: the JSON an API returns, a DB column, a wire format, another language reading the same bytes, a feature flag, code three hops downstream. Use `search/usages` on the named symbol, then a targeted read.
4. Be honest about each risk. Give it a real chance of happening and a real cost if it does. Keep the risks you confirmed. List the ones you checked and cleared separately. Cite a real `file:line`. A search that finds nothing is still an answer. Never make up a caller or an API.
5. Prove the one fact. Run code that calls the real function. Take the command from `tooling.suggested_verify` in `uv run goat context --repo <name> --format json`, or a focused test that repo already knows how to run. When this chat is the primary Implementer, invoke **Verifier** (`.github/agents/verifier.agent.md`) with `#tool:agent` and that command. Otherwise run it here. If you were started as a subagent, run it yourself. Only the hidden Orchestrator may delegate while it is a subagent. Verifier never delegates. `read/problems` is early feedback, not the proof. Paste what happened. Put a regression test in the product repo when that repo already tests this path. Do not leave a scratch script in this goat repo.

## What to hand back

Run the writeup through `.github/skills/unslop/SKILL.md`. Cite real code. Strip anything private before it goes anywhere public.

- **What it does.** What changed, including the part that isn't obvious.
- **The one fact it's safe because of.** State it, say which step you got it to, and show the proof. If you couldn't prove it, write unproven.
- **Risks.** Each names how it breaks, the `file:line`, how likely and how bad, and how to check. Paste the proof for the ones that matter.
- **Cleared.** What you checked and why it's fine.
- **Before you merge.** The cheapest test or repro that catches the real bug, including the command you ran.

Code-change judgment stays in `.github/instructions/engineering-principles.instructions.md`.

**Reply:** the writeup above, with the one safety fact either proven or marked unproven.

Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md

---
name: teach
description: Explain a subsystem in plain language, covering how it works and why it is built that way.
argument-hint: subsystem or change
disable-model-invocation: true
---

# Teach

Explain what a thing is, how it works, and why it is built that way, in one plain account. The person should understand it. Do not change the code.

Do this in this chat. If you were started as a subagent other than Orchestrator, do every read yourself and do not invoke Bulk Reader. Only the hidden Orchestrator may delegate while it is a subagent.

Do not read `.env`, print a token, or ask anyone to paste a token. Do not clone a repo into this goat folder.

## Steps

1. From the conversation, pick the few things they should walk away understanding. Skip what they already know. Do not quiz them.
2. Run `/how` and `/why` yourself in this chat. Load `.github/skills/how/SKILL.md` and follow it, then load `.github/skills/why/SKILL.md` and follow it. Sequential. Do not hand either skill to a subagent. `/how`'s own Bulk Reader survey calls remain allowed under `/how`'s rules, including the subagent rule.
3. Publish one explanation, not the two reports pasted together. Keep the confidence hedges from why. Those hedges are findings. Reword the rest so it teaches.
4. Write that explanation through `/unslop` (`.github/skills/unslop/SKILL.md`).
5. Diagrams are Mermaid only. No image generation. When the picture has three or more parts, draw a short series. Each diagram redraws the last and adds one part. A single diagram of the whole thing is a reference, not teaching. For a flow from A to B to C, draw A to B, then redraw and add C, then redraw and add the return or the next piece.

## How to say it

Start with a plain definition and the common name if it has one. Then the case in front of you, how it works, the reasons, and the edges. For each part, say the problem it solves and the mechanism.

Give the smallest complete answer in a sentence or two, then stop. Add a layer when they ask. Offer to go deeper at the end.

Do not print framing labels ("the one idea to hold onto", "the key insight", "TL;DR", "here is the tricky part"). One name per concept. State the mechanism.

**Reply:** the explanation itself. Lead with the point, then what it is, how it works, and why.

Adapted from pstack (MIT) by Lauren Tan; see THIRD_PARTY_NOTICES.md

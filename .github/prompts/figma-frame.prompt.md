---
name: figma-frame
description: Export a Figma frame image URL and look at the rendered design
argument-hint: https://www.figma.com/design/…
---

The user will provide a Figma file/design/proto URL or a file key as `${input:file:Figma URL or file key}`. Follow `.github/skills/figma-cli/SKILL.md` for CLI rules.

1. From the coboose repo (do not `cd` into a sibling first), run `#tool:runCommands` with cwd = the coboose folder and `uv run coboose figma images ${input:file} --format json`. If cwd is already a product clone, use `uv run --project "$COBOOSE_ROOT" coboose figma images ${input:file} --format json` instead — bare `uv run coboose` cannot spawn there.
2. If `uv` is missing, follow `docs/install-uv.md` for the user's OS (macOS/Linux: `./scripts/setup.sh`; Windows: `.\scripts\setup.ps1`), then retry.
3. Use only that CLI JSON. Do not curl Figma, read `.env`, or call MCP.
4. For each non-null value in `images` (node id → URL), open that URL in VS Code Simple Browser and look at the rendered frame. That image is the visual source of truth.
5. Summarize the visible screen: layout, obvious components, and copy you can actually read. Do not invent spacing or tokens.
6. If an `images` value is `null`, say that node failed.
7. If they want implementation next, write a short plan and stop unless they ask to implement.

Do not download the PNG into a product repo unless they asked. Do not reconstruct the design from JSON.

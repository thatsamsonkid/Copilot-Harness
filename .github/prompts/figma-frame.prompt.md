---
name: figma-frame
description: Export a Figma frame image URL and look at the rendered design
argument-hint: https://www.figma.com/design/…
---

The user will provide a Figma file/design/proto URL or a file key as `${input:file:Figma URL or file key}`. Follow `.github/skills/figma-cli/SKILL.md` for CLI rules.

1. From the goat repo (do not `cd` into a sibling first), run `#tool:runCommands` with cwd = the goat folder and `uv run goat figma images ${input:file} --format json`. If cwd is already a product clone, use `uv run --project "$GOAT_ROOT" goat figma images ${input:file} --format json` instead — bare `uv run goat` cannot spawn there.
2. If `uv` is missing, follow `docs/install-uv.md` for the user's OS (macOS/Linux: `./scripts/setup.sh`; Windows: `.\scripts\setup.ps1`), then retry.
3. Use only that CLI JSON. Do not curl Figma, read `.env`, or call MCP.
4. For each `images[].url`, open the URL in VS Code Simple Browser and look at the rendered frame. That image is the visual source of truth.
5. Summarize the visible screen: layout, obvious components, and copy you can actually read. Do not invent spacing or tokens.
6. If designer notes would help, also run `uv run goat figma comments ${input:file} --format json` and read `comments[].message`.
7. If they asked for exact colors, type, or spacing on a **small targeted frame**, also run `uv run goat figma nodes ${input:file} --format json`. Remind them this returns raw Figma JSON and should stay on that tight node. Do not run `nodes` on a page, file, or large artboard.
8. If `missing` is set, say which nodes failed.
9. If they want implementation next, write a short plan and stop unless they ask to implement.

If they passed several frames (or a ticket **Figma frames** table), treat each row's **role** (`default`, `success`, `error`, …) as the meaning of that PNG. `figma images` does not return frame names. Ask for missing roles instead of guessing. See `templates/jira-ticket.md`.

Do not download the PNG into a product repo unless they asked. Do not reconstruct the design from JSON. The rendered image is the visual source of truth.

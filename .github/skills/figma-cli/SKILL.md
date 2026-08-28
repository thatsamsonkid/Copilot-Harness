---
name: figma-cli
description: Operate the local coboose Figma CLI (uv run coboose). Use when the user pastes a Figma file/design/proto URL, a file key plus node id, or asks to export a frame image, inspect clipped node styling, fetch file comments, inspect Figma schema, or diagnose Figma auth. Do not curl Figma, read .env, print tokens, or use a Figma MCP server.
argument-hint: https://www.figma.com/design/…
---

# Figma CLI

This workspace talks to Figma only through the `coboose` CLI. There is no Figma MCP server.

The Images API returns a small map of node id → rendered PNG URL. That URL is the visual source of truth. Do not fetch the whole Figma file JSON.

## Hard rules

- Run `uv run coboose <command>` from the coboose repo (or `./scripts/coboose.sh` / `.\scripts\coboose.ps1`). If you already `cd`'d into a sibling, use `uv run --project "$COBOOSE_ROOT" coboose <command>` — bare `uv run coboose` cannot spawn there. If `uv` is missing, follow `docs/install-uv.md` (macOS/Linux: `./scripts/setup.sh`; Windows: `.\scripts\setup.ps1`).
- Default `--format` is `json`. Keep JSON. Read stdout. Errors are JSON on stderr with a non-zero exit.
- Treat CLI JSON as complete. It is already filtered by `catalog/stack.yaml` `figma.fields`, `figma.comment_fields`, `figma.node_fields`, and `figma.shapes`. Do not ask Figma for more fields.
- Never curl, fetch, or browse `api.figma.com` or `/v1/`.
- Never read `.env`, print `env`, or expand `$FIGMA_ACCESS_TOKEN` / `$FIGMA_TOKEN` / `$FIGMA_API_TOKEN`.
- Never configure or call a Figma MCP tool.
- If credentials are missing, tell the user to run `uv run coboose figma login` in their own terminal. Never ask them to paste a token into chat.
- `figma whoami` must not include a token. If it ever does, stop and do not repeat it.

## Parse the file

Accept a Figma URL (`/design/`, `/file/`, `/proto/`) or a bare file key. The CLI extracts `file_key` and `node-id`. A frame link that includes `node-id` is enough. If they only have a file key, they must also pass `--ids 12:34` for `images` and `nodes`.

## Which command

| User intent | Command |
| --- | --- |
| Export rendered frame URLs (default) | `uv run coboose figma images <URL>` |
| File key plus node ids | `uv run coboose figma images <KEY> --ids 12:34,12:56` |
| Override format / scale | add `--image-format png` and/or `--scale 2` |
| Design comments on the pasted frame | `uv run coboose figma comments <URL>` |
| Comments for the whole file | add `--file-comments` |
| Clipped styling for a small specific frame | `uv run coboose figma nodes <URL>` |
| Shallower / deeper node tree | add `--depth 1` (max is `figma.max_depth`) |
| What Copilot is allowed to see | `uv run coboose figma schema` |
| Auth check (no token in output) | `uv run coboose figma whoami` |
| Store token in OS keychain | Tell them to run `uv run coboose figma login` (or `--from-env`) themselves |
| Catalog / clones / env | `uv run coboose doctor` |
| Live Figma ping | `uv run coboose doctor --ping-figma` |
| First-run / missing token | `uv run coboose init` (see the get-started skill) |

Always start with `figma images`. Add `figma comments` when designer notes would help. Use `figma nodes` only for a small, specific frame when you need exact colors, type, or spacing — never for a whole page or file.

Prefer these commands over assembling a Figma REST call yourself.

## `figma images` JSON

Use these objects only:

- `file_key` — Figma file key
- `url` — browse URL for the file (and node when one was given)
- `format` / `scale` — export settings
- `images` — list of `{id, url}`. Each `url` is a temporary rendered PNG (or the requested format)
- `missing` — node ids Figma could not render

## `figma comments` JSON

- `file_key` / `url`
- `comments` — list of `{author, created, message, node_id, resolved}`
- A frame URL filters to that node plus replies. `--file-comments` returns the whole file (still capped by `figma.max_comments`)

## `figma nodes` JSON

- `file_key` / `url` / `depth`
- `nodes` — clipped trees (`id`, `name`, `type`, `size`, `fills`, `strokes`, `typography`, `layout`, `characters`, `children`, …)
- `missing` — node ids Figma could not return
- Requires a `node-id` or `--ids`. Depth defaults to `figma.default_depth` and cannot exceed `figma.max_depth`. Wide frames clip children at `figma.max_children`.

## After a successful export

This skill is the CLI contract, not an implementer.

1. For each `images[].url`, open the URL in **VS Code Simple Browser** (Simple Browser: Show) so you can see the rendered frame. Taking a screenshot of that tab is the intended way to look at the design.
2. Summarize from what you can see in those images plus the returned ids. Do not invent layout, spacing, or copy that is not visible.
3. If you also fetched comments, treat `message` as designer context. Do not treat a comment as an implementation spec unless the user said to.
4. If you also fetched nodes, use fills / type / spacing as tokens that confirm what the image shows. Do not reconstruct the screen from the node tree.
5. Do not download the PNG into a product repo unless the user asked.
6. If `missing` is set, say which nodes failed. Do not guess those frames.
7. If the user wants a plan, write one from the visible frames and stop. Do not edit product code until they ask.

Do not try to reconstruct the screen from JSON. The Images payload is only ids and URLs.

## Auth and setup failures

| Symptom | What to do |
| --- | --- |
| Missing `FIGMA_ACCESS_TOKEN` | Tell the user to run `uv run coboose figma login` (`docs/figma-access-token.md`) |
| 401 / 403 from the CLI | Tell them to rotate the Figma personal access token and run `uv run coboose figma login` |
| Comments 403 / `file_comments:read` | Their token is images-only. Tell them to create a token that includes file comments read |
| No `node-id` on images/nodes | Ask for a frame URL, or `--ids 12:34` |
| `uv` missing | `docs/install-uv.md` — macOS/Linux `setup.sh`, Windows `setup.ps1` |
| `Failed to spawn: coboose` / no `pyproject.toml` | Cwd is a sibling. Re-run from the coboose folder or `uv run --project "$COBOOSE_ROOT" coboose …` |

## Related Copilot customizations

- Always-on rules: `.github/copilot-instructions.md`
- First-run setup: get-started skill or `/get-started`
- Export a pasted frame: `/figma-frame`
- Ticket routing: jira-cli skill or `/jira-ticket`
- Vague / large-repo orientation: workspace-context skill or `/orient`
- Implement an agreed plan: Implementer agent
- Review a diff: Reviewer agent or `/review`

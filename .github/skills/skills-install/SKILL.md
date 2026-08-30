---
name: skills-install
description: List sibling or remote agent skills and copy them into the coboose .github/skills root so VS Code Agents can load them. Use when the Agents window cannot see child-repo skills, the user asks to lift/install/copy skills, or a git URL of skills should be pulled. Temporary multi-root shim. Do not commit lifted copies. Do not nest clones inside coboose.
argument-hint: list | lift | pull <git-url>
---

# Skills install (VS Code Agents shim)

VS Code Agents does not scan skills in multi-root child folders. Copilot can still *read* a sibling `SKILL.md` if you open it, but those skills are not first-class in chat. This coboose copies selected skills into **this repo's** `.github/skills/` (the first workspace folder) so the Agents window can detect them.

This is a local overlay. Do not commit lifted or pulled copies into coboose.

## Commands

Run these from the coboose repo. After `cd` into a sibling, use `uv run --project "$COBOOSE_ROOT" coboose …` or `./scripts/coboose.sh`.

| User intent | Command |
| --- | --- |
| What skills exist in coboose + siblings | `uv run coboose skills list --format json` |
| Name + description only (many siblings) | `uv run coboose skills list --brief --format json` |
| Open feature workspace only | `uv run coboose skills list` (follows `COBOOSE_WORKSPACE`) |
| One catalog workspace | `uv run coboose skills list --workspace frontend` |
| One or more repos | `uv run coboose skills list --repo frontend,backend` |
| Every enabled repo | `uv run coboose skills list --all` (only if they asked for the full catalog) |
| Lift from a terminal (pick numbers or `all`) | Tell them to run `uv run coboose skills lift` themselves |
| Lift every discovered skill (no prompt) | `uv run coboose skills lift --all-skills --format json` |
| Lift a subset | `uv run coboose skills lift --only <pick,pick>` |
| Preview a lift | `uv run coboose skills lift --all-skills --dry-run` |
| Single-folder window on parent_dir | add `--parent` (copies into `parent_dir/.github/skills`) |
| Preview a remote skills repo | `uv run coboose skills pull <git-url> --format json` |
| Install selected remote skills | `uv run coboose skills pull <git-url> --only name,name` |
| Install every skill in that repo | `uv run coboose skills pull <git-url> --all` |

`init`, `prepare`, `workspace generate`, `workspace create`, and `doctor` already lift coboose plus in-scope siblings with no prompt. Use the commands above when the user wants a catalog, a subset, or a remote repo.

## Walkthrough

1. Run `coboose skills list --brief`. Stay inside `workspace.repos` unless they asked for `--all`. `--brief` is only `name`, `description`, `source_id`, and `pick`.
2. Show that catalog. First-party coboose skills are already in the dest; they are not copied over themselves.
3. If they want sibling skills in the Agents window, tell them to run `coboose skills lift` in their terminal. It prints a numbered list (name + description) and accepts numbers, names, ranges (`1-3`), or `all`. Do not drive that prompt from chat. From chat, use `--only` with `available[].pick` or `--all-skills`.
4. If they paste a git URL of skills, run `coboose skills pull <url>` first **without** `--only`. If `needs_selection` is true, show `available[]` and ask which names to install. Then rerun with `--only name,name` or `--all`.
5. Do not `git clone` a skills repo into this coboose or a sibling. `skills pull` uses a temp directory and deletes it.
6. Tell them copies land in `dest` and are gitignored. Do not `git add` them unless they explicitly ask.

## Hard rules

- Never nest a skills clone inside this coboose.
- Never overwrite a first-party coboose skill (`get-started`, `jira-cli`, and the other committed folders).
- Never commit lifted product skills or remote copies here.
- Do not treat every clone under `parent_dir` as in scope. Pass `--all` only when they asked.
- Do not execute files from a pulled skills repo. Copy `SKILL.md` folders only.

## Failures

| Symptom | What to tell them |
| --- | --- |
| Agents window still misses a skill | Confirm `dest` is this coboose `.github/skills` (or `--parent` if they opened `parent_dir` as one folder). Reload the window. |
| `Unknown skill name(s)` | Re-run `skills list` and pass `available[].pick` to `--only` |
| `needs_selection` | Ask which `available[]` names to install, then `skills pull <url> --only …` |
| `Failed to spawn: coboose` | Cwd is a sibling. Re-run from this repo or `uv run --project "$COBOOSE_ROOT" coboose …` |

## Related Copilot customizations

- First-run setup: get-started skill or `/get-started`
- Vague / large-repo orientation: workspace-context skill or `/orient`
- Ticket routing: jira-cli skill or `/jira-ticket`
- Local stack start: workspace-start skill or `/start-workspace`

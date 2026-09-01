---
name: skills-install
description: List sibling or remote agent skills and copy them into the goat .github/skills root so VS Code Agents can load them. Use when the Agents window cannot see child-repo skills, the user asks to lift/install/copy skills, or a git URL of skills should be pulled. Temporary multi-root shim. Do not commit lifted copies. Do not nest clones inside goat.
argument-hint: list | lift | pull <git-url>
---

# Skills install (VS Code Agents shim)

VS Code Agents does not scan skills in multi-root child folders. Copilot can still *read* a sibling `SKILL.md` if you open it, but those skills are not first-class in chat. This goat copies selected skills into **this repo's** `.github/skills/` (the first workspace folder) so the Agents window can detect them.

This is a local overlay. Do not commit lifted or pulled copies into goat.

## Commands

Run these from the goat repo. After `cd` into a sibling, use `uv run --project "$GOAT_ROOT" goat …` or `./scripts/goat.sh`.

| User intent | Command |
| --- | --- |
| What skills exist in goat + siblings | `uv run goat skills list --format json` |
| Name + description only (many siblings) | `uv run goat skills list --brief --format json` |
| Open feature workspace only | `uv run goat skills list` (follows `GOAT_WORKSPACE`) |
| One catalog workspace | `uv run goat skills list --workspace frontend` |
| One or more repos | `uv run goat skills list --repo frontend,backend` |
| Every enabled repo | `uv run goat skills list --all` (only if they asked for the full catalog) |
| Lift from a terminal (pick numbers or `all`) | Tell them to run `uv run goat skills lift` themselves |
| Lift every discovered skill (no prompt) | `uv run goat skills lift --all-skills --format json` |
| Lift a subset | `uv run goat skills lift --only <pick,pick>` |
| Preview a lift | `uv run goat skills lift --all-skills --dry-run` |
| Single-folder window on parent_dir | add `--parent` (copies into `parent_dir/.github/skills`) |
| Preview a remote skills repo | `uv run goat skills pull <git-url> --format json` |
| Install selected remote skills | `uv run goat skills pull <git-url> --only name,name` |
| Install every skill in that repo | `uv run goat skills pull <git-url> --all` |

`init`, `prepare`, `workspace generate`, `workspace create`, and `doctor` already lift goat plus in-scope siblings with no prompt. Use the commands above when the user wants a catalog, a subset, or a remote repo.

## Walkthrough

1. Run `goat skills list --brief`. Stay inside `workspace.repos` unless they asked for `--all`. `--brief` is only `name`, `description`, `source_id`, and `pick`.
2. Show that catalog. First-party goat skills are already in the dest; they are not copied over themselves.
3. If they want sibling skills in the Agents window, tell them to run `goat skills lift` in their terminal. It prints a numbered list (name + description) and accepts numbers, names, ranges (`1-3`), or `all`. Do not drive that prompt from chat. From chat, use `--only` with `available[].pick` or `--all-skills`.
4. If they paste a git URL of skills, run `goat skills pull <url>` first **without** `--only`. If `needs_selection` is true, show `available[]` and ask which names to install. Then rerun with `--only name,name` or `--all`.
5. Do not `git clone` a skills repo into this goat or a sibling. `skills pull` uses a temp directory and deletes it.
6. Tell them copies land in `dest` and are gitignored. Do not `git add` them unless they explicitly ask.

## Hard rules

- Never nest a skills clone inside this goat.
- Never overwrite a first-party goat skill (`get-started`, `jira-cli`, `jira-ticket`, and the other committed folders).
- Never commit lifted product skills or remote copies here.
- Do not treat every clone under `parent_dir` as in scope. Pass `--all` only when they asked.
- Do not execute files from a pulled skills repo. Copy `SKILL.md` folders only.

## Failures

| Symptom | What to tell them |
| --- | --- |
| Agents window still misses a skill | Confirm `dest` is this goat `.github/skills` (or `--parent` if they opened `parent_dir` as one folder). Reload the window. |
| `Unknown skill name(s)` | Re-run `skills list` and pass `available[].pick` to `--only` |
| `needs_selection` | Ask which `available[]` names to install, then `skills pull <url> --only …` |
| `Failed to spawn: goat` | Cwd is a sibling. Re-run from this repo or `uv run --project "$GOAT_ROOT" goat …` |

## Related Copilot customizations

- First-run setup: get-started skill or `/get-started`
- Vague / large-repo orientation: workspace-context skill or `/orient`
- Ticket routing: jira-cli skill, jira-ticket skill, or `/jira-ticket`
- Local stack start: workspace-start skill or `/start-workspace`

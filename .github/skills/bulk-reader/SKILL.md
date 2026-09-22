---
name: bulk-reader
description: Survey large files as structured bullets. Do not use for debugging, architectural decisions, safety-critical analysis, or as the source of truth for edits.
argument-hint: survey question and file paths
---

# Bulk reader

Whole-file reads of large files are blocked by the `check-file-size` and `check-bash-read` hooks (default 350 lines, `GOAT_BULK_READ_MAX_LINES` or `.github/hooks/read-guard.json`). Delegation saves tokens on **understanding** only.

## Do not use

Do not invoke Bulk Reader (and do not treat a hook deny as an order to delegate) when the work is:

- Debugging (races, thread-safety, failed tests, repros)
- Architectural decisions (what to build, which pattern to keep)
- Safety-critical code (auth, payments, concurrency, data loss)
- An edit you are about to make

For those, stay in this chat. Open the section with a targeted `Read` (`limit` / `offset`). Piped shell (`cat file | grep …`) is allowed. Bulk Reader bullets are not reliable enough to edit from — re-read the slice first.

## How to run (survey only)

1. Invoke the **Bulk Reader** agent with `#tool:agent`. Agent names are case-sensitive. Its profile pins Copilot Auto (`Auto (copilot)`) — do not override the model.
2. Each call is stateless. Include the exact survey question, repo-relative paths or symbols, and what to skip.
3. Ask for structured bullets only (name, type, and `path:line`). No source dump.
4. **Fan out Bulk Readers.** In the same turn, invoke one `#tool:agent` Bulk Reader per independent group. Prefer one group per repo, or disjoint path sets in the same repo. Cap a group at a handful of files. Never send the same file to two readers. A single group is a single call — sequential readers are the fallback, not the default.
5. Stay inside `workspace.repos` from `goat context` / `prepare`. Never read `.env` or tokens.

When `/goat-plan` or Jira Planner is gathering context, record those groups in the plan's **Survey groups** table so `/goat-implement` can fan out the same way before a wave. If **Survey groups** is `None` (or missing), group that wave's `Model after` / reference paths by repo yourself.

## Output you should expect

- `ClassName` (class, `repo/path.py:12`)
  - `method` (`:40`) — one-line fact
- `MISSING path — not found`

Synthesize those bullets as a map. Do not paste the file. Do not apply edits until you have targeted-read the lines yourself.

## Related Copilot customizations

- Feature planning: Jira Planner or `/jira-ticket`
- Write a plan: planning skill or `/goat-plan` (fan out Bulk Readers; fill **Survey groups**)
- Start implementing a saved plan: implementing skill or `/goat-implement` (fan out Bulk Readers, then Code Writers)
- Hooks: `.github/hooks/check-file-size.json`, `.github/hooks/check-bash-read.json`, `.github/hooks/bulk-read-routing.json`

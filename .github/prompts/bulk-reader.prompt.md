---
name: bulk-reader
description: Survey large files as structured bullets. Not for debug, architecture, or edits.
argument-hint: survey question and file paths
agent: agent
tools: ['agent']
---

The user wants a survey of large or many files, not a debug or design pass. Load `.github/skills/bulk-reader/SKILL.md`.

1. If this turn is debugging, an architectural decision, or safety-critical analysis, do **not** invoke Bulk Reader. Targeted-`Read` the section yourself (`limit`/`offset`).
2. Otherwise invoke **Bulk Reader** (`#tool:agent`) with the exact survey question and repo-relative paths. Each call is stateless.
3. Synthesize bullets as a map. Do not dump source. Do not edit from those line numbers — re-read the slice before any change.

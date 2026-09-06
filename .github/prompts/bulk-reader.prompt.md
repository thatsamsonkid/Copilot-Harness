---
name: bulk-reader
description: Read large or many files as structured bullets instead of dumping source
argument-hint: question and file paths
agent: agent
tools: ['agent']
---

A whole-file read was blocked or the user wants context without flooding chat. Load `.github/skills/bulk-reader/SKILL.md`.

1. Invoke **Bulk Reader** (`#tool:agent`) with the exact question and repo-relative paths. Each call is stateless.
2. Ask for structured bullets only. Parallelize independent groups.
3. Synthesize. Quote paths and symbols. Do not dump source. Do not retry `cat`/`Read` on the blocked file without `limit`.

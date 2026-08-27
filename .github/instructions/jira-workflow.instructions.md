---
name: Jira ticket workflow
description: How to pull Jira context and choose a feature workspace
applyTo: "**"
---

Use the `harness` CLI instead of a Jira MCP server. Authentication is Jira Cloud basic auth (email + API token) from the environment.

Always parse issue keys from either `PROJ-123` or a browse URL. Prefer `harness prepare <KEY>` over assembling get/match/clone yourself.

When planning from a ticket, cite the issue key, status, components, labels, and the matched workspace id. If routing confidence is low (score 0 or only fallback reasons), ask which workspace to open.

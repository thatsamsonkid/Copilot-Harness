# Feature workspaces

`catalog/stack.yaml` is the committed catalog: starter workspace ids, repo folders/tags, and Jira routing.

The `.code-workspace` files in this folder are **generated locally**. Git ignores them. Do not commit them.

```bash
coboose workspace generate          # write starters from the catalog
coboose workspace list              # see ids, sync, open paths
coboose workspace open frontend     # open a catalog starter
coboose workspace create            # add a shared id to the catalog, or --personal
```

Get-started / `coboose init` / `setup` / `doctor` already generate the catalog starters. Open one of those, or create your own mix with `/new-workspace`.

- **Shared** (`coboose workspace create`) adds the id to `catalog/stack.yaml` so the team and Jira routing see it. The `.code-workspace` file is still local.
- **Personal** (`--personal`) stays under `workspaces/personal/` (gitignored, no catalog edit, no Jira routing).

A saved boot sequence is `workspaces/<id>.start.yml` next to the generated file. Those plans can be committed so the team reuses the same start order.

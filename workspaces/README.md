# Feature workspaces

`catalog/stack.yaml` is the committed catalog: workspace ids, repo folders/tags, and Jira routing.

The `.code-workspace` files in this folder are **generated locally**. Git ignores them. Do not commit them.

```bash
goat workspace generate          # write files from the catalog
goat workspace list              # see ids, sync, open paths
goat workspace open frontend     # open a catalog starter
goat workspace create            # add an id to the catalog
```

Get-started / `goat init` / `setup` / `doctor` already generate the catalog starters. Open one of those, or create your own mix with `/new-workspace`.

A saved boot sequence is `workspaces/<id>.start.yml` next to the generated file. Those plans can be committed so the team reuses the same start order.

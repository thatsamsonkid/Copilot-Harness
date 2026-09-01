# Feature workspaces

`catalog/stack.yaml` is the committed catalog: workspace ids, repo folders/tags, and Jira routing.

The `.code-workspace` files in this folder are **generated locally**. Git ignores them. Do not commit them.

```bash
goat workspace map --write --generate   # adopt existing clones, then write files
goat workspace generate                 # write files from the catalog
goat workspace list                     # see ids, sync, open paths
goat workspace open frontend            # open a catalog starter
goat workspace create                   # add an id to the catalog
```

If product repos already live somewhere else, `goat workspace map` matches them by git remote URL (not folder name) and writes gitignored `repositories.local.yml`. Generated workspace folders then point at those paths. Do not put machine-specific paths in `catalog/stack.yaml` or `repositories.yml`.

Get-started / `goat init` / `setup` / `doctor` already generate the catalog starters. Open one of those, or create your own mix with `/new-workspace`.

A saved boot sequence is `workspaces/<id>.start.yml` next to the generated file. Those plans can be committed so the team reuses the same start order.

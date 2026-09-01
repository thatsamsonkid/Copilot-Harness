# Workspace graph inputs

Committed intent lives in `catalog/graph.yaml` (declare / reject) and in each
sibling's `.workspace/component.yaml`.

Generated files go under `generated/` and are gitignored. Rebuild with:

```bash
goat graph build
goat graph explain application:frontend api:booking-v2
```

See `docs/workspace-graph.md`.

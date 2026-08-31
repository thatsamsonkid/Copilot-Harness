# Personal workspaces

`.code-workspace` files here are **local only**. Git ignores them, so you do not have to add ignore rules for each one.

Create one with:

```bash
goat workspace create --personal
```

or choose **personal** when `goat workspace create` prompts.

Shared team workspaces still live in `workspaces/<id>.code-workspace` and `catalog/stack.yaml`. Those are what `/new-workspace` writes when you pick **shared**.

A personal start sequence, if you save one, is `workspaces/personal/<id>.start.yml` next to that workspace file. Shared plans use `workspaces/<id>.start.yml`.

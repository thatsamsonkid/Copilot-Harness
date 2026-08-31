# Personal workspaces

`.code-workspace` files here are **local only**. Git ignores them, so you do not have to add ignore rules for each one.

Create one with:

```bash
coboose workspace create --personal
```

or choose **personal** when `coboose workspace create` prompts.

Shared team workspaces live in `catalog/stack.yaml`. `/new-workspace` writes that catalog when you pick **shared**. The matching `.code-workspace` file is generated locally (gitignored) by `coboose workspace generate`.

A personal start sequence, if you save one, is `workspaces/personal/<id>.start.yml` next to that workspace file. Shared plans use `workspaces/<id>.start.yml`.

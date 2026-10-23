---
name: bootstrap-project
description: List goat templates and bootstrap a new project under parent_dir from one of them
argument-hint: template-name new-folder
disable-model-invocation: true
---

The user wants to start a new project. Prefer a listed template over inventing a scaffold.

1. From the goat repo (do not `cd` into a sibling first), run `uv run goat templates --format json`. If cwd is already a product clone, use `uv run --project "$GOAT_ROOT" goat templates --format json`.
2. If the user named a template or their request clearly matches one (`spartan-stack`, `react-native`, `spring-boot`, or another `templates.yml` entry), use that. Otherwise show the list and ask which to use.
3. Agree a destination `--name` (and optional `--group` such as `frontend` / `backend` / `infra` / `shared`) that does not collide with `repositories.yml` or an existing folder under `parent_dir`. `--name frontend/shop-web` is the same as `--name shop-web --group frontend`.
4. Run `uv run goat bootstrap --template <template> --name <folder> --format json`. Add `--group` when they want organized folders. Take `<template>` and `<folder>` from the slash arguments when they supplied them.
5. Do not nest the new project inside this goat. Do not `git clone` by hand when `goat bootstrap` can do it.
6. Summarize the created path, whether origin was detached, and the CLI `next_steps`.
7. Ask before `--register` (adds the project to `repositories.yml`) or `--fresh-git`.

If `uv` is missing, run `./scripts/setup.sh`, then retry with `./scripts/goat.sh`.

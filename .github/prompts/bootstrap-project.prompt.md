---
name: bootstrap-project
description: List harness templates and bootstrap a new project under parent_dir from one of them
argument-hint: template-name new-folder
agent: plan
---

The user wants to start a new project. Prefer a listed template over inventing a scaffold.

1. From the harness repo, run `#tool:runCommands` with `uv run harness templates --format json`.
2. If the user named a template or their request clearly matches one (`spartan-stack`, `react-native`, `spring-boot`, or another `templates.yml` entry), use that. Otherwise show the list and ask which to use.
3. Agree a destination `--name` (and optional `--group` such as `frontend` / `backend` / `infra` / `shared`) that does not collide with `repositories.yml` or an existing folder under `parent_dir`. `--name frontend/shop-web` is the same as `--name shop-web --group frontend`.
4. Run `#tool:runCommands` with `uv run harness bootstrap --template ${input:template:Template name from templates.yml} --name ${input:name:New folder name or group/name} --format json`. Add `--group` when they want organized folders.
5. Do not nest the new project inside this harness. Do not `git clone` by hand when `harness bootstrap` can do it.
6. Summarize the created path, whether origin was detached, and the CLI `next_steps`.
7. Ask before `--register` (adds the project to `repositories.yml`) or `--fresh-git`.

If `uv` is missing, run `./scripts/setup.sh`, then retry with `./scripts/harness.sh`.

from __future__ import annotations

from pathlib import Path
from typing import Any

from goat.branch import suggested_branch
from goat.catalog import Catalog
from goat.clone import clone_repos
from goat.context import inspect_repo
from goat.done import build_done_when
from goat.jira_client import JiraClient
from goat.routing import recommend_workspace
from goat.skills import sync_root_skills
from goat.workspace import generate_workspaces, open_command
from goat.workspace_detect import resolve_workspace_scope


def prepare_issue(
    catalog: Catalog,
    goat_root: Path,
    client: JiraClient,
    key: str,
    *,
    clone_missing: bool = False,
    generate: bool = True,
) -> dict[str, Any]:
    issue = client.get_context(key, settings=catalog.jira)
    recommended, alternatives = recommend_workspace(catalog, issue)
    if generate:
        generate_workspaces(catalog, goat_root)

    if recommended is None:
        return {
            "issue": issue,
            "routing": None,
            "next_steps": ["Add workspaces to catalog/stack.yaml and rerun prepare."],
        }

    workspace = catalog.workspace(recommended["id"])
    workspace_file = catalog.workspace_file(goat_root, workspace)
    repos = []
    missing = []
    for repo_id in catalog.workspace_repo_names(workspace):
        repo = catalog.repo(repo_id)
        path = catalog.repo_path(goat_root, repo)
        present = path.exists()
        snapshot = inspect_repo(catalog, goat_root, repo)
        item = {
            "name": repo.name,
            "id": repo.name,
            "url": repo.url,
            "tags": repo.tags,
            "path": str(path),
            "cloned": present,
            "placeholder": repo.is_placeholder,
            "graphify": snapshot["graphify"],
            "instructions": snapshot["instructions"],
            "knowledge": snapshot["knowledge"],
            "tooling": snapshot["tooling"],
        }
        repos.append(item)
        if not present:
            missing.append(item)

    clone_result = None
    if clone_missing and missing:
        clone_result = clone_repos(
            catalog,
            goat_root,
            only=[item["id"] for item in missing],
        )
        for item in repos:
            item["cloned"] = catalog.repo_path(goat_root, item["id"]).exists()
        missing = [item for item in repos if not item["cloned"]]

    next_steps = [
        "Read the issue summary, description, comments, and linked work.",
        f"Open the recommended workspace: {open_command(workspace_file)}",
        "Inspect only the repos listed in routing.repos unless the ticket clearly needs more.",
        "If a repo has graphify.report, read that before grepping the tree.",
        "Before editing, load that repo's instruction files and knowledge notes; use tooling.suggested_verify after changes.",
        "If the change adds user-visible or non-obvious behavior, update docs/features (or an ADR) in that sibling. Do not file it in the Goat repo.",
        f"Use branch name {suggested_branch(issue['key'])} in each touched sibling (`goat branch {issue['key']}`).",
        "Treat done_when as the stop condition. Do not declare the ticket done until those items are checked.",
        "Write an implementation plan covering impacted repos, files, risks, and test strategy.",
        "Do not start coding until the plan is agreed, unless the user asks to implement immediately.",
        "If VS Code Agents cannot see sibling skills, use routing.skills or `goat skills list` / `skills lift`.",
    ]
    if missing:
        ids = ",".join(item["id"] for item in missing)
        next_steps.insert(
            1,
            f"Clone missing repos: goat clone --only {ids}",
        )

    current = resolve_workspace_scope(catalog, goat_root)
    if current.detected and current.id != workspace.id:
        next_steps.insert(
            1,
            (
                f"This window is workspace {current.id}. "
                f"Open the recommended workspace before planning: "
                f"{open_command(workspace_file)}"
            ),
        )

    return {
        "issue": issue,
        "current_workspace": current.as_payload(),
        "routing": {
            "workspace_id": workspace.id,
            "workspace_name": workspace.name,
            "workspace_file": str(workspace_file),
            "score": recommended["score"],
            "reasons": recommended["reasons"],
            "alternatives": alternatives[:3],
            "repos": repos,
            "missing_repos": missing,
            "open_command": open_command(workspace_file),
            "clone_command": (
                "goat clone --only " + ",".join(item["id"] for item in missing)
                if missing
                else None
            ),
            "clone_result": clone_result,
            "suggested_branch": suggested_branch(issue["key"]),
        },
        "done_when": build_done_when(issue, repos),
        "skills": sync_root_skills(
            catalog,
            goat_root,
            workspace_id=workspace.id,
        ),
        "next_steps": next_steps,
    }

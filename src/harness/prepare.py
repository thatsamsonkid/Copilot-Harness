from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.catalog import Catalog
from harness.clone import clone_repos
from harness.context import inspect_repo
from harness.jira_client import JiraClient
from harness.routing import recommend_workspace
from harness.workspace import generate_workspaces, open_command


def prepare_issue(
    catalog: Catalog,
    harness_root: Path,
    client: JiraClient,
    key: str,
    *,
    clone_missing: bool = False,
    generate: bool = True,
) -> dict[str, Any]:
    issue = client.get_context(key, settings=catalog.jira)
    recommended, alternatives = recommend_workspace(catalog, issue)
    if generate:
        generate_workspaces(catalog, harness_root)

    if recommended is None:
        return {
            "issue": issue,
            "routing": None,
            "next_steps": ["Add workspaces to catalog/stack.yaml and rerun prepare."],
        }

    workspace = catalog.workspace(recommended["id"])
    workspace_file = catalog.workspace_file(harness_root, workspace)
    repos = []
    missing = []
    for repo_id in catalog.workspace_repo_names(workspace):
        repo = catalog.repo(repo_id)
        path = catalog.repo_path(harness_root, repo)
        present = path.exists()
        snapshot = inspect_repo(catalog, harness_root, repo)
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
            "tooling": snapshot["tooling"],
        }
        repos.append(item)
        if not present:
            missing.append(item)

    clone_result = None
    if clone_missing and missing:
        clone_result = clone_repos(
            catalog,
            harness_root,
            only=[item["id"] for item in missing],
        )
        for item in repos:
            item["cloned"] = catalog.repo_path(harness_root, item["id"]).exists()
        missing = [item for item in repos if not item["cloned"]]

    next_steps = [
        "Read the issue summary, description, comments, and linked work.",
        f"Open the recommended workspace: {open_command(workspace_file)}",
        "Inspect only the repos listed in routing.repos unless the ticket clearly needs more.",
        "If a repo has graphify.report, read that before grepping the tree.",
        "Before editing, load that repo's instruction files and use tooling.suggested_verify after changes.",
        "Write an implementation plan covering impacted repos, files, risks, and test strategy.",
        "Do not start coding until the plan is agreed, unless the user asks to implement immediately.",
    ]
    if missing:
        ids = ",".join(item["id"] for item in missing)
        next_steps.insert(
            1,
            f"Clone missing repos: harness clone --only {ids}",
        )

    return {
        "issue": issue,
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
                "harness clone --only " + ",".join(item["id"] for item in missing)
                if missing
                else None
            ),
            "clone_result": clone_result,
        },
        "next_steps": next_steps,
    }

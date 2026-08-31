from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from coboose import CobooseError
from coboose.catalog import Catalog, Workspace
from coboose.envspec import vars_for
from coboose.invoke import COBOOSE_FOLDER_NAME, terminal_env_settings
from coboose.paths import WORKSPACES_DIR


def workspace_document(catalog: Catalog, coboose_root: Path, workspace: Workspace) -> dict[str, Any]:
    folders: list[dict[str, str]] = []
    workspace_file = catalog.workspace_file(coboose_root, workspace)
    if workspace.include_coboose:
        folders.append(
            {
                "name": COBOOSE_FOLDER_NAME,
                "path": _rel(workspace_file, coboose_root),
            }
        )
    for repo_id in catalog.workspace_repo_names(workspace):
        repo = catalog.repo(repo_id)
        folders.append(
            {
                "name": repo.name,
                "path": _rel(workspace_file, catalog.repo_path(coboose_root, repo)),
            }
        )
    settings: dict[str, Any] = {
        "git.autoRepositoryDetection": True,
        "git.detectSubmodules": False,
        "git.repositoryScanMaxDepth": 1,
        "git.openRepositoryInParentFolders": "never",
        "github.copilot.chat.codeGeneration.useInstructionFiles": True,
        "chat.useCustomizationsInParentRepositories": True,
    }
    settings.update(
        terminal_env_settings(
            folder_name=COBOOSE_FOLDER_NAME if workspace.include_coboose else None,
            workspace_id=workspace.id,
            include_root=workspace.include_coboose,
        )
    )
    return {
        "folders": folders,
        "settings": settings,
        "extensions": {
            "recommendations": [
                "GitHub.copilot",
                "GitHub.copilot-chat",
            ]
        },
        "coboose": {
            "id": workspace.id,
            "name": workspace.name,
            "description": workspace.description,
            "folders": catalog.workspace_repo_names(workspace),
            "tags": workspace.tags,
            "include_coboose": workspace.include_coboose,
        },
    }


def workspace_file_text(
    catalog: Catalog, coboose_root: Path, workspace: Workspace
) -> str:
    return json.dumps(workspace_document(catalog, coboose_root, workspace), indent=2) + "\n"


def write_workspace_file(
    catalog: Catalog, coboose_root: Path, workspace: Workspace
) -> dict[str, Any]:
    path = catalog.workspace_file(coboose_root, workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = workspace_document(catalog, coboose_root, workspace)
    text = workspace_file_text(catalog, coboose_root, workspace)
    existed = path.exists()
    previous = path.read_text(encoding="utf-8") if existed else None
    path.write_text(text, encoding="utf-8")
    if not existed:
        action = "created"
    elif previous != text:
        action = "updated"
    else:
        action = "unchanged"
    return {
        "id": workspace.id,
        "name": workspace.name,
        "file": str(path),
        "folders": [folder["name"] for folder in document["folders"]],
        "action": action,
        "changed": action != "unchanged",
    }


def generate_workspaces(catalog: Catalog, coboose_root: Path) -> list[dict[str, Any]]:
    return [
        write_workspace_file(catalog, coboose_root, workspace)
        for workspace in catalog.workspaces
    ]


def workspace_file_status(
    catalog: Catalog, coboose_root: Path, workspace: Workspace
) -> dict[str, Any]:
    path = catalog.workspace_file(coboose_root, workspace)
    payload: dict[str, Any] = {
        "id": workspace.id,
        "name": workspace.name,
        "file": str(path),
        "exists": path.exists(),
    }
    if not path.exists():
        payload["status"] = "missing"
        return payload
    actual = path.read_text(encoding="utf-8")
    expected = workspace_file_text(catalog, coboose_root, workspace)
    payload["status"] = "ok" if actual == expected else "stale"
    return payload


def check_workspaces(catalog: Catalog, coboose_root: Path) -> dict[str, Any]:
    """Compare catalog/stack.yaml workspaces to workspaces/*.code-workspace."""
    expected_ids = {workspace.id for workspace in catalog.workspaces}
    workspaces = [
        workspace_file_status(catalog, coboose_root, workspace)
        for workspace in catalog.workspaces
    ]
    missing = [item["id"] for item in workspaces if item["status"] == "missing"]
    stale = [item["id"] for item in workspaces if item["status"] == "stale"]
    orphans: list[dict[str, str]] = []
    directory = coboose_root / WORKSPACES_DIR
    if directory.is_dir():
        for path in sorted(directory.glob("*.code-workspace")):
            if not path.is_file() or path.stem in expected_ids:
                continue
            orphans.append({"id": path.stem, "file": str(path), "status": "orphan"})
    in_sync = not missing and not stale and not orphans
    payload: dict[str, Any] = {
        "ok": in_sync,
        "in_sync": in_sync,
        "workspaces": workspaces,
        "missing": missing,
        "stale": stale,
        "orphans": [item["id"] for item in orphans],
        "orphan_files": orphans,
    }
    if not in_sync:
        payload["hint"] = (
            "Run `coboose workspace generate` to rewrite workspaces/*.code-workspace "
            "from catalog/stack.yaml. Delete orphan files or add the id to the catalog."
        )
    return payload


def workspace_sync_error(status: dict[str, Any]) -> str:
    parts: list[str] = []
    if status.get("missing"):
        parts.append("missing " + ", ".join(status["missing"]))
    if status.get("stale"):
        parts.append("stale " + ", ".join(status["stale"]))
    if status.get("orphans"):
        parts.append("orphan " + ", ".join(status["orphans"]))
    detail = "; ".join(parts) if parts else "unknown drift"
    return (
        "Shared workspace files are out of sync with catalog/stack.yaml "
        f"({detail}). Run `coboose workspace generate` to rewrite "
        "workspaces/*.code-workspace from the catalog."
    )


def list_workspaces(catalog: Catalog, coboose_root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for workspace in catalog.workspaces:
        path = catalog.workspace_file(coboose_root, workspace)
        start_file = catalog.workspace_start_file(coboose_root, workspace)
        repos = []
        for repo_id in catalog.workspace_repo_names(workspace):
            repo_path = catalog.repo_path(coboose_root, repo_id)
            repos.append(
                {
                    "id": repo_id,
                    "path": str(repo_path),
                    "relpath": catalog.repo(repo_id).path,
                    "group": catalog.repo(repo_id).group,
                    "cloned": repo_path.exists(),
                }
            )
        sync = workspace_file_status(catalog, coboose_root, workspace)
        result.append(
            {
                "id": workspace.id,
                "name": workspace.name,
                "description": workspace.description,
                "fallback": workspace.fallback,
                "env": [
                    variable.name
                    for variable in vars_for(
                        catalog.env_vars, workspace.id, workspace.env
                    )
                ],
                "file": str(path),
                "exists": path.exists(),
                "sync": sync["status"],
                "in_sync": sync["status"] == "ok",
                "open_command": open_command(path),
                "start_file": str(start_file),
                "start_plan": start_file.is_file(),
                "repos": repos,
            }
        )
    return result


def catalog_starters(catalog: Catalog, coboose_root: Path) -> list[dict[str, Any]]:
    """Shared catalog/stack.yaml workspaces for get-started / init."""
    starters: list[dict[str, Any]] = []
    for row in list_workspaces(catalog, coboose_root):
        starters.append(
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "fallback": row["fallback"],
                "file": row["file"],
                "exists": row["exists"],
                "open_command": row["open_command"],
            }
        )
    return starters


def open_command(workspace_file: Path) -> str:
    return f"code {workspace_file}"


def open_workspace(workspace_file: Path) -> dict[str, Any]:
    if not workspace_file.exists():
        raise CobooseError(
            f"Workspace file missing: {workspace_file}. Run `coboose workspace generate`."
        )
    command = ["code", str(workspace_file)]
    if shutil.which("code"):
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        launched = True
    else:
        launched = False
    return {
        "file": str(workspace_file),
        "command": " ".join(command),
        "launched": launched,
    }


def _rel(workspace_file: Path, target: Path) -> str:
    return Path(os_relpath(target, workspace_file.parent)).as_posix()


def os_relpath(target: Path, start: Path) -> str:
    return os_path_rel(target.resolve(), start.resolve())


def os_path_rel(target: Path, start: Path) -> str:
    import os

    return os.path.relpath(target, start)

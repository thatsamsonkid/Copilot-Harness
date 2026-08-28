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
            "personal": workspace.personal,
            "folders": catalog.workspace_repo_names(workspace),
            "tags": workspace.tags,
            "include_coboose": workspace.include_coboose,
        },
    }


def write_workspace_file(
    catalog: Catalog, coboose_root: Path, workspace: Workspace
) -> dict[str, Any]:
    path = catalog.workspace_file(coboose_root, workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = workspace_document(catalog, coboose_root, workspace)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return {
        "id": workspace.id,
        "name": workspace.name,
        "personal": workspace.personal,
        "file": str(path),
        "folders": [folder["name"] for folder in document["folders"]],
    }


def generate_workspaces(catalog: Catalog, coboose_root: Path) -> list[dict[str, Any]]:
    return [
        write_workspace_file(catalog, coboose_root, workspace)
        for workspace in catalog.workspaces
        if not workspace.personal
    ]


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
                "personal": workspace.personal,
                "file": str(path),
                "exists": path.exists(),
                "start_file": str(start_file),
                "start_plan": start_file.is_file(),
                "repos": repos,
            }
        )
    return result


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

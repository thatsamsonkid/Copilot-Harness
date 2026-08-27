from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from harness import HarnessError
from harness.catalog import Catalog, Workspace
from harness.invoke import HARNESS_FOLDER_NAME, terminal_env_settings


def workspace_document(catalog: Catalog, harness_root: Path, workspace: Workspace) -> dict[str, Any]:
    folders: list[dict[str, str]] = []
    workspace_file = catalog.workspace_file(harness_root, workspace)
    if workspace.include_harness:
        folders.append(
            {
                "name": HARNESS_FOLDER_NAME,
                "path": _rel(workspace_file, harness_root),
            }
        )
    for repo_id in catalog.workspace_repo_names(workspace):
        repo = catalog.repo(repo_id)
        folders.append(
            {
                "name": repo.name,
                "path": _rel(workspace_file, catalog.repo_path(harness_root, repo)),
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
    if workspace.include_harness:
        settings.update(terminal_env_settings(folder_name=HARNESS_FOLDER_NAME))
    return {
        "folders": folders,
        "settings": settings,
        "extensions": {
            "recommendations": [
                "GitHub.copilot",
                "GitHub.copilot-chat",
            ]
        },
    }


def write_workspace_file(
    catalog: Catalog, harness_root: Path, workspace: Workspace
) -> dict[str, Any]:
    path = catalog.workspace_file(harness_root, workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = workspace_document(catalog, harness_root, workspace)
    if workspace.personal:
        document["harness"] = {
            "id": workspace.id,
            "name": workspace.name,
            "description": workspace.description,
            "personal": True,
            "folders": catalog.workspace_repo_names(workspace),
            "tags": workspace.tags,
            "include_harness": workspace.include_harness,
        }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return {
        "id": workspace.id,
        "name": workspace.name,
        "personal": workspace.personal,
        "file": str(path),
        "folders": [folder["name"] for folder in document["folders"]],
    }


def generate_workspaces(catalog: Catalog, harness_root: Path) -> list[dict[str, Any]]:
    return [
        write_workspace_file(catalog, harness_root, workspace)
        for workspace in catalog.workspaces
        if not workspace.personal
    ]


def list_workspaces(catalog: Catalog, harness_root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for workspace in catalog.workspaces:
        path = catalog.workspace_file(harness_root, workspace)
        repos = []
        for repo_id in catalog.workspace_repo_names(workspace):
            repo_path = catalog.repo_path(harness_root, repo_id)
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
                "personal": workspace.personal,
                "file": str(path),
                "exists": path.exists(),
                "repos": repos,
            }
        )
    return result


def open_command(workspace_file: Path) -> str:
    return f"code {workspace_file}"


def open_workspace(workspace_file: Path) -> dict[str, Any]:
    if not workspace_file.exists():
        raise HarnessError(
            f"Workspace file missing: {workspace_file}. Run `harness workspace generate`."
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

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from harness.catalog import load_catalog
from harness.http import HttpResponse


def write_yaml(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def write_harness_config(root: Path, data: dict) -> Path:
    """Write repositories.yml + catalog/stack.yaml from the combined test fixture."""
    repo_items = data.get("repositories") or data.get("repos") or []
    repositories = []
    for item in repo_items:
        repositories.append(
            {
                "name": item.get("name") or item.get("id"),
                "url": item.get("url") or item.get("clone_url"),
                "path": item.get("path"),
                "group": item.get("group"),
                "default_branch": item.get("default_branch") or item.get("branch"),
                "description": item.get("description") or "",
                "tags": item.get("tags") or ["untagged"],
                "enabled": item.get("enabled", True),
            }
        )
        if item.get("graphify") is not None:
            repositories[-1]["graphify"] = item["graphify"]
        if item.get("start") is not None:
            repositories[-1]["start"] = item["start"]
        if repositories[-1]["path"] is None:
            repositories[-1].pop("path")
        if repositories[-1]["group"] is None:
            repositories[-1].pop("group")
        if repositories[-1]["default_branch"] is None:
            repositories[-1].pop("default_branch")
    write_yaml(
        root / "repositories.yml",
        {
            "parent_dir": data.get("parent_dir", ".."),
            "repositories": repositories,
        },
    )
    stack = {key: data[key] for key in ("workspaces", "jira") if key in data}
    write_yaml(root / "catalog" / "stack.yaml", stack)
    if "templates" in data:
        write_yaml(root / "templates.yml", {"templates": data["templates"]})
    return root


def load_test_catalog(root: Path):
    return load_catalog(root)


class FakeHttp:
    def __init__(self, routes: dict[tuple[str, str], HttpResponse]):
        self.routes = routes
        self.calls: list[tuple[str, str]] = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        key = (method.upper(), url.split("?", 1)[0])
        if key not in self.routes:
            raise AssertionError(f"Unexpected request {key}")
        return self.routes[key]


def json_response(payload: Any, status: int = 200) -> HttpResponse:
    return HttpResponse(status=status, body=json.dumps(payload), headers={})

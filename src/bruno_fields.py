"""Config-driven allowlist for Copilot-facing Bruno payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from goat.projection import ProjectionSpec, project

DEFAULT_TAGS = ("bruno",)
DEFAULT_ENV = "local"
DEFAULT_WORKFLOWS_FILE = "goat.workflows.yml"
DEFAULT_SERVICES_FILE = "goat.services.yml"
LEGACY_WORKFLOWS_FILE = "coboose.workflows.yml"
LEGACY_SERVICES_FILE = "coboose.services.yml"

DEFAULT_OUTPUT_FIELDS = [
    "kind",
    "bru_cli",
    "default_env",
    "repos",
    "collections",
    "services",
    "workflows",
    "requests",
    "environments",
    "missing_repos",
    "clone_command",
    "note",
    "dry_run",
    "cwd",
    "collection",
    "request",
    "env",
    "env_var_keys",
    "bru_command",
    "exit_code",
    "stdout",
    "stderr",
]

DEFAULT_SHAPES: dict[str, tuple[str, ...]] = {
    "bru_cli": ("present", "path"),
    "repos": ("name", "path", "cloned", "placeholder", "collections"),
    "collections": (
        "id",
        "name",
        "repo",
        "path",
        "relpath",
        "request_count",
        "environments",
        "folders",
    ),
    "services": ("id", "collection", "env", "description", "repo"),
    "workflows": (
        "id",
        "description",
        "env",
        "service",
        "collection",
        "repo",
        "steps",
    ),
    "requests": (
        "id",
        "name",
        "method",
        "url",
        "path",
        "collection",
        "seq",
        "docs",
        "folder",
    ),
    "environments": ("name", "path", "collection", "vars", "secrets"),
    "steps": ("id", "request", "pick", "needs", "env_vars", "env", "bru_command"),
    "missing_repos": ("id", "path"),
}

REQUEST_TEMPLATE = """meta {
  name: Example request
  type: http
  seq: 1
}

get {
  url: {{baseUrl}}/path
}

headers {
  Content-Type: application/json
}

body:json {
  {
    "example": true
  }
}

docs {
  What this request is for. Keep secrets in environments, not here.
}
"""

INVENTORY_NOTE = (
    "bru run executes HTTP from a collection root. goat only resolves "
    "the sibling path, collection cwd, and --env. Workflows are a plan — "
    "Copilot picks values between steps and passes them as --env-var."
)


def _copy_shapes(
    source: dict[str, tuple[str, ...] | list[str]] | None = None,
) -> dict[str, list[str]]:
    items = source if source is not None else DEFAULT_SHAPES
    return {key: list(value) for key, value in items.items()}


@dataclass(frozen=True)
class BrunoService:
    id: str
    collection: str = ""
    env: str = ""
    description: str = ""
    repo: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "collection": self.collection,
            "env": self.env,
            "description": self.description,
            "repo": self.repo,
        }


@dataclass(frozen=True)
class BrunoSettings:
    repos: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=lambda: list(DEFAULT_TAGS))
    default_env: str = DEFAULT_ENV
    workflows_file: str = DEFAULT_WORKFLOWS_FILE
    services_file: str = DEFAULT_SERVICES_FILE
    services: list[BrunoService] = field(default_factory=list)
    fields: list[str] = field(default_factory=lambda: list(DEFAULT_OUTPUT_FIELDS))
    shapes: dict[str, list[str]] = field(default_factory=_copy_shapes)
    drop_empty: bool = True

    def output_fields(self) -> list[str]:
        names = list(self.fields or DEFAULT_OUTPUT_FIELDS)
        if "kind" not in names:
            names.insert(0, "kind")
        return names

    def projection(self) -> ProjectionSpec:
        return ProjectionSpec(
            name="bruno",
            fields=tuple(self.output_fields()),
            shapes={key: tuple(value) for key, value in self.shapes.items()},
            drop_empty=self.drop_empty,
        )

    def schema(self) -> dict[str, Any]:
        return {
            "repos": list(self.repos),
            "tags": list(self.tags),
            "default_env": self.default_env,
            "workflows_file": self.workflows_file,
            "services_file": self.services_file,
            "services": [item.as_dict() for item in self.services],
            "fields": self.output_fields(),
            "shapes": {key: list(value) for key, value in self.shapes.items()},
            "drop_empty": self.drop_empty,
            "request_template": REQUEST_TEMPLATE,
            "note": INVENTORY_NOTE,
        }


def project_bruno(payload: dict[str, Any], settings: BrunoSettings) -> dict[str, Any]:
    """Keep only configured output fields. Never pass raw environment values through."""
    return project(payload, settings.projection())

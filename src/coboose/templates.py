from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from coboose import CobooseError
from coboose.catalog import Repo, as_list, read_yaml
from coboose.paths import TEMPLATES_RELATIVE


@dataclass(frozen=True)
class Template:
    name: str
    url: str
    tags: list[str] = field(default_factory=list)
    description: str = ""
    language: str = ""
    kind: str = ""
    default_branch: str = "main"
    enabled: bool = True

    @property
    def id(self) -> str:
        return self.name

    @property
    def is_placeholder(self) -> bool:
        needle = self.url.lower()
        return "your_org" in needle or "example.com" in needle or "example/" in needle

    def as_repo(
        self,
        dest_name: str,
        *,
        path: str | None = None,
        group: str = "",
    ) -> Repo:
        return Repo(
            name=dest_name,
            url=self.url,
            path=path or dest_name,
            default_branch=self.default_branch,
            description=self.description,
            tags=list(self.tags),
            enabled=True,
            group=group,
        )


def load_templates(path: Path) -> list[Template]:
    if not path.exists():
        return []
    raw = read_yaml(path)
    items: list[Any]
    if raw is None:
        items = []
    elif isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        if raw.get("repositories") and not raw.get("templates"):
            raise CobooseError(
                f"{path} looks like {Path('repositories.yml')}. "
                f"Keep starter remotes under `templates:` in {TEMPLATES_RELATIVE}."
            )
        items = raw.get("templates") or raw.get("template_repositories") or []
    else:
        raise CobooseError(f"{path} must be a mapping or a list of templates")

    templates: list[Template] = []
    seen: set[str] = set()
    for item in items:
        template = _parse_template(item)
        if template.name in seen:
            raise CobooseError(f"Duplicate template name: {template.name}")
        seen.add(template.name)
        templates.append(template)
    return templates


def _parse_template(item: Any) -> Template:
    if not isinstance(item, dict):
        raise CobooseError("Each template entry must be a mapping")
    name = item.get("name") or item.get("id")
    url = item.get("url") or item.get("clone_url") or item.get("git")
    if not name or not url:
        raise CobooseError("Each template needs name and url (GitHub clone URL)")
    name = str(name)
    tags = as_list(item.get("tags"))
    if not tags:
        raise CobooseError(f"Template {name} needs at least one tag")
    return Template(
        name=name,
        url=str(url),
        tags=tags,
        description=str(item.get("description") or ""),
        language=str(item.get("language") or ""),
        kind=str(item.get("kind") or item.get("category") or ""),
        default_branch=str(item.get("default_branch") or item.get("branch") or "main"),
        enabled=bool(item.get("enabled", True)),
    )


def select_templates(
    templates: list[Template],
    *,
    only: list[str] | None = None,
    tags: list[str] | None = None,
    include_disabled: bool = False,
) -> list[Template]:
    selected = [item for item in templates if item.enabled or include_disabled]
    if only:
        wanted = set(only)
        known = {item.name for item in templates}
        unknown = wanted.difference(known)
        if unknown:
            raise CobooseError(
                "Unknown template name(s): "
                + ", ".join(sorted(unknown))
                + ". Run `coboose templates` to see the list."
            )
        selected = [item for item in selected if item.name in wanted]
    if tags:
        wanted = {tag.lower() for tag in tags}
        selected = [
            item
            for item in selected
            if wanted.intersection(tag.lower() for tag in item.tags)
        ]
    return selected


def get_template(templates: list[Template], name: str) -> Template:
    for item in templates:
        if item.name == name:
            return item
    raise CobooseError(
        f"Unknown template: {name}. Run `coboose templates` to see the list."
    )


def template_to_dict(template: Template) -> dict[str, Any]:
    return {
        "name": template.name,
        "url": template.url,
        "tags": list(template.tags),
        "description": template.description,
        "language": template.language,
        "kind": template.kind,
        "default_branch": template.default_branch,
        "enabled": template.enabled,
        "placeholder": template.is_placeholder,
    }


def templates_payload(
    templates: list[Template],
    source: Path,
    *,
    only: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    selected = select_templates(templates, only=only, tags=tags)
    return {
        "manifest": str(source),
        "count": len(selected),
        "templates": [template_to_dict(item) for item in selected],
    }

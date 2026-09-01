"""Language packs for TypeScript, Python, and Java.

Product style stays in sibling instruction files. Goat only maps a repo to
the matching first-party skill and path-scoped rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from goat.catalog import Repo

PACKS: tuple[dict[str, Any], ...] = (
    {
        "id": "typescript",
        "skill": "typescript",
        "skill_path": ".github/skills/typescript/SKILL.md",
        "instructions_path": ".github/instructions/typescript.instructions.md",
        "aliases": frozenset(
            {
                "typescript",
                "ts",
                "tsx",
                "angular",
                "analog",
                "react",
                "react-native",
                "expo",
            }
        ),
        "tags": frozenset(
            {
                "typescript",
                "ts",
                "angular",
                "analog",
                "react",
                "react-native",
                "expo",
            }
        ),
        "files": (
            "tsconfig.json",
            "angular.json",
            "nx.json",
        ),
        "markers": frozenset({"eslint", "pnpm-workspace", "nx", "turbo", "tsconfig"}),
    },
    {
        "id": "python",
        "skill": "python",
        "skill_path": ".github/skills/python/SKILL.md",
        "instructions_path": ".github/instructions/python.instructions.md",
        "aliases": frozenset({"python", "py", "django", "fastapi", "flask"}),
        "tags": frozenset({"python", "django", "fastapi", "flask"}),
        "files": (
            "pyproject.toml",
            "requirements.txt",
            "Pipfile",
            "manage.py",
            "pytest.ini",
        ),
        "markers": frozenset({"pyproject", "ruff"}),
    },
    {
        "id": "java",
        "skill": "java",
        "skill_path": ".github/skills/java/SKILL.md",
        "instructions_path": ".github/instructions/java.instructions.md",
        "aliases": frozenset({"java", "spring", "spring-boot"}),
        "tags": frozenset({"java", "spring"}),
        "files": (
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "mvnw",
            "gradlew",
        ),
        "markers": frozenset({"pom", "gradle", "gradle-kts", "mvnw", "gradlew"}),
    },
)

_BY_ID = {pack["id"]: pack for pack in PACKS}
_ALIAS_TO_ID = {
    alias: pack["id"] for pack in PACKS for alias in pack["aliases"]
}


def normalize_language(value: str | None) -> str | None:
    if not value:
        return None
    return _ALIAS_TO_ID.get(str(value).strip().lower())


def language_pack(language_id: str) -> dict[str, Any] | None:
    return _BY_ID.get(language_id)


def discover_languages(
    repo: Repo,
    repo_path: Path,
    *,
    cloned: bool,
    markers: list[str] | None = None,
) -> dict[str, Any]:
    """Return declared + inferred language packs for one repo."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    declared = normalize_language(repo.language)
    if declared:
        _append_language(found, seen, declared, source="declared")

    tag_hits = _languages_from_tags(repo.tags)
    for language_id in tag_hits:
        _append_language(found, seen, language_id, source="tags")

    if cloned:
        marker_set = {item.lower() for item in (markers or [])}
        for language_id in _languages_from_tree(repo_path, marker_set):
            source = "files"
            _append_language(found, seen, language_id, source=source)

    languages = found
    primary = languages[0] if languages else None
    return {
        "language": primary["id"] if primary else None,
        "languages": languages,
        "skill": primary["skill_path"] if primary else None,
    }


def _languages_from_tags(tags: list[str]) -> list[str]:
    hits: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        language_id = _ALIAS_TO_ID.get(str(tag).strip().lower())
        if language_id and language_id not in seen:
            seen.add(language_id)
            hits.append(language_id)
    return hits


def _languages_from_tree(repo_path: Path, markers: set[str]) -> list[str]:
    hits: list[str] = []
    seen: set[str] = set()
    for pack in PACKS:
        language_id = pack["id"]
        if language_id in seen:
            continue
        if any((repo_path / relative).is_file() for relative in pack["files"]):
            seen.add(language_id)
            hits.append(language_id)
            continue
        if markers & pack["markers"]:
            seen.add(language_id)
            hits.append(language_id)
    return hits


def _append_language(
    found: list[dict[str, Any]],
    seen: set[str],
    language_id: str,
    *,
    source: str,
) -> None:
    if language_id in seen:
        return
    pack = _BY_ID[language_id]
    seen.add(language_id)
    found.append(
        {
            "id": pack["id"],
            "source": source,
            "skill": pack["skill"],
            "skill_path": pack["skill_path"],
            "instructions_path": pack["instructions_path"],
        }
    )

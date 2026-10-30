from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from goat.catalog import Catalog, Repo
from goat.glossary import glossary_summary
from goat.skills import list_skills
from goat.workspace_detect import resolve_workspace_scope, scoped_repos

INSTRUCTION_FILES = (
    ".github/copilot-instructions.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
)

INSTRUCTION_GLOBS = (
    (".github/instructions", "*.instructions.md"),
    (".github/skills", "*/SKILL.md"),
    (".github/agents", "*.agent.md"),
)

KNOWLEDGE_DIRS = (
    ("docs/features", "feature"),
    ("docs/adr", "adr"),
    ("docs/adrs", "adr"),
    ("docs/decisions", "adr"),
    ("docs/architecture", "architecture"),
    ("docs/rfcs", "rfc"),
    ("adr", "adr"),
)

KNOWLEDGE_FILES = (
    ("ARCHITECTURE.md", "architecture"),
    ("docs/ARCHITECTURE.md", "architecture"),
    ("docs/README.md", "docs-index"),
)

KNOWLEDGE_FILE_LIMIT = 20
FEATURE_NOTE_TEMPLATE = "templates/feature-note.md"

PACKAGE_VERIFY_SCRIPTS = (
    "verify",
    "check",
    "lint",
    "test",
    "typecheck",
    "format",
    "fmt",
    "ci",
)

MAKE_VERIFY_TARGETS = ("verify", "check", "lint", "test", "format", "fmt", "ci")


def collect_context(
    catalog: Catalog,
    goat_root: Path,
    *,
    only: list[str] | None = None,
    workspace_id: str | None = None,
    all_repos: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    scope = resolve_workspace_scope(
        catalog,
        goat_root,
        workspace_id=workspace_id,
        all_repos=all_repos,
        environ=environ,
    )
    repos = []
    for repo in scoped_repos(catalog, scope, only=only):
        repos.append(inspect_repo(catalog, goat_root, repo))
    guidance = [
        "Stay inside workspace.repos. Do not inspect sibling clones that are "
        "only on disk and not in this feature workspace.",
        "Find code in this order: this payload names the repo and its instruction "
        "files; search/codebase finds candidate code; search/usages on the named "
        "symbol covers definitions, references, and implementations; then targeted "
        "reads with limit/offset. Use text search only for strings and config.",
        "Before editing a sibling repo, load its instruction files and use its tooling.",
        "Product knowledge lives in each sibling (docs/features, ADRs). "
        "Do not start a second wiki in the Goat repo.",
        "Do not copy product standards into the Goat repo. Do not open a whole "
        "monorepo as the first move.",
        "For cross-repo links use goat graph path and goat graph neighbors "
        "(docs/cli.md).",
        "Do not hand-edit tooling.generated paths.",
        "To start local apps in this workspace, run `goat start` "
        "(see the workspace-start skill). That command prints a plan; "
        "it does not launch processes. Save the sequence once with "
        "`goat start --save` when a workspace is detected.",
        "VS Code Agents does not scan multi-root child skills. Use "
        "`goat skills list` / `skills lift` (see the skills-install skill) "
        "to copy sibling or remote skills into this goat .github/skills.",
        "Unknown workplace words or acronyms: `goat glossary get TERM` "
        "(see the glossary skill). Do not guess team language.",
    ]
    if not scope.detected:
        guidance.insert(
            0,
            scope.detail,
        )
    return {
        "sibling_root": str(catalog.sibling_root(goat_root)),
        "workspace": scope.id,
        "workspace_scope": scope.as_payload(),
        "repos": repos,
        "skills": list_skills(
            catalog,
            goat_root,
            only=only,
            workspace_id=workspace_id,
            all_repos=all_repos,
            environ=environ,
        ),
        "glossary": glossary_summary(
            catalog,
            goat_root,
            only=only,
            workspace_id=workspace_id,
            all_repos=all_repos,
            environ=environ,
        ),
        "guidance": guidance,
    }


def inspect_repo(catalog: Catalog, goat_root: Path, repo: Repo | str) -> dict[str, Any]:
    if isinstance(repo, str):
        repo = catalog.repo(repo)
    path = catalog.repo_path(goat_root, repo)
    cloned = path.exists()
    return {
        "name": repo.name,
        "id": repo.name,
        "path": str(path),
        "relpath": repo.path,
        "group": repo.group,
        "cloned": cloned,
        "placeholder": repo.is_placeholder,
        "tags": repo.tags,
        "instructions": discover_instructions(path) if cloned else [],
        "knowledge": discover_knowledge(path, extra_dirs=repo.knowledge_dirs) if cloned else _empty_knowledge(),
        "tooling": discover_tooling(path) if cloned else _empty_tooling(),
        "env_example": discover_env_example(path) if cloned else None,
    }


def discover_instructions(repo_path: Path) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for relative in INSTRUCTION_FILES:
        path = repo_path / relative
        if path.is_file():
            found.append({"path": str(path), "kind": _instruction_kind(relative)})
            seen.add(str(path))
    for directory, pattern in INSTRUCTION_GLOBS:
        root = repo_path / directory
        if not root.is_dir():
            continue
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or str(path) in seen:
                continue
            found.append({"path": str(path), "kind": _instruction_kind(str(path.relative_to(repo_path)))})
            seen.add(str(path))
    return found


def discover_knowledge(
    repo_path: Path, *, extra_dirs: tuple[str, ...] | list[str] = ()
) -> dict[str, Any]:
    dirs: list[dict[str, Any]] = []
    files: list[dict[str, str]] = []
    seen_roots: set[str] = set()
    search = list(KNOWLEDGE_DIRS)
    for relative in extra_dirs:
        search.append((relative, "custom"))
    for relative, kind in search:
        root = repo_path / relative
        if not root.is_dir() or str(root) in seen_roots:
            continue
        seen_roots.add(str(root))
        matches = sorted(
            path
            for path in root.glob("*.md")
            if path.is_file() and path.name.lower() != "readme.md"
        )
        dirs.append(
            {
                "path": str(root),
                "kind": kind,
                "count": len(matches),
            }
        )
        for path in matches:
            if len(files) >= KNOWLEDGE_FILE_LIMIT:
                break
            files.append({"path": str(path), "kind": kind, "name": path.name})
    for relative, kind in KNOWLEDGE_FILES:
        path = repo_path / relative
        if path.is_file() and not any(item["path"] == str(path) for item in files):
            files.append({"path": str(path), "kind": kind, "name": path.name})
    return {
        "dirs": dirs,
        "files": files,
        "template": FEATURE_NOTE_TEMPLATE,
        "write_hint": (
            "Keep feature notes and ADRs in this sibling repo. "
            f"Use the Goat {FEATURE_NOTE_TEMPLATE} template. "
            "Do not copy product knowledge into the Goat repo."
        ),
    }


def discover_tooling(repo_path: Path) -> dict[str, Any]:
    package_scripts = _package_scripts(repo_path)
    make_targets = _make_targets(repo_path)
    markers = [
        name
        for name, relative in (
            ("package.json", "package.json"),
            ("pnpm-workspace", "pnpm-workspace.yaml"),
            ("nx", "nx.json"),
            ("turbo", "turbo.json"),
            ("makefile", "Makefile"),
            ("justfile", "justfile"),
            ("pyproject", "pyproject.toml"),
            ("pre-commit", ".pre-commit-config.yaml"),
            ("ruff", "ruff.toml"),
            ("eslint", "eslint.config.js"),
        )
        if (repo_path / relative).exists() or (repo_path / relative.replace(".js", ".mjs")).exists()
    ]
    if (repo_path / "eslint.config.mjs").exists() and "eslint" not in markers:
        markers.append("eslint")
    verify = _suggested_verify(package_scripts, make_targets, repo_path)
    generated = discover_generated(repo_path)
    return {
        "markers": markers,
        "package_scripts": package_scripts,
        "make_targets": make_targets,
        "suggested_verify": verify,
        "generated": generated,
    }


def _empty_tooling() -> dict[str, Any]:
    return {
        "markers": [],
        "package_scripts": [],
        "make_targets": [],
        "suggested_verify": [],
        "generated": {"markers": [], "paths": [], "hint": None},
    }


def _empty_knowledge() -> dict[str, Any]:
    return {
        "dirs": [],
        "files": [],
        "template": FEATURE_NOTE_TEMPLATE,
        "write_hint": (
            "Keep feature notes and ADRs in this sibling repo. "
            f"Use the Goat {FEATURE_NOTE_TEMPLATE} template. "
            "Do not copy product knowledge into the Goat repo."
        ),
    }


GENERATED_MARKERS = (
    ("nx.json", "nx"),
    ("project.json", "nx"),
    ("openapitools.json", "openapi"),
    ("openapi-generator-config.yaml", "openapi"),
    ("openapi-generator-config.yml", "openapi"),
    ("graphql-codegen.yml", "graphql-codegen"),
    ("graphql-codegen.yaml", "graphql-codegen"),
    ("codegen.yml", "graphql-codegen"),
    ("codegen.ts", "graphql-codegen"),
    ("codegen.cjs", "graphql-codegen"),
)

GENERATED_DIRS = (
    "generated",
    "src/generated",
    "src/gen",
    "libs/api-client",
    ".nx",
)


def discover_generated(repo_path: Path) -> dict[str, Any]:
    markers: list[str] = []
    for relative, kind in GENERATED_MARKERS:
        if (repo_path / relative).exists() and kind not in markers:
            markers.append(kind)
    paths = [
        relative
        for relative in GENERATED_DIRS
        if (repo_path / relative).exists()
    ]
    hint = None
    if markers or paths:
        hint = (
            "Do not hand-edit generated outputs. Regenerate them with the "
            "repo's codegen / Nx / OpenAPI command."
        )
    return {"markers": markers, "paths": paths, "hint": hint}


def discover_env_example(repo_path: Path) -> dict[str, Any] | None:
    for relative in (".env.example", ".env.sample", ".env.template"):
        path = repo_path / relative
        if path.is_file():
            return {
                "path": str(path),
                "hint": (
                    "This sibling has its own env template. Copy it locally "
                    "in that repo. Never read or print the filled values."
                ),
            }
    return None


def _instruction_kind(relative: str) -> str:
    if relative.endswith("copilot-instructions.md"):
        return "copilot"
    if relative.endswith("AGENTS.md"):
        return "agents"
    if relative.endswith(".instructions.md"):
        return "path-instructions"
    if relative.endswith("SKILL.md"):
        return "skill"
    if relative.endswith(".agent.md"):
        return "agent"
    return "docs"


def _package_scripts(repo_path: Path) -> list[str]:
    package = repo_path / "package.json"
    if not package.is_file():
        return []
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return []
    return [name for name in PACKAGE_VERIFY_SCRIPTS if name in scripts]


def _make_targets(repo_path: Path) -> list[str]:
    makefile = repo_path / "Makefile"
    if not makefile.is_file():
        return []
    found: list[str] = []
    for raw in makefile.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("\t") or raw.startswith("#") or ":" not in raw:
            continue
        target = raw.split(":", 1)[0].strip()
        if target in MAKE_VERIFY_TARGETS and target not in found:
            found.append(target)
    return found


def _suggested_verify(
    package_scripts: list[str],
    make_targets: list[str],
    repo_path: Path,
) -> list[str]:
    commands: list[str] = []
    if "verify" in make_targets:
        commands.append("make verify")
    elif "check" in make_targets:
        commands.append("make check")
    else:
        commands.extend(f"make {name}" for name in make_targets if name in ("lint", "test", "format"))
    if package_scripts:
        runner = _js_runner(repo_path)
        if "verify" in package_scripts:
            commands.append(f"{runner} verify")
        elif "check" in package_scripts:
            commands.append(f"{runner} check")
        else:
            commands.extend(
                f"{runner} {name}"
                for name in package_scripts
                if name in ("lint", "test", "typecheck", "format")
            )
    if (repo_path / "pyproject.toml").exists() and not commands:
        commands.append("uv run pytest")
    return commands


def _js_runner(repo_path: Path) -> str:
    if (repo_path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_path / "yarn.lock").exists():
        return "yarn"
    if (repo_path / "bun.lockb").exists() or (repo_path / "bun.lock").exists():
        return "bun run"
    return "npm run"

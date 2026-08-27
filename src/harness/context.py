from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.catalog import Catalog, Repo

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
    harness_root: Path,
    *,
    only: list[str] | None = None,
) -> dict[str, Any]:
    repos = []
    for repo in catalog.enabled_repos(only=only):
        repos.append(inspect_repo(catalog, harness_root, repo))
    return {
        "sibling_root": str(catalog.sibling_root(harness_root)),
        "repos": repos,
        "guidance": [
            "For vague or low-context prompts, read each cloned repo's graphify.report "
            "before grepping the tree.",
            "Before editing a sibling repo, load its instruction files and use its tooling.",
            "Product knowledge lives in each sibling (docs/features, ADRs, Graphify). "
            "Do not start a second wiki in the harness.",
            "Do not copy product standards into the harness. Do not rebuild a graph "
            "unless the user asked.",
        ],
    }


def inspect_repo(catalog: Catalog, harness_root: Path, repo: Repo | str) -> dict[str, Any]:
    if isinstance(repo, str):
        repo = catalog.repo(repo)
    path = catalog.repo_path(harness_root, repo)
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
        "graphify": discover_graphify(path, repo) if cloned else _empty_graphify(repo, cloned=False),
        "instructions": discover_instructions(path) if cloned else [],
        "knowledge": discover_knowledge(path) if cloned else _empty_knowledge(),
        "tooling": discover_tooling(path) if cloned else _empty_tooling(),
    }


def discover_graphify(repo_path: Path, repo: Repo) -> dict[str, Any]:
    payload = _empty_graphify(repo)
    if not repo.graphify.enabled:
        return payload
    out_dir = repo_path / repo.graphify.out
    payload["out_dir"] = str(out_dir)
    if not out_dir.is_dir():
        payload["detail"] = f"{repo.graphify.out}/ is not present"
        return payload

    report = out_dir / "GRAPH_REPORT.md"
    graph = out_dir / "graph.json"
    html = out_dir / "graph.html"
    payload.update(
        {
            "present": True,
            "report": str(report) if report.is_file() else None,
            "graph": str(graph) if graph.is_file() else None,
            "html": str(html) if html.is_file() else None,
            "updated_at": _mtime(graph if graph.is_file() else out_dir),
            "query_command": (
                f'graphify query --graph "{graph}" "<question>"' if graph.is_file() else None
            ),
            "path_command": (
                f'graphify path --graph "{graph}" "<from>" "<to>"' if graph.is_file() else None
            ),
            "explain_command": (
                f'graphify explain --graph "{graph}" "<concept>"' if graph.is_file() else None
            ),
            "detail": "graph is available",
        }
    )
    return payload


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


def discover_knowledge(repo_path: Path) -> dict[str, Any]:
    dirs: list[dict[str, Any]] = []
    files: list[dict[str, str]] = []
    for relative, kind in KNOWLEDGE_DIRS:
        root = repo_path / relative
        if not root.is_dir():
            continue
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
            f"Use the harness {FEATURE_NOTE_TEMPLATE} template. "
            "Do not copy product knowledge into the harness."
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
    return {
        "markers": markers,
        "package_scripts": package_scripts,
        "make_targets": make_targets,
        "suggested_verify": verify,
    }


def _empty_graphify(repo: Repo, *, cloned: bool = True) -> dict[str, Any]:
    if not repo.graphify.enabled:
        detail = "disabled in repositories.yml"
    elif not cloned:
        detail = "repo is not cloned"
    else:
        detail = "graph not found"
    return {
        "enabled": repo.graphify.enabled,
        "present": False,
        "out_dir": None,
        "report": None,
        "graph": None,
        "html": None,
        "updated_at": None,
        "query_command": None,
        "path_command": None,
        "explain_command": None,
        "detail": detail,
    }


def _empty_tooling() -> dict[str, Any]:
    return {
        "markers": [],
        "package_scripts": [],
        "make_targets": [],
        "suggested_verify": [],
    }


def _empty_knowledge() -> dict[str, Any]:
    return {
        "dirs": [],
        "files": [],
        "template": FEATURE_NOTE_TEMPLATE,
        "write_hint": (
            "Keep feature notes and ADRs in this sibling repo. "
            f"Use the harness {FEATURE_NOTE_TEMPLATE} template. "
            "Do not copy product knowledge into the harness."
        ),
    }


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


def _mtime(path: Path) -> str:
    stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return stamp.isoformat()

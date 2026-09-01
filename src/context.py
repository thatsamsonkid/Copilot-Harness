from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from goat.catalog import Catalog, Repo
from goat.gitinfo import last_commit_unix
from goat.languages import discover_languages
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
        "For vague or low-context prompts, read each cloned repo's graphify.report "
        "before grepping the tree.",
        "Before editing a sibling repo, load its instruction files, the matching "
        "language skill (languages[].skill_path), and use its tooling.",
        "Product knowledge lives in each sibling (docs/features, ADRs, Graphify). "
        "Do not start a second wiki in the Goat repo.",
        "Do not copy product standards into the Goat repo. Do not rebuild a graph "
        "unless the user asked.",
        "If graphify.stale is true, offer a scoped refresh in that repo after the user agrees.",
        "Do not hand-edit tooling.generated paths.",
        "To start local apps in this workspace, run `goat start` "
        "(see the workspace-start skill). That command prints a plan; "
        "it does not launch processes. Save the sequence once with "
        "`goat start --save` when a workspace is detected.",
        "VS Code Agents does not scan multi-root child skills. Use "
        "`goat skills list` / `skills lift` (see the skills-install skill) "
        "to copy sibling or remote skills into this goat .github/skills.",
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
        "guidance": guidance,
    }


def inspect_repo(catalog: Catalog, goat_root: Path, repo: Repo | str) -> dict[str, Any]:
    if isinstance(repo, str):
        repo = catalog.repo(repo)
    path = catalog.repo_path(goat_root, repo)
    cloned = path.exists()
    tooling = discover_tooling(path) if cloned else _empty_tooling()
    languages = discover_languages(
        repo,
        path,
        cloned=cloned,
        markers=tooling.get("markers"),
    )
    return {
        "name": repo.name,
        "id": repo.name,
        "path": str(path),
        "relpath": repo.path,
        "group": repo.group,
        "cloned": cloned,
        "placeholder": repo.is_placeholder,
        "tags": repo.tags,
        "language": languages["language"],
        "languages": languages["languages"],
        "language_skill": languages["skill"],
        "graphify": discover_graphify(path, repo) if cloned else _empty_graphify(repo, cloned=False),
        "instructions": discover_instructions(path) if cloned else [],
        "knowledge": discover_knowledge(path, extra_dirs=repo.knowledge_dirs) if cloned else _empty_knowledge(),
        "tooling": tooling,
        "env_example": discover_env_example(path) if cloned else None,
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
    payload.update(_graphify_freshness(repo_path, graph if graph.is_file() else None))
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
            ("tsconfig", "tsconfig.json"),
            ("pom", "pom.xml"),
            ("gradle", "build.gradle"),
            ("gradle-kts", "build.gradle.kts"),
            ("mvnw", "mvnw"),
            ("gradlew", "gradlew"),
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
        "stale": None,
        "stale_detail": None,
        "detail": detail,
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


def _graphify_freshness(repo_path: Path, graph: Path | None) -> dict[str, Any]:
    if graph is None or not graph.is_file():
        return {"stale": None, "stale_detail": None}
    graph_mtime = int(graph.stat().st_mtime)
    commit_unix = last_commit_unix(repo_path)
    if commit_unix is None:
        return {"stale": None, "stale_detail": "no git history to compare"}
    stale = commit_unix > graph_mtime + 60
    return {
        "stale": stale,
        "stale_detail": (
            "graph.json is older than the latest commit"
            if stale
            else "graph.json is at least as new as the latest commit"
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
    if not commands:
        commands.extend(_language_verify(repo_path))
    return commands


def _language_verify(repo_path: Path) -> list[str]:
    if (repo_path / "pyproject.toml").exists():
        return ["uv run pytest"]
    if (repo_path / "mvnw").is_file() or (repo_path / "mvnw.cmd").is_file():
        return ["./mvnw test"]
    if (repo_path / "pom.xml").is_file():
        return ["mvn test"]
    if (repo_path / "gradlew").is_file() or (repo_path / "gradlew.bat").is_file():
        return ["./gradlew test"]
    if (repo_path / "build.gradle").is_file() or (repo_path / "build.gradle.kts").is_file():
        return ["gradle test"]
    if (repo_path / "manage.py").is_file() or (repo_path / "pytest.ini").is_file():
        return ["pytest"]
    return []


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

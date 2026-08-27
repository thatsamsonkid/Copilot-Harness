from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from harness import HarnessError
from harness.catalog import Catalog, Repo, StartConfig

PACKAGE_START_SCRIPTS = ("start", "serve", "dev")
MAKE_START_TARGETS = ("start", "run", "serve", "dev", "up", "bootrun")

FRONTEND_TAGS = {"ui", "frontend", "web", "angular", "react", "vue"}
BACKEND_TAGS = {"api", "backend", "service", "java", "spring"}
INFRA_TAGS = {"infra", "devops", "ops"}
MOBILE_TAGS = {"mobile", "ios", "android"}

ROLE_ORDER = {"infra": 0, "backend": 1, "worker": 2, "frontend": 3, "mobile": 4}

PROXY_FILENAMES = (
    "proxy.conf.json",
    "proxy.conf.js",
    "proxy.conf.mjs",
    "proxy.conf.cjs",
    "proxy.conf.cts",
    "src/proxy.conf.json",
    "src/proxy.conf.js",
)

COMPOSE_FILENAMES = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
)

_PORT_IN_SCRIPT = re.compile(
    r"(?i)(?:--port|-p)\s*[= ]\s*(\d{2,5})"
)
_SERVER_PORT_FLAT = re.compile(
    r"(?im)^\s*server\.port\s*[:=]\s*(?:\$\{[^:\n]+:)?(\d{2,5})"
)
_SERVER_PORT_PROP = re.compile(
    r"(?im)^\s*server\.port\s*=\s*(?:\$\{[^:\n]+:)?(\d{2,5})"
)


def collect_start_plan(
    catalog: Catalog,
    harness_root: Path,
    *,
    workspace_id: str | None = None,
    only: list[str] | None = None,
) -> dict[str, Any]:
    repos = _selected_repos(catalog, workspace_id=workspace_id, only=only)
    services = [inspect_start(catalog, harness_root, repo) for repo in repos]
    backends = [item["name"] for item in services if item.get("role") == "backend"]
    for item in services:
        if item.get("role") in {"frontend", "mobile"} and backends:
            item["depends_on"] = list(backends)
        else:
            item.setdefault("depends_on", [])
    services.sort(key=_service_sort_key)
    blocked = [item for item in services if item.get("blocked")]
    return {
        "workspace": workspace_id,
        "sibling_root": str(catalog.sibling_root(harness_root)),
        "order": [item["name"] for item in services],
        "services": services,
        "blocked": [
            {"name": item["name"], "reason": item.get("blocked")} for item in blocked
        ],
        "guidance": [
            "This command prints a plan. It does not start processes.",
            "Start backends (and infra) first, one at a time. Wait until the "
            "process is listening before starting frontends.",
            "If port_hint is missing or the app binds a different port, read the "
            "startup logs and use the live port.",
            "Rewrite Angular proxy targets to the live backend URL in the sibling "
            "working tree. Do not commit that change unless the user asked.",
            "Optional repositories.yml start: {command, port, role, wait} overrides "
            "discovery when it is wrong.",
        ],
    }


def inspect_start(catalog: Catalog, harness_root: Path, repo: Repo | str) -> dict[str, Any]:
    if isinstance(repo, str):
        repo = catalog.repo(repo)
    path = catalog.repo_path(harness_root, repo)
    payload = _empty_service(repo, path)
    if not path.exists():
        payload["blocked"] = "repo is not cloned"
        payload["notes"].append("Clone this repo before starting it.")
        return payload

    discovered = discover_start(path, repo)
    merged = _apply_override(discovered, repo.start)
    payload.update(merged)
    if not payload.get("command"):
        payload["blocked"] = "no start command found"
        payload["notes"].append(
            "Add repositories.yml start.command or a start/serve/dev script."
        )
    elif payload.get("role") == "infra" and payload.get("kind") == "compose":
        payload["notes"].append(
            "Do not start docker compose unless the user asked for the local stack."
        )
    if payload.get("proxies") and payload.get("role") == "frontend":
        payload["notes"].append(
            "Update proxy targets after backend ports are known, then start this app."
        )
    if payload.get("port_hint") is None and payload.get("command"):
        payload["notes"].append(
            "Port is unknown until the process starts. Read the startup logs."
        )
    return payload


def discover_start(repo_path: Path, repo: Repo) -> dict[str, Any]:
    markers = _markers(repo_path)
    package_scripts = _all_package_scripts(repo_path)
    make_targets = _make_start_targets(repo_path)
    kind, role_from_kind = _detect_kind(repo_path, markers, package_scripts)
    role = role_from_kind or _role_from_tags(repo.tags) or "unknown"
    command, command_source = _detect_command(
        repo_path, kind, package_scripts, make_targets
    )
    port_hint, port_source = _detect_port(repo_path, kind, package_scripts)
    proxies = _detect_proxies(repo_path, kind)
    compose = _compose_files(repo_path)
    confidence = _confidence(kind, command, port_hint, repo.start)
    notes: list[str] = []
    if compose and kind != "compose":
        notes.append(
            "Compose file present; start it only if this service needs those containers."
        )
    return {
        "cloned": True,
        "kind": kind,
        "role": role,
        "confidence": confidence,
        "source": "discovered",
        "command": command,
        "command_source": command_source,
        "cwd": str(repo_path),
        "port_hint": port_hint,
        "port_source": port_source,
        "wait": _default_wait(port_hint),
        "proxies": proxies,
        "compose": compose,
        "markers": markers,
        "notes": notes,
        "blocked": None,
    }


def _selected_repos(
    catalog: Catalog,
    *,
    workspace_id: str | None,
    only: list[str] | None,
) -> list[Repo]:
    names: list[str] | None = None
    if workspace_id:
        names = catalog.workspace_repo_names(workspace_id)
    if only:
        wanted = set(only)
        if names is None:
            return catalog.enabled_repos(only=only)
        unknown = wanted.difference(repo.name for repo in catalog.repos)
        if unknown:
            raise HarnessError("Unknown repo name(s): " + ", ".join(sorted(unknown)))
        names = [name for name in names if name in wanted]
    if names is None:
        return catalog.enabled_repos()
    return [catalog.repo(name) for name in names if catalog.repo(name).enabled]


def _empty_service(repo: Repo, path: Path) -> dict[str, Any]:
    return {
        "name": repo.name,
        "id": repo.name,
        "path": str(path),
        "relpath": repo.path,
        "group": repo.group,
        "tags": list(repo.tags),
        "cloned": False,
        "kind": "unknown",
        "role": _role_from_tags(repo.tags) or "unknown",
        "confidence": "none",
        "source": "none",
        "command": None,
        "command_source": None,
        "cwd": str(path),
        "port_hint": None,
        "port_source": None,
        "wait": None,
        "depends_on": [],
        "proxies": [],
        "compose": [],
        "markers": [],
        "notes": [],
        "blocked": None,
        "override": repo.start.to_dict(),
    }


def _apply_override(discovered: dict[str, Any], override: StartConfig) -> dict[str, Any]:
    if not override.configured():
        return discovered
    merged = dict(discovered)
    merged["source"] = "override"
    merged["confidence"] = "high"
    if override.command:
        merged["command"] = override.command
        merged["command_source"] = "repositories.yml start.command"
    if override.port:
        merged["port_hint"] = override.port
        merged["port_source"] = "repositories.yml start.port"
        merged["wait"] = override.wait or _default_wait(override.port)
    elif override.wait:
        merged["wait"] = override.wait
    if override.role:
        merged["role"] = override.role
    if override.cwd:
        merged["cwd"] = str(Path(merged["cwd"]) / override.cwd)
    return merged


def _markers(repo_path: Path) -> list[str]:
    names = [
        ("angular", "angular.json"),
        ("package.json", "package.json"),
        ("pom", "pom.xml"),
        ("gradle", "build.gradle"),
        ("gradle-kts", "build.gradle.kts"),
        ("makefile", "Makefile"),
        ("pyproject", "pyproject.toml"),
        ("manage.py", "manage.py"),
        ("mvnw", "mvnw"),
        ("gradlew", "gradlew"),
    ]
    found = [name for name, relative in names if (repo_path / relative).exists()]
    if any((repo_path / name).exists() for name in COMPOSE_FILENAMES) and "compose" not in found:
        found.append("compose")
    return found


def _detect_kind(
    repo_path: Path, markers: list[str], package_scripts: dict[str, str]
) -> tuple[str, str | None]:
    if "angular" in markers:
        return "angular", "frontend"
    if _is_spring_boot(repo_path):
        return "spring-boot", "backend"
    if "manage.py" in markers:
        return "django", "backend"
    if _looks_like_python_web(repo_path):
        return "python", "backend"
    if "package.json" in markers:
        role = "frontend" if _js_looks_frontend(package_scripts) else None
        return "node", role
    if "compose" in markers and not {"pom", "gradle", "gradle-kts", "pyproject"} & set(markers):
        return "compose", "infra"
    if "makefile" in markers:
        return "make", None
    return "unknown", None


def _detect_command(
    repo_path: Path,
    kind: str,
    package_scripts: dict[str, str],
    make_targets: list[str],
) -> tuple[str | None, str | None]:
    if kind == "spring-boot":
        if (repo_path / "mvnw").is_file() or (repo_path / "mvnw.cmd").is_file():
            return "./mvnw spring-boot:run", "mvnw"
        if (repo_path / "gradlew").is_file() or (repo_path / "gradlew.bat").is_file():
            return "./gradlew bootRun", "gradlew"
        if (repo_path / "pom.xml").is_file():
            return "mvn spring-boot:run", "pom.xml"
        if (repo_path / "build.gradle").is_file() or (repo_path / "build.gradle.kts").is_file():
            return "gradle bootRun", "build.gradle"
    if kind == "django":
        return "python manage.py runserver", "manage.py"
    if kind == "compose":
        compose = _compose_files(repo_path)
        filename = Path(compose[0]).name if compose else "compose.yaml"
        return f"docker compose -f {filename} up", filename
    if package_scripts:
        runner = _js_runner(repo_path)
        for name in PACKAGE_START_SCRIPTS:
            if name in package_scripts:
                return f"{runner} {name}", f"package.json scripts.{name}"
    if make_targets:
        preferred = next(
            (name for name in ("start", "run", "serve", "dev", "up") if name in make_targets),
            make_targets[0],
        )
        return f"make {preferred}", f"Makefile {preferred}"
    if kind == "python":
        return None, None
    return None, None


def _detect_port(
    repo_path: Path, kind: str, package_scripts: dict[str, str]
) -> tuple[int | None, str | None]:
    if kind == "angular":
        port, source = _angular_serve_port(repo_path)
        if port:
            return port, source
        script_port = _port_from_scripts(package_scripts)
        if script_port:
            return script_port
        return 4200, "angular default"
    if kind == "spring-boot":
        found = _spring_port(repo_path)
        if found:
            return found
        return 8080, "spring-boot default"
    if kind == "django":
        script_port = _port_from_scripts(package_scripts)
        return script_port if script_port else (8000, "django default")
    script_port = _port_from_scripts(package_scripts)
    if script_port:
        return script_port
    return None, None


def _detect_proxies(repo_path: Path, kind: str) -> list[dict[str, Any]]:
    paths: list[Path] = []
    seen: set[str] = set()
    configured = _angular_proxy_files(repo_path) if kind == "angular" else []
    for relative in [*configured, *PROXY_FILENAMES]:
        path = (repo_path / relative).resolve()
        key = str(path)
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        paths.append(path)
    proxies: list[dict[str, Any]] = []
    for path in paths:
        item: dict[str, Any] = {
            "path": str(path),
            "relative": str(path.relative_to(repo_path)),
            "targets": [],
        }
        if path.suffix == ".json":
            item["targets"] = _parse_proxy_json(path)
        else:
            item["targets"] = _parse_proxy_js_targets(path)
        proxies.append(item)
    return proxies


def _angular_proxy_files(repo_path: Path) -> list[str]:
    data = _read_json(repo_path / "angular.json")
    if not isinstance(data, dict):
        return []
    found: list[str] = []
    for project in (data.get("projects") or {}).values():
        if not isinstance(project, dict):
            continue
        serve = _angular_serve_block(project)
        options = serve.get("options") if isinstance(serve.get("options"), dict) else {}
        proxy = options.get("proxyConfig")
        if isinstance(proxy, str):
            found.append(proxy)
    return found


def _angular_serve_port(repo_path: Path) -> tuple[int | None, str | None]:
    data = _read_json(repo_path / "angular.json")
    if not isinstance(data, dict):
        return None, None
    for name, project in (data.get("projects") or {}).items():
        if not isinstance(project, dict):
            continue
        serve = _angular_serve_block(project)
        options = serve.get("options") if isinstance(serve.get("options"), dict) else {}
        port = _as_port(options.get("port"))
        if port:
            return port, f"angular.json projects.{name}.serve.options.port"
    return None, None


def _angular_serve_block(project: dict[str, Any]) -> dict[str, Any]:
    for key in ("architect", "targets"):
        block = project.get(key)
        if isinstance(block, dict) and isinstance(block.get("serve"), dict):
            return block["serve"]
    return {}


def _spring_port(repo_path: Path) -> tuple[int | None, str | None]:
    preferred = (
        "application-local.yml",
        "application-local.yaml",
        "application-local.properties",
        "application-dev.yml",
        "application-dev.yaml",
        "application-dev.properties",
        "application.yml",
        "application.yaml",
        "application.properties",
    )
    search_dirs = (
        repo_path / "src" / "main" / "resources",
        repo_path / "src" / "main" / "resources" / "config",
        repo_path / "config",
        repo_path,
    )
    candidates: list[Path] = []
    seen: set[str] = set()
    for directory in search_dirs:
        if not directory.is_dir() and directory != repo_path:
            continue
        for name in preferred:
            path = directory / name
            key = str(path)
            if key in seen or not path.is_file():
                continue
            seen.add(key)
            candidates.append(path)
    candidates.sort(
        key=lambda item: (
            preferred.index(item.name),
            0 if "local" in item.name else 1,
            len(item.parts),
        )
    )
    for path in candidates:
        port = _parse_server_port(_read_text(path))
        if port:
            try:
                relative = str(path.relative_to(repo_path))
            except ValueError:
                relative = path.name
            return port, relative
    return None, None


def _parse_server_port(text: str) -> int | None:
    match = _SERVER_PORT_FLAT.search(text) or _SERVER_PORT_PROP.search(text)
    if match:
        return _as_port(match.group(1))
    in_server = False
    server_indent = 0
    for raw in text.splitlines():
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        label = stripped.strip()
        if re.match(r"server\s*:", label):
            in_server = True
            server_indent = indent
            continue
        if in_server:
            if indent <= server_indent:
                in_server = False
            else:
                match = re.match(
                    r"port\s*:\s*(?:\$\{[^:]+:)?(\d{2,5})", label
                )
                if match:
                    return _as_port(match.group(1))
    return None


def _parse_proxy_json(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path)
    targets: list[dict[str, Any]] = []
    if isinstance(data, dict):
        for context, spec in data.items():
            if not isinstance(context, str) or context.startswith("$"):
                continue
            if isinstance(spec, dict) and spec.get("target"):
                targets.append({"context": context, "target": str(spec["target"])})
    elif isinstance(data, list):
        for spec in data:
            if not isinstance(spec, dict) or not spec.get("target"):
                continue
            context = spec.get("context") or spec.get("path") or spec.get("contextPath")
            targets.append({"context": context, "target": str(spec["target"])})
    return targets


def _parse_proxy_js_targets(path: Path) -> list[dict[str, Any]]:
    text = _read_text(path)
    targets: list[dict[str, Any]] = []
    for match in re.finditer(r"""target\s*:\s*['"]([^'"]+)['"]""", text):
        targets.append({"context": None, "target": match.group(1)})
    return targets


def _port_from_scripts(package_scripts: dict[str, str]) -> tuple[int | None, str | None]:
    for name in PACKAGE_START_SCRIPTS:
        script = package_scripts.get(name)
        if not script:
            continue
        match = _PORT_IN_SCRIPT.search(script)
        if match:
            return _as_port(match.group(1)), f"package.json scripts.{name}"
    return None, None


def _all_package_scripts(repo_path: Path) -> dict[str, str]:
    data = _read_json(repo_path / "package.json")
    if not isinstance(data, dict):
        return {}
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return {}
    return {
        str(name): str(value)
        for name, value in scripts.items()
        if isinstance(value, str)
    }


def _make_start_targets(repo_path: Path) -> list[str]:
    makefile = repo_path / "Makefile"
    if not makefile.is_file():
        return []
    found: list[str] = []
    for raw in _read_text(makefile).splitlines():
        if raw.startswith("\t") or raw.startswith("#") or ":" not in raw:
            continue
        target = raw.split(":", 1)[0].strip().lower()
        if target in MAKE_START_TARGETS and target not in found:
            found.append(target)
    return found


def _is_spring_boot(repo_path: Path) -> bool:
    needles = ("spring-boot", "org.springframework.boot")
    for relative in ("pom.xml", "build.gradle", "build.gradle.kts"):
        path = repo_path / relative
        if path.is_file() and any(needle in _read_text(path).lower() for needle in needles):
            return True
    return False


def _looks_like_python_web(repo_path: Path) -> bool:
    needles = ("uvicorn", "fastapi", "flask", "django", "gunicorn")
    for relative in ("pyproject.toml", "requirements.txt", "Pipfile"):
        path = repo_path / relative
        if path.is_file() and any(needle in _read_text(path).lower() for needle in needles):
            return True
    return False


def _js_looks_frontend(package_scripts: dict[str, str]) -> bool:
    blob = " ".join(package_scripts.values()).lower()
    return any(token in blob for token in ("ng serve", "vite", "next", "webpack", "react-scripts"))


def _role_from_tags(tags: list[str]) -> str | None:
    lowered = {tag.lower() for tag in tags}
    if lowered & FRONTEND_TAGS:
        return "frontend"
    if lowered & BACKEND_TAGS:
        return "backend"
    if lowered & INFRA_TAGS:
        return "infra"
    if lowered & MOBILE_TAGS:
        return "mobile"
    return None


def _compose_files(repo_path: Path) -> list[str]:
    found = []
    for name in COMPOSE_FILENAMES:
        path = repo_path / name
        if path.is_file():
            found.append(str(path))
    return found


def _confidence(
    kind: str, command: str | None, port_hint: int | None, override: StartConfig
) -> str:
    if override.configured():
        return "high"
    if kind in {"angular", "spring-boot", "django"} and command:
        return "high"
    if command and port_hint:
        return "medium"
    if command:
        return "medium"
    return "low"


def _default_wait(port: int | None) -> str | None:
    if not port:
        return None
    return f"listen:{port}"


def _js_runner(repo_path: Path) -> str:
    if (repo_path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_path / "yarn.lock").exists():
        return "yarn"
    if (repo_path / "bun.lockb").exists() or (repo_path / "bun.lock").exists():
        return "bun run"
    return "npm run"


def _as_port(value: Any) -> int | None:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if port < 1 or port > 65535:
        return None
    return port


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _service_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    role_rank = ROLE_ORDER.get(str(item.get("role") or ""), 9)
    blocked = 1 if item.get("blocked") else 0
    return (role_rank, blocked, str(item.get("name") or ""))

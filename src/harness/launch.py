from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from harness import HarnessError
from harness.envfile import env_file_keys, load_env_file

LAUNCH_RELATIVE = ".vscode/launch.json"
_VSCODE_INPUT = re.compile(r"^\$\{(?:input|command):")
_WORKSPACE_FOLDER = re.compile(
    r"\$\{workspaceFolder(?:[:.]([^}]+))?\}"
)


def read_jsonc(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(strip_jsonc(text))
    except json.JSONDecodeError:
        return None


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas, leaving strings intact."""
    result: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    escape = False
    while i < n:
        ch = text[i]
        if in_string:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i = min(n, i + 2)
            continue
        result.append(ch)
        i += 1
    return _strip_trailing_commas("".join(result))


def _strip_trailing_commas(text: str) -> str:
    result: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    escape = False
    while i < n:
        ch = text[i]
        if in_string:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "]}":
                i += 1
                continue
        result.append(ch)
        i += 1
    return "".join(result)


def summarize_launch(
    repo_path: Path,
    *,
    kind: str | None = None,
    repo_name: str | None = None,
    configuration: str | None = None,
    env_file: str | None = None,
) -> dict[str, Any] | None:
    """Redacted launch.json / env-file metadata. Values are never returned."""
    launch_path = repo_path / LAUNCH_RELATIVE
    data = read_jsonc(launch_path)
    configs = _launch_configurations(data)
    compounds = _compound_names(data)
    selected = select_configuration(
        configs,
        name=configuration,
        kind=kind,
        repo_name=repo_name,
        required=bool(configuration),
    )
    env_file_rel = env_file or _env_file_relative(repo_path, selected)
    if not selected and not env_file_rel and not configs:
        return None

    env_keys = _env_keys(selected)
    env_file_present = _env_file_key_names(repo_path, env_file_rel)
    uses_vscode_inputs = _uses_vscode_inputs(selected)
    has_env = bool(env_keys)
    has_args = _has_value(selected, "args")
    has_vm_args = _has_value(selected, "vmArgs") or _has_value(selected, "vmArg")
    secret_risk = bool(
        has_env or env_file_rel or has_args or has_vm_args or uses_vscode_inputs
    )
    payload: dict[str, Any] = {
        "file": LAUNCH_RELATIVE if launch_path.is_file() else None,
        "configuration": selected.get("name") if selected else None,
        "type": selected.get("type") if selected else None,
        "request": selected.get("request") if selected else None,
        "main_class": selected.get("mainClass") if selected else None,
        "project_name": selected.get("projectName") if selected else None,
        "has_env": has_env,
        "has_args": has_args,
        "has_vm_args": has_vm_args,
        "env_keys": env_keys,
        "env_file": env_file_rel,
        "env_file_keys": env_file_present,
        "uses_vscode_inputs": uses_vscode_inputs,
        "secret_risk": secret_risk,
        "configurations": [
            str(item.get("name"))
            for item in configs
            if isinstance(item.get("name"), str)
        ],
        "compounds": compounds,
    }
    return payload


def select_configuration(
    configs: list[dict[str, Any]],
    *,
    name: str | None = None,
    kind: str | None = None,
    repo_name: str | None = None,
    required: bool = False,
) -> dict[str, Any] | None:
    launchable = [
        item
        for item in configs
        if str(item.get("request") or "launch").lower() == "launch"
    ]
    if name:
        for item in launchable:
            if item.get("name") == name:
                return item
        if required:
            available = ", ".join(
                str(item.get("name"))
                for item in launchable
                if item.get("name")
            ) or "(none)"
            raise HarnessError(
                f"launch.json has no configuration named {name!r}. "
                f"Available: {available}"
            )
        return None
    if not launchable:
        return None
    wanted_type = _type_for_kind(kind)
    typed = [
        item
        for item in launchable
        if wanted_type and str(item.get("type") or "") == wanted_type
    ]
    pool = typed or launchable
    scored = sorted(pool, key=lambda item: _config_score(item, repo_name), reverse=True)
    return scored[0]


def load_launch_runtime(
    repo_path: Path,
    summary: dict[str, Any] | None,
    *,
    configuration: str | None = None,
) -> dict[str, Any]:
    """Load env and args in-process. Callers must not print values."""
    data = read_jsonc(repo_path / LAUNCH_RELATIVE)
    configs = _launch_configurations(data)
    selected = None
    if configs:
        selected = select_configuration(
            configs,
            name=configuration or (summary or {}).get("configuration"),
            required=bool(configuration),
        )
    env: dict[str, str] = {}
    env_file = (summary or {}).get("env_file") or _env_file_relative(repo_path, selected)
    if env_file:
        env.update(load_env_file(_resolve_workspace_path(repo_path, env_file)))
    raw_env = selected.get("env") if selected else None
    if isinstance(raw_env, dict):
        for key, value in raw_env.items():
            if key is None:
                continue
            env[str(key)] = "" if value is None else str(value)
    return {
        "configuration": selected.get("name") if selected else None,
        "env": env,
        "args": selected.get("args") if selected else None,
        "vm_args": (selected.get("vmArgs") if selected else None)
        or (selected.get("vmArg") if selected else None),
        "uses_vscode_inputs": _uses_vscode_inputs(selected),
        "cwd": _launch_cwd(repo_path, selected),
    }


def resolve_workspace_path(repo_path: Path, value: str) -> Path:
    return _resolve_workspace_path(repo_path, value)


def _launch_configurations(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    raw = data.get("configurations")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _compound_names(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    raw = data.get("compounds")
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def _env_keys(selected: dict[str, Any] | None) -> list[str]:
    if not selected:
        return []
    raw = selected.get("env")
    if not isinstance(raw, dict):
        return []
    return [str(key) for key in raw if key is not None]


def _env_file_relative(repo_path: Path, selected: dict[str, Any] | None) -> str | None:
    if not selected:
        return None
    raw = selected.get("envFile") or selected.get("envfile")
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = _resolve_workspace_path(repo_path, raw.strip())
    try:
        relative = path.resolve().relative_to(repo_path.resolve()).as_posix()
    except ValueError:
        return path.name
    return relative


def _env_file_key_names(repo_path: Path, relative: str | None) -> list[str]:
    if not relative:
        return []
    path = _resolve_workspace_path(repo_path, relative)
    return sorted(env_file_keys(path))


def _uses_vscode_inputs(selected: dict[str, Any] | None) -> bool:
    if not selected:
        return False
    raw = selected.get("env")
    if isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, str) and _VSCODE_INPUT.match(value.strip()):
                return True
    for key in ("args", "vmArgs", "vmArg"):
        value = selected.get(key)
        if isinstance(value, str) and _VSCODE_INPUT.match(value.strip()):
            return True
        if isinstance(value, list) and any(
            isinstance(part, str) and _VSCODE_INPUT.match(part.strip()) for part in value
        ):
            return True
    return False


def _has_value(selected: dict[str, Any] | None, key: str) -> bool:
    if not selected:
        return False
    value = selected.get(key)
    if value is None or value == "" or value == []:
        return False
    return True


def _type_for_kind(kind: str | None) -> str | None:
    if kind in {"spring-boot", "java"}:
        return "java"
    if kind in {"node", "angular"}:
        return "node"
    if kind in {"python", "django"}:
        return "python"
    return None


def _config_score(item: dict[str, Any], repo_name: str | None) -> int:
    name = str(item.get("name") or "").lower()
    score = 0
    if repo_name and repo_name.lower() in name:
        score += 8
    for token in ("launch", "run", "start", "boot", "app", "application"):
        if token in name:
            score += 2
    if "test" in name or "attach" in name:
        score -= 4
    return score


def _resolve_workspace_path(repo_path: Path, value: str) -> Path:
    text = value.strip()
    match = _WORKSPACE_FOLDER.search(text)
    if match:
        text = _WORKSPACE_FOLDER.sub(str(repo_path), text, count=1)
    path = Path(text)
    if not path.is_absolute():
        path = repo_path / path
    return path


def _launch_cwd(repo_path: Path, selected: dict[str, Any] | None) -> Path:
    if not selected:
        return repo_path
    raw = selected.get("cwd")
    if isinstance(raw, str) and raw.strip():
        path = _resolve_workspace_path(repo_path, raw.strip())
        try:
            path.resolve().relative_to(repo_path.resolve())
        except ValueError as exc:
            raise HarnessError(
                f"launch.json cwd must stay inside the repo: {raw}"
            ) from exc
        return path
    return repo_path

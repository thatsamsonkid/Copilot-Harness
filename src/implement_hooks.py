"""Gates parent product-file edits during /goat-implement so Code Writer must write them."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from goat.read_hooks import (
    allow,
    deny,
    emit,
    load_payload,
    payload_cwd,
    read_path,
    tool_args,
    tool_name,
)

ENV_GATE = "GOAT_IMPLEMENT_EDIT_GATE"
LOCK_RELATIVE = Path(".goat") / "implement-lock.json"
PLAN_GLOB = "*.plan.md"

IMPLEMENT_CONTEXT = (
    "This chat is implementing a plans/ file. You are Implementer — do not spawn "
    "Implementer. Invoke Code Writer (#tool:agent) for every product-file write. "
    "Do not #tool:edit product files yourself. Invoke Verifier for each plan Verify "
    "check and the final Verification section. You still run goat branch and write "
    "feature notes / ADRs. A workspace hook denies parent edits to sibling product "
    "files until Code Writer is the caller."
)

DENY_REASON = (
    "Parent chat cannot edit sibling product files during /goat-implement. "
    "Invoke Code Writer (#tool:agent) with the spec, target paths, and reference "
    "paths. You may still edit goat catalog, plans/, and sibling docs/features "
    "or docs/adr. Disable with GOAT_IMPLEMENT_EDIT_GATE=off."
)

# Only strings unique to /goat-implement (not mentions inside /goat-plan or /jira-ticket).
ARM_MARKERS = (
    "start implementing an agreed plan",
    "chat compaction may have dropped",
    "skills/implementing/skill.md",
    "name: goat-implement",
)
SLASH_IMPLEMENT = re.compile(r"(?m)^\s*/goat-implement\b")
PLANNING_TURN = "do not implement in this planning turn"
DISARM_MARKERS = ("/review",)
EXECUTOR_MARKERS = ("you are the executor",)
IMPLEMENT_INTENT = re.compile(
    r"\b(?:implement|execute)(?:\s+the|\s+this|\s+our|\s+agreed)\s+plan\b"
    r"|\bstart implementing\b"
    r"|\bimplement the agreed\b",
    re.IGNORECASE,
)

EDIT_TOOLS = frozenset(
    {
        "edit",
        "Edit",
        "editFiles",
        "EditFiles",
        "write",
        "Write",
        "createFile",
        "CreateFile",
        "StrReplace",
        "strReplace",
        "search_replace",
        "SearchReplace",
        "ApplyPatch",
        "apply_patch",
        "applyPatch",
        "NotebookEdit",
        "notebookEdit",
        "MultiEdit",
        "multi_edit",
        "replace_string_in_file",
    }
)
CODE_WRITER_NAMES = frozenset(
    {"code writer", "code-writer", "code_writer", "codewriter"}
)
VERIFIER_NAMES = frozenset({"verifier"})
PARENT_DOC_DIRS = frozenset({"features", "adr", "adrs"})
PROMPT_EVENTS = frozenset(
    {"userpromptsubmit", "userpromptsubmitted", "usersubmitprompt"}
)
PRE_TOOL_EVENTS = frozenset({"pretooluse", "pretoolusehook"})
PRE_COMPACT_EVENTS = frozenset({"precompact"})
SUBAGENT_START_EVENTS = frozenset({"subagentstart"})


def gate_enabled(environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    raw = env.get(ENV_GATE, "").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def event_name(payload: Mapping[str, Any]) -> str:
    value = (
        payload.get("hook_event_name")
        or payload.get("hookEventName")
        or payload.get("event")
        or ""
    )
    return str(value)


def session_id(payload: Mapping[str, Any]) -> str:
    value = (
        payload.get("session_id")
        or payload.get("sessionId")
        or payload.get("sessionID")
        or "_"
    )
    text = str(value).strip()
    return text or "_"


def prompt_text(payload: Mapping[str, Any]) -> str:
    value = payload.get("prompt") or payload.get("user_prompt") or payload.get("userPrompt") or ""
    return str(value)


def agent_label(payload: Mapping[str, Any]) -> str:
    value = (
        payload.get("agent_type")
        or payload.get("agentType")
        or payload.get("agent_name")
        or payload.get("agentName")
        or ""
    )
    return str(value).strip().lower()


def context_output(event: str, text: str) -> dict[str, Any]:
    return {
        "continue": True,
        "additionalContext": text,
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        },
    }


def continue_ok() -> dict[str, Any]:
    return {"continue": True}


def _guess_goat_root(start: Path | None = None) -> Path | None:
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    if start is not None:
        candidates.append(start.resolve())
    candidates.append(Path.cwd().resolve())
    if here.parts[-2:] == ("src", "implement_hooks.py"):
        candidates.append(here.parents[1])
    seen: set[Path] = set()
    for origin in candidates:
        for path in [origin, *origin.parents]:
            if path in seen:
                continue
            seen.add(path)
            if (path / "repositories.yml").is_file() or (
                path / "catalog" / "stack.yaml"
            ).is_file():
                return path
    return None


def goat_root_from(
    payload: Mapping[str, Any],
    *,
    goat_root: Path | None = None,
) -> Path | None:
    if goat_root is not None:
        return goat_root
    return _guess_goat_root(payload_cwd(payload))


def plan_exists(root: Path) -> bool:
    plans = root / "plans"
    if not plans.is_dir():
        return False
    return next(plans.glob(PLAN_GLOB), None) is not None


def classify_prompt(text: str, *, has_plan: bool) -> str:
    """Return arm, disarm, or ignore."""
    lowered = text.lower()
    if not lowered.strip():
        return "ignore"
    if PLANNING_TURN in lowered:
        return "ignore"
    if any(marker in lowered for marker in ARM_MARKERS) or SLASH_IMPLEMENT.search(text):
        return "arm"
    if any(marker in lowered for marker in DISARM_MARKERS):
        return "disarm"
    if any(marker in lowered for marker in EXECUTOR_MARKERS):
        return "disarm"
    if has_plan and IMPLEMENT_INTENT.search(text):
        return "arm"
    return "ignore"


def is_code_writer(payload: Mapping[str, Any], session: Mapping[str, Any]) -> bool:
    if agent_label(payload) in CODE_WRITER_NAMES:
        return True
    return bool(session.get("code_writer_active"))


def is_parent_owned_path(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
    except OSError:
        return False
    if resolved == root_resolved or root_resolved in resolved.parents:
        return True
    parts = resolved.parts
    for index, part in enumerate(parts):
        if part == "docs" and index + 1 < len(parts):
            if parts[index + 1] in PARENT_DOC_DIRS:
                return True
    return False


def edit_paths(args: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    single = read_path(args)
    if single:
        found.append(single)
    files = args.get("files") or args.get("Files")
    if isinstance(files, list):
        for item in files:
            if isinstance(item, str) and item.strip():
                found.append(item.strip())
            elif isinstance(item, Mapping):
                nested = read_path(item)
                if nested:
                    found.append(nested)
    return found


def load_lock(root: Path) -> dict[str, Any]:
    path = root / LOCK_RELATIVE
    if not path.is_file():
        return {"sessions": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sessions": {}}
    sessions = data.get("sessions") if isinstance(data, dict) else None
    return {"sessions": sessions} if isinstance(sessions, dict) else {"sessions": {}}


def save_lock(root: Path, data: Mapping[str, Any]) -> None:
    path = root / LOCK_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def session_state(lock: Mapping[str, Any], sid: str) -> dict[str, Any]:
    sessions = lock.get("sessions")
    if not isinstance(sessions, dict):
        return {}
    current = sessions.get(sid)
    return dict(current) if isinstance(current, dict) else {}


def write_session(root: Path, sid: str, state: Mapping[str, Any]) -> dict[str, Any]:
    lock = load_lock(root)
    sessions = lock.setdefault("sessions", {})
    sessions[sid] = dict(state)
    save_lock(root, lock)
    return lock


def empty_session() -> dict[str, Any]:
    return {
        "armed": False,
        "code_writer_active": False,
        "code_writer_started": False,
        "verifier_started": False,
    }


def on_user_prompt(
    payload: Mapping[str, Any],
    *,
    goat_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root = goat_root_from(payload, goat_root=goat_root)
    if root is None:
        return continue_ok()
    sid = session_id(payload)
    kind = classify_prompt(prompt_text(payload), has_plan=plan_exists(root))
    state = session_state(load_lock(root), sid) or empty_session()
    if kind == "arm":
        state["armed"] = True
        write_session(root, sid, state)
        return context_output("UserPromptSubmit", IMPLEMENT_CONTEXT)
    if kind == "disarm":
        state["armed"] = False
        state["code_writer_active"] = False
        write_session(root, sid, state)
        return continue_ok()
    if state.get("armed") and gate_enabled(environ):
        return context_output("UserPromptSubmit", IMPLEMENT_CONTEXT)
    return continue_ok()


def on_pre_tool(
    payload: Mapping[str, Any],
    *,
    goat_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not gate_enabled(environ):
        return allow()
    if tool_name(payload) not in EDIT_TOOLS:
        return allow()
    root = goat_root_from(payload, goat_root=goat_root)
    if root is None:
        return allow()
    sid = session_id(payload)
    state = session_state(load_lock(root), sid)
    if not state.get("armed"):
        return allow()
    if is_code_writer(payload, state):
        return allow()
    cwd = payload_cwd(payload)
    for raw in edit_paths(tool_args(payload)):
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = cwd / candidate
        if not is_parent_owned_path(candidate, root):
            return deny(DENY_REASON)
    return allow()


def on_pre_compact(
    payload: Mapping[str, Any],
    *,
    goat_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not gate_enabled(environ):
        return continue_ok()
    root = goat_root_from(payload, goat_root=goat_root)
    if root is None:
        return continue_ok()
    state = session_state(load_lock(root), session_id(payload))
    if not state.get("armed"):
        return continue_ok()
    return context_output("PreCompact", IMPLEMENT_CONTEXT)


def on_subagent_start(
    payload: Mapping[str, Any],
    *,
    goat_root: Path | None = None,
) -> dict[str, Any]:
    root = goat_root_from(payload, goat_root=goat_root)
    if root is None:
        return continue_ok()
    sid = session_id(payload)
    state = session_state(load_lock(root), sid) or empty_session()
    label = agent_label(payload)
    if label in CODE_WRITER_NAMES:
        state["code_writer_active"] = True
        state["code_writer_started"] = True
        write_session(root, sid, state)
    elif label in VERIFIER_NAMES:
        state["verifier_started"] = True
        write_session(root, sid, state)
    return continue_ok()


def decide(
    payload: Mapping[str, Any],
    *,
    goat_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    event = event_name(payload).replace("_", "").lower()
    if event in PROMPT_EVENTS or (not event and prompt_text(payload)):
        return on_user_prompt(payload, goat_root=goat_root, environ=environ)
    if event in PRE_TOOL_EVENTS or (not event and tool_name(payload)):
        return on_pre_tool(payload, goat_root=goat_root, environ=environ)
    if event in PRE_COMPACT_EVENTS:
        return on_pre_compact(payload, goat_root=goat_root, environ=environ)
    if event in SUBAGENT_START_EVENTS:
        return on_subagent_start(payload, goat_root=goat_root)
    return continue_ok()


def run_implement_gate() -> int:
    try:
        return emit(decide(load_payload()))
    except Exception:
        return emit(allow())

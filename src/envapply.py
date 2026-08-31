from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from goat import GoatError

GOAT_ENV_REPO = "GOAT_ENV_REPO"
GOAT_ENV_CONFIGURATION = "GOAT_ENV_CONFIGURATION"
_GOAT_MARKERS = (GOAT_ENV_REPO, GOAT_ENV_CONFIGURATION)
_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_env_prefix(prefix: str | None) -> str:
    """Return a suffix-ready prefix, or empty when unused.

    Application keys stay unprefixed by default so Spring/Node see the same
    names as VS Code. A custom prefix gets a trailing underscore if missing.
    """
    text = (prefix or "").strip()
    if not text:
        return ""
    if not _PREFIX.match(text):
        raise GoatError(
            "Env --prefix must be a shell identifier "
            f"(letters, digits, underscore), got {prefix!r}"
        )
    return text if text.endswith("_") else f"{text}_"


@dataclass(frozen=True)
class AppliedEnv:
    env: dict[str, str]
    applied: dict[str, str]
    env_keys: list[str]
    overwritten_keys: list[str]
    skipped_keys: list[str]
    new_keys: list[str]
    marker_keys: list[str]
    prefix: str
    keep_existing: bool


def apply_project_env(
    incoming: Mapping[str, str],
    parent: Mapping[str, str],
    *,
    repo_name: str,
    configuration: str | None = None,
    prefix: str | None = None,
    keep_existing: bool = False,
) -> AppliedEnv:
    """Merge launch/env-file keys into a parent environment without printing values.

    Launch values overwrite the parent unless ``keep_existing`` is set.
    Goat marker keys are always stamped so a terminal can show which
    project env is active. Those markers are prefixed already (`GOAT_ENV_`).
    """
    prefix_text = normalize_env_prefix(prefix)
    env = {str(key): str(value) for key, value in parent.items()}
    applied: dict[str, str] = {}
    overwritten: list[str] = []
    skipped: list[str] = []
    new_keys: list[str] = []

    for raw_key, value in incoming.items():
        if raw_key is None:
            continue
        key = f"{prefix_text}{raw_key}"
        text = "" if value is None else str(value)
        if key in env:
            if keep_existing:
                skipped.append(key)
                continue
            overwritten.append(key)
        else:
            new_keys.append(key)
        env[key] = text
        applied[key] = text

    markers: dict[str, str] = {GOAT_ENV_REPO: repo_name}
    if configuration:
        markers[GOAT_ENV_CONFIGURATION] = configuration
    for key, text in markers.items():
        if key in env and env.get(key) != text and key not in overwritten:
            overwritten.append(key)
        env[key] = text
        applied[key] = text

    return AppliedEnv(
        env=env,
        applied=applied,
        env_keys=sorted(key for key in applied if key not in markers),
        overwritten_keys=sorted(overwritten),
        skipped_keys=sorted(skipped),
        new_keys=sorted(new_keys),
        marker_keys=sorted(markers),
        prefix=prefix_text,
        keep_existing=keep_existing,
    )


def applied_env_preview(applied: AppliedEnv) -> dict[str, Any]:
    """JSON-safe collision metadata. Values are never included."""
    return {
        "env_keys": list(applied.env_keys),
        "overwritten_keys": list(applied.overwritten_keys),
        "skipped_keys": list(applied.skipped_keys),
        "new_keys": list(applied.new_keys),
        "marker_keys": list(applied.marker_keys),
        "prefix": applied.prefix or None,
        "keep_existing": applied.keep_existing,
    }

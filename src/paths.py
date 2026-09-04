from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from goat import GoatError

REPOS_RELATIVE = Path("repositories.yml")
STACK_RELATIVE = Path("catalog") / "stack.yaml"
TEMPLATES_RELATIVE = Path("templates.yml")
ENV_RELATIVE = Path("catalog") / "env.yaml"
GLOSSARY_RELATIVE = Path("catalog") / "glossary.yml"
WORKSPACES_DIR = Path("workspaces")
ROOT_ENV = "GOAT_ROOT"
LEGACY_ROOT_ENV = "COBOOSE_ROOT"


def first_env(
    *names: str, environ: Mapping[str, str] | None = None
) -> tuple[str, str] | None:
    """Return (name, value) for the first set environment variable."""
    env = environ if environ is not None else os.environ
    for name in names:
        value = env.get(name)
        if value:
            return name, value
    return None


def is_goat_root(path: Path) -> bool:
    return (path / REPOS_RELATIVE).exists() or (path / STACK_RELATIVE).exists()


def find_goat_root(start: Path | None = None) -> Path:
    found = first_env(ROOT_ENV, LEGACY_ROOT_ENV)
    if found:
        name, env = found
        root = Path(env).expanduser().resolve()
        if not is_goat_root(root):
            raise GoatError(
                f"{name}={root} does not contain {REPOS_RELATIVE} "
                f"or {STACK_RELATIVE}"
            )
        return root

    candidates = []
    if start is not None:
        candidates.append(Path(start).resolve())
    candidates.append(Path.cwd().resolve())
    candidates.append(Path(__file__).resolve())

    seen: set[Path] = set()
    for origin in candidates:
        for path in [origin, *origin.parents]:
            if path in seen:
                continue
            seen.add(path)
            if is_goat_root(path):
                return path

    raise GoatError(
        f"Could not find Goat root ({REPOS_RELATIVE}). "
        f"Run from the Goat repo or set {ROOT_ENV}."
    )


def load_dotenv_files(root: Path) -> None:
    """Load the Goat repo's own .env into the process environment.

    Only the trusted Goat-root .env is loaded. The current working directory is
    intentionally NOT read: goat is run from inside sibling product clones, and
    a clone could commit a .env that would silently override JIRA_BASE_URL,
    GIT_SSH_COMMAND, and similar, poisoning the environment. Global settings such
    as JIRA_BASE_URL / JIRA_EMAIL belong in the user's permanent shell
    environment instead (see docs/jira-api-token.md).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(root / ".env", override=False)

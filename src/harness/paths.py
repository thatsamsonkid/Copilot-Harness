from __future__ import annotations

import os
from pathlib import Path

from harness import HarnessError

REPOS_RELATIVE = Path("repositories.yml")
STACK_RELATIVE = Path("catalog") / "stack.yaml"
TEMPLATES_RELATIVE = Path("templates.yml")
ENV_RELATIVE = Path("catalog") / "env.yaml"
WORKSPACES_DIR = Path("workspaces")
PERSONAL_WORKSPACES_DIR = WORKSPACES_DIR / "personal"


def is_harness_root(path: Path) -> bool:
    return (path / REPOS_RELATIVE).exists() or (path / STACK_RELATIVE).exists()


def find_harness_root(start: Path | None = None) -> Path:
    env = os.environ.get("HARNESS_ROOT")
    if env:
        root = Path(env).expanduser().resolve()
        if not is_harness_root(root):
            raise HarnessError(
                f"HARNESS_ROOT={root} does not contain {REPOS_RELATIVE} "
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
            if is_harness_root(path):
                return path

    raise HarnessError(
        f"Could not find harness root ({REPOS_RELATIVE}). "
        "Run from the harness repo or set HARNESS_ROOT."
    )


def load_dotenv_files(root: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(root / ".env", override=False)
    load_dotenv(Path.cwd() / ".env", override=False)

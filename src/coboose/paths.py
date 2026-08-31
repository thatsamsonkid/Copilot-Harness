from __future__ import annotations

import os
from pathlib import Path

from coboose import CobooseError

REPOS_RELATIVE = Path("repositories.yml")
STACK_RELATIVE = Path("catalog") / "stack.yaml"
TEMPLATES_RELATIVE = Path("templates.yml")
ENV_RELATIVE = Path("catalog") / "env.yaml"
WORKSPACES_DIR = Path("workspaces")


def is_coboose_root(path: Path) -> bool:
    return (path / REPOS_RELATIVE).exists() or (path / STACK_RELATIVE).exists()


def find_coboose_root(start: Path | None = None) -> Path:
    env = os.environ.get("COBOOSE_ROOT")
    if env:
        root = Path(env).expanduser().resolve()
        if not is_coboose_root(root):
            raise CobooseError(
                f"COBOOSE_ROOT={root} does not contain {REPOS_RELATIVE} "
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
            if is_coboose_root(path):
                return path

    raise CobooseError(
        f"Could not find Coboose root ({REPOS_RELATIVE}). "
        "Run from the Coboose repo or set COBOOSE_ROOT."
    )


def load_dotenv_files(root: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(root / ".env", override=False)
    load_dotenv(Path.cwd() / ".env", override=False)

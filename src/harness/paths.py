from __future__ import annotations

import os
from pathlib import Path

from harness import HarnessError

CATALOG_RELATIVE = Path("catalog") / "stack.yaml"


def find_harness_root(start: Path | None = None) -> Path:
    env = os.environ.get("HARNESS_ROOT")
    if env:
        root = Path(env).expanduser().resolve()
        if not (root / CATALOG_RELATIVE).exists():
            raise HarnessError(
                f"HARNESS_ROOT={root} does not contain {CATALOG_RELATIVE}"
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
            if (path / CATALOG_RELATIVE).exists():
                return path

    raise HarnessError(
        f"Could not find harness root ({CATALOG_RELATIVE}). "
        "Run from the harness repo or set HARNESS_ROOT."
    )


def load_dotenv_files(root: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(root / ".env", override=False)
    load_dotenv(Path.cwd() / ".env", override=False)

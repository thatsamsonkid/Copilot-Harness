from __future__ import annotations

import time
from pathlib import Path

from goat.envfile import TOKEN_WARN_DAYS, env_file_age


def test_env_age_warns_after_ten_months(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("JIRA_API_TOKEN=hidden\n", encoding="utf-8")
    now = time.time()
    older = now - ((TOKEN_WARN_DAYS + 5) * 86400)
    payload = env_file_age(env, now=now)
    # Fresh file should not be stale.
    assert payload["stale"] is False
    assert "hidden" not in payload["detail"]

    import os

    os.utime(env, (older, older))
    stale = env_file_age(env, now=now)
    assert stale["stale"] is True
    assert stale["age_days"] >= TOKEN_WARN_DAYS
    assert "hidden" not in stale["detail"]

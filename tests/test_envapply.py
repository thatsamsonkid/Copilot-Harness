from __future__ import annotations

import pytest

from coboose import CobooseError
from coboose.envapply import (
    COBOOSE_ENV_CONFIGURATION,
    COBOOSE_ENV_REPO,
    apply_project_env,
    normalize_env_prefix,
)


def test_normalize_prefix_adds_underscore():
    assert normalize_env_prefix(None) == ""
    assert normalize_env_prefix("") == ""
    assert normalize_env_prefix("BACKEND") == "BACKEND_"
    assert normalize_env_prefix("BACKEND_") == "BACKEND_"


def test_normalize_prefix_rejects_invalid():
    with pytest.raises(CobooseError, match="identifier"):
        normalize_env_prefix("backend-api")


def test_apply_reports_collisions_and_stamps_markers():
    applied = apply_project_env(
        {"DB_PASSWORD": "secret", "NEW_KEY": "1"},
        {"DB_PASSWORD": "old", "PATH": "/bin"},
        repo_name="backend",
        configuration="Launch Backend",
    )
    assert applied.env["DB_PASSWORD"] == "secret"
    assert applied.env["NEW_KEY"] == "1"
    assert applied.env["PATH"] == "/bin"
    assert applied.env[COBOOSE_ENV_REPO] == "backend"
    assert applied.env[COBOOSE_ENV_CONFIGURATION] == "Launch Backend"
    assert applied.env_keys == ["DB_PASSWORD", "NEW_KEY"]
    assert applied.overwritten_keys == ["DB_PASSWORD"]
    assert applied.new_keys == ["NEW_KEY"]
    assert applied.skipped_keys == []
    assert applied.marker_keys == [COBOOSE_ENV_CONFIGURATION, COBOOSE_ENV_REPO]
    assert applied.prefix == ""


def test_keep_existing_skips_parent_keys():
    applied = apply_project_env(
        {"DB_PASSWORD": "secret", "NEW_KEY": "1"},
        {"DB_PASSWORD": "old"},
        repo_name="backend",
        keep_existing=True,
    )
    assert applied.env["DB_PASSWORD"] == "old"
    assert applied.env["NEW_KEY"] == "1"
    assert applied.skipped_keys == ["DB_PASSWORD"]
    assert "DB_PASSWORD" not in applied.env_keys
    assert applied.new_keys == ["NEW_KEY"]


def test_prefix_namespaces_app_keys_not_markers():
    applied = apply_project_env(
        {"DB_PASSWORD": "secret"},
        {"DB_PASSWORD": "old"},
        repo_name="backend",
        prefix="BACKEND",
    )
    assert applied.env["BACKEND_DB_PASSWORD"] == "secret"
    assert applied.env["DB_PASSWORD"] == "old"
    assert applied.env[COBOOSE_ENV_REPO] == "backend"
    assert applied.env_keys == ["BACKEND_DB_PASSWORD"]
    assert applied.prefix == "BACKEND_"
    assert applied.overwritten_keys == []
    assert COBOOSE_ENV_REPO not in applied.env_keys

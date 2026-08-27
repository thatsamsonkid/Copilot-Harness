from pathlib import Path

import pytest

from harness import HarnessError
from harness.catalog import catalog_to_dict, load_catalog
from harness.paths import find_harness_root
from tests.conftest import write_catalog


def test_load_and_resolve_sibling_paths(catalog, harness_root: Path):
    assert catalog.repo("frontend").url.endswith("frontend.git")
    assert catalog.sibling_root(harness_root) == harness_root.parent
    assert catalog.repo_path(harness_root, "backend") == harness_root.parent / "backend"
    assert catalog.workspace("frontend").folders == ["frontend", "backend"]


def test_rejects_unknown_workspace_folder(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["workspaces"][0]["folders"] = ["frontend", "missing"]
    path = write_catalog(tmp_path / "stack.yaml", sample_catalog_data)
    with pytest.raises(HarnessError, match="unknown repo"):
        load_catalog(path)


def test_rejects_nested_repo_path(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["path"] = "../escape"
    path = write_catalog(tmp_path / "stack.yaml", sample_catalog_data)
    with pytest.raises(HarnessError, match="sibling folder"):
        load_catalog(path)


def test_find_harness_root_from_nested_cwd(harness_root: Path, monkeypatch: pytest.MonkeyPatch):
    nested = harness_root / "src" / "harness"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("HARNESS_ROOT", raising=False)
    assert find_harness_root() == harness_root.resolve()


def test_catalog_to_dict_marks_placeholders(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"][0]["url"] = "git@github.com:YOUR_ORG/frontend.git"
    root = tmp_path / "harness"
    path = write_catalog(root / "catalog" / "stack.yaml", sample_catalog_data)
    catalog = load_catalog(path)
    payload = catalog_to_dict(catalog, root)
    assert payload["repos"][0]["placeholder"] is True
    assert payload["repos"][1]["placeholder"] is False

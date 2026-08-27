from pathlib import Path

import pytest

from harness import HarnessError
from harness.catalog import load_catalog
from harness.paths import TEMPLATES_RELATIVE
from harness.templates import get_template, load_templates, select_templates
from tests.helpers import write_harness_config, write_yaml


def test_load_templates_from_harness_root(catalog):
    names = [item.name for item in catalog.templates]
    assert names == ["web-starter", "api-starter"]
    assert catalog.template("web-starter").kind == "frontend"
    assert catalog.templates_source.name == "templates.yml"


def test_missing_templates_file_is_empty(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data.pop("templates")
    root = tmp_path / "harness"
    write_harness_config(root, sample_catalog_data)
    assert not (root / TEMPLATES_RELATIVE).exists()
    catalog = load_catalog(root)
    assert catalog.templates == []


def test_rejects_duplicate_template_names(tmp_path: Path):
    path = write_yaml(
        tmp_path / "templates.yml",
        {
            "templates": [
                {
                    "name": "web",
                    "url": "https://github.com/acme/a.git",
                    "tags": ["web"],
                },
                {
                    "name": "web",
                    "url": "https://github.com/acme/b.git",
                    "tags": ["web"],
                },
            ]
        },
    )
    with pytest.raises(HarnessError, match="Duplicate template"):
        load_templates(path)


def test_requires_name_url_and_tags(tmp_path: Path):
    path = write_yaml(
        tmp_path / "templates.yml",
        {"templates": [{"name": "web", "url": "https://github.com/acme/a.git"}]},
    )
    with pytest.raises(HarnessError, match="at least one tag"):
        load_templates(path)


def test_select_templates_by_tag_and_unknown_name(catalog):
    selected = select_templates(catalog.templates, tags=["mobile", "api"])
    assert [item.name for item in selected] == ["api-starter"]
    with pytest.raises(HarnessError, match="Unknown template"):
        get_template(catalog.templates, "nope")


def test_rejects_repositories_key_in_templates_file(tmp_path: Path):
    path = write_yaml(
        tmp_path / "templates.yml",
        {
            "repositories": [
                {
                    "name": "frontend",
                    "url": "https://github.com/acme/frontend.git",
                    "tags": ["ui"],
                }
            ]
        },
    )
    with pytest.raises(HarnessError, match="repositories.yml"):
        load_templates(path)


def test_shipped_templates_yml_loads():
    root = Path(__file__).resolve().parents[1]
    templates = load_templates(root / TEMPLATES_RELATIVE)
    names = [item.name for item in templates]
    assert "spartan-stack" in names
    assert "react-native" in names
    assert "spring-boot" in names
    assert all(item.tags for item in templates)

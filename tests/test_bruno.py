from __future__ import annotations

from pathlib import Path

import pytest

from goat import GoatError
from goat.bruno import (
    collect_bruno_inventory,
    list_bruno_envs,
    list_bruno_requests,
    list_bruno_workflows,
    parse_bru_blocks,
    parse_bru_environment,
    parse_bru_request,
    parse_env_vars,
    run_bruno_request,
)
from goat.catalog import load_catalog
from goat.cli import main
from tests.helpers import write_goat_config


SEARCH_BRU = """meta {
  name: Search products
  type: http
  seq: 1
}

post {
  url: {{baseUrl}}/search
}

body:json {
  {
    "q": "shoes"
  }
}

docs {
  Find a product to add to the cart.
}
"""

CART_BRU = """meta {
  name: Add to cart
  type: http
  seq: 2
}

post {
  url: {{baseUrl}}/cart/items
}

body:json {
  {
    "productId": "{{productId}}"
  }
}
"""

FOLDER_BRU = """meta {
  name: Search
  type: folder
  seq: 1
}
"""

LOCAL_ENV = """vars {
  baseUrl: http://localhost:8080
  storeId: 1
}
"""

STAGING_ENV = """vars {
  baseUrl: https://staging.example.com
}

vars:secret [
  apiKey
]
"""

WORKFLOWS = """
workflows:
  - id: add-to-cart
    description: Search, pick a product, add it to the cart
    env: staging
    service: cart
    steps:
      - id: search
        request: search/search-products
        pick:
          product_id: body.products[0].id
      - id: add
        request: cart/add-item
        needs: [product_id]
        env_vars:
          productId: $product_id
"""

SERVICES = """
services:
  - id: cart
    env: staging
    description: Cart and checkout
  - id: search
    env: staging
"""


def _write_bruno_tree(sibling: Path) -> Path:
    root = sibling / "api-collections"
    (root / "search").mkdir(parents=True)
    (root / "cart").mkdir()
    (root / "environments").mkdir()
    (root / "bruno.json").write_text(
        '{"version": "1", "name": "cart-api", "type": "collection"}\n',
        encoding="utf-8",
    )
    (root / "search" / "folder.bru").write_text(FOLDER_BRU, encoding="utf-8")
    (root / "search" / "search-products.bru").write_text(SEARCH_BRU, encoding="utf-8")
    (root / "cart" / "add-item.bru").write_text(CART_BRU, encoding="utf-8")
    (root / "environments" / "local.bru").write_text(LOCAL_ENV, encoding="utf-8")
    (root / "environments" / "staging.bru").write_text(STAGING_ENV, encoding="utf-8")
    (root / "goat.workflows.yml").write_text(WORKFLOWS, encoding="utf-8")
    (root / "goat.services.yml").write_text(SERVICES, encoding="utf-8")
    return root


def _catalog_with_bruno(goat_root: Path, sample_catalog_data: dict):
    sample_catalog_data["repos"].append(
        {
            "name": "api-collections",
            "url": "https://github.com/acme/api-collections.git",
            "tags": ["bruno"],
            "description": "Bruno collections",
        }
    )
    sample_catalog_data["bruno"] = {
        "tags": ["bruno"],
        "default_env": "local",
        "services": [{"id": "cart", "env": "staging", "collection": "cart-api"}],
    }
    write_goat_config(goat_root, sample_catalog_data)
    _write_bruno_tree(goat_root.parent)
    return load_catalog(goat_root)


def test_parse_bru_blocks_and_request(tmp_path: Path):
    path = tmp_path / "search-products.bru"
    path.write_text(SEARCH_BRU, encoding="utf-8")
    names = [name for name, _ in parse_bru_blocks(SEARCH_BRU)]
    assert "meta" in names
    assert "post" in names
    parsed = parse_bru_request(path, tmp_path)
    assert parsed is not None
    assert parsed["name"] == "Search products"
    assert parsed["method"] == "POST"
    assert parsed["url"] == "{{baseUrl}}/search"
    assert "product" in parsed["docs"]


def test_parse_bru_environment_never_returns_values(tmp_path: Path):
    path = tmp_path / "staging.bru"
    path.write_text(
        "vars {\n  baseUrl: https://secret.example\n}\nvars:secret {\n  apiKey: SUPER-SECRET\n}\n",
        encoding="utf-8",
    )
    env = parse_bru_environment(path)
    dumped = str(env)
    assert "SUPER-SECRET" not in dumped
    assert "https://secret.example" not in dumped
    assert env["vars"] == ["baseUrl"]
    assert env["secrets"] == ["apiKey"]


def test_parse_env_vars_requires_key():
    assert parse_env_vars(["productId=abc", "q=shoes"]) == [
        ("productId", "abc"),
        ("q", "shoes"),
    ]
    with pytest.raises(GoatError, match="KEY=value"):
        parse_env_vars(["novalue"])


def test_inventory_lists_repo_collections_and_workflows(
    goat_root: Path, sample_catalog_data: dict
):
    catalog = _catalog_with_bruno(goat_root, sample_catalog_data)
    payload = collect_bruno_inventory(catalog, goat_root)
    assert payload["kind"] == "bruno_inventory"
    assert payload["repos"][0]["name"] == "api-collections"
    assert payload["repos"][0]["cloned"] is True
    assert payload["collections"][0]["id"] == "cart-api"
    assert payload["collections"][0]["request_count"] == 2
    assert "local" in payload["collections"][0]["environments"]
    assert "search" in payload["collections"][0]["folders"]
    services = {item["id"]: item for item in payload["services"]}
    assert services["cart"]["env"] == "staging"
    workflows = {item["id"]: item for item in payload["workflows"]}
    assert "add-to-cart" in workflows
    assert workflows["add-to-cart"]["steps"][0]["request"] == "search/search-products"


def test_requests_and_envs(goat_root: Path, sample_catalog_data: dict):
    catalog = _catalog_with_bruno(goat_root, sample_catalog_data)
    requests = list_bruno_requests(catalog, goat_root, "cart-api")
    ids = [item["id"] for item in requests["requests"]]
    assert any(item.endswith("search/search-products") for item in ids)
    assert all(item["collection"] == "cart-api" for item in requests["requests"])
    envs = list_bruno_envs(catalog, goat_root, "cart-api")
    names = {item["name"] for item in envs["environments"]}
    assert names == {"local", "staging"}
    staging = next(item for item in envs["environments"] if item["name"] == "staging")
    assert "apiKey" in staging["secrets"]
    assert "SUPER-SECRET" not in str(envs)
    assert "https://staging.example.com" not in str(envs)


def test_workflow_plan_includes_bru_command(
    goat_root: Path, sample_catalog_data: dict
):
    catalog = _catalog_with_bruno(goat_root, sample_catalog_data)
    payload = list_bruno_workflows(catalog, goat_root, "add-to-cart")
    workflow = payload["workflows"][0]
    assert workflow["env"] == "staging"
    assert workflow["steps"][0]["pick"]["product_id"] == "body.products[0].id"
    assert workflow["steps"][1]["needs"] == ["product_id"]
    command = workflow["steps"][1]["bru_command"]
    assert command[:3] == ["bru", "run", "cart/add-item.bru"]
    assert "--env" in command
    assert "staging" in command


def test_run_dry_run_redacts_env_vars(
    goat_root: Path, sample_catalog_data: dict
):
    catalog = _catalog_with_bruno(goat_root, sample_catalog_data)
    payload = run_bruno_request(
        catalog,
        goat_root,
        "search/search-products",
        service="cart",
        env_vars=["productId=should-not-leak", "token=sekrit"],
        dry_run=True,
    )
    assert payload["dry_run"] is True
    assert payload["env"] == "staging"
    assert payload["env_var_keys"] == ["productId", "token"]
    command = " ".join(payload["bru_command"])
    assert "should-not-leak" not in command
    assert "sekrit" not in command
    assert "<redacted>" in command
    assert payload["cwd"].endswith("api-collections")


def test_run_invokes_bru(goat_root: Path, sample_catalog_data: dict, monkeypatch):
    catalog = _catalog_with_bruno(goat_root, sample_catalog_data)
    monkeypatch.setattr("goat.bruno.shutil.which", lambda _name: "/usr/bin/bru")

    class Result:
        returncode = 0
        stdout = '{"ok": true}'
        stderr = ""

    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["cwd"] = kwargs["cwd"]
        assert cmd[0] == "bru"
        assert cmd[1] == "run"
        assert "--env" in cmd
        return Result()

    payload = run_bruno_request(
        catalog,
        goat_root,
        "Add to cart",
        env="local",
        run_fn=fake_run,
    )
    assert payload["exit_code"] == 0
    assert payload["stdout"] == '{"ok": true}'
    assert seen["cwd"].endswith("api-collections")
    assert any(str(part).endswith("add-item.bru") for part in seen["cmd"])


def test_run_missing_bru_is_clear(goat_root: Path, sample_catalog_data: dict, monkeypatch):
    catalog = _catalog_with_bruno(goat_root, sample_catalog_data)
    monkeypatch.setattr("goat.bruno.shutil.which", lambda _name: None)
    with pytest.raises(GoatError, match="bru is not on PATH"):
        run_bruno_request(catalog, goat_root, "search/search-products")


def test_unknown_bruno_repo_in_stack(tmp_path: Path, sample_catalog_data: dict):
    sample_catalog_data["bruno"] = {"repos": ["missing-collections"]}
    root = tmp_path / "goat"
    write_goat_config(root, sample_catalog_data)
    with pytest.raises(GoatError, match="unknown repo"):
        load_catalog(root)


def test_empty_inventory_when_no_bruno_tag(catalog, goat_root: Path):
    payload = collect_bruno_inventory(catalog, goat_root)
    assert payload["kind"] == "bruno_inventory"
    assert payload.get("repos") in (None, [])
    assert payload.get("collections") in (None, [])


def test_cli_schema_and_collections(
    goat_root: Path, sample_catalog_data: dict, capsys, monkeypatch
):
    _catalog_with_bruno(goat_root, sample_catalog_data)
    monkeypatch.chdir(goat_root)
    assert main(["--root", str(goat_root), "bruno", "schema"]) == 0
    schema = __import__("json").loads(capsys.readouterr().out)
    assert schema["bruno"]["tags"] == ["bruno"]
    assert "meta {" in schema["bruno"]["request_template"]
    assert main(["--root", str(goat_root), "bruno", "collections"]) == 0
    inventory = __import__("json").loads(capsys.readouterr().out)
    assert inventory["collections"][0]["id"] == "cart-api"
    assert main(
        ["--root", str(goat_root), "bruno", "run", "search-products", "--dry-run"]
    ) == 0
    run = __import__("json").loads(capsys.readouterr().out)
    assert run["dry_run"] is True
    assert run["bru_command"][0] == "bru"


def test_catalog_to_dict_includes_bruno(goat_root: Path, sample_catalog_data: dict):
    from goat.catalog import catalog_to_dict

    catalog = _catalog_with_bruno(goat_root, sample_catalog_data)
    payload = catalog_to_dict(catalog, goat_root)
    assert payload["bruno"]["default_env"] == "local"
    assert payload["bruno"]["workflows_file"] == "goat.workflows.yml"
    assert payload["bruno"]["services"][0]["id"] == "cart"


BRU_WITH_APOSTROPHE = """meta {
  name: X
  type: http
  seq: 1
}

docs {
  Don't drop the blocks that come after this one.
}

post {
  url: {{baseUrl}}/x
}
"""


def test_apostrophe_in_docs_does_not_drop_later_blocks(tmp_path: Path):
    path = tmp_path / "x.bru"
    path.write_text(BRU_WITH_APOSTROPHE, encoding="utf-8")
    names = [name for name, _ in parse_bru_blocks(BRU_WITH_APOSTROPHE)]
    assert names == ["meta", "docs", "post"]
    parsed = parse_bru_request(path, tmp_path)
    assert parsed is not None
    assert parsed["method"] == "POST"
    assert parsed["url"] == "{{baseUrl}}/x"


def test_malformed_workflow_file_warns_and_returns_empty(tmp_path: Path):
    from goat.bruno import parse_workflow_file

    path = tmp_path / "goat.workflows.yml"
    path.write_text("workflows: [oops\n  - broken", encoding="utf-8")
    with pytest.warns(UserWarning, match="malformed"):
        result = parse_workflow_file(path)
    assert result == []


def test_nested_collection_requests_not_folded_into_parent(
    goat_root: Path, sample_catalog_data: dict
):
    catalog = _catalog_with_bruno(goat_root, sample_catalog_data)
    root = goat_root.parent / "api-collections"
    nested = root / "nested"
    nested.mkdir()
    (nested / "bruno.json").write_text(
        '{"version": "1", "name": "nested-api", "type": "collection"}\n',
        encoding="utf-8",
    )
    (nested / "ping.bru").write_text(
        "meta {\n  name: Ping\n  type: http\n  seq: 1\n}\n\nget {\n  url: {{baseUrl}}/ping\n}\n",
        encoding="utf-8",
    )
    payload = collect_bruno_inventory(catalog, goat_root)
    by_name = {item["name"]: item for item in payload["collections"]}
    assert by_name["cart-api"]["request_count"] == 2
    assert by_name["nested-api"]["request_count"] == 1

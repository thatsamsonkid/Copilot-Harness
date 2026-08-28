from __future__ import annotations

import json

import pytest

from coboose import CobooseError
from coboose.figma_client import FigmaClient, parse_figma_target
from coboose.figma_fields import FigmaSettings
from coboose.http import HttpResponse


class FakeHttp:
    def __init__(self, routes: dict[tuple[str, str], HttpResponse]):
        self.routes = routes
        self.calls: list[tuple[str, str]] = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        key = (method.upper(), url.split("?", 1)[0])
        if key not in self.routes:
            raise AssertionError(f"Unexpected request {key}")
        return self.routes[key]


def _json(payload, status=200) -> HttpResponse:
    return HttpResponse(status=status, body=json.dumps(payload), headers={})


def test_parse_figma_target_from_url_and_key():
    target = parse_figma_target(
        "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr/Checkout?node-id=12-34"
    )
    assert target.file_key == "AbCdEfGhIjKlMnOpQr"
    assert target.node_ids == ("12:34",)
    assert target.url.endswith("?node-id=12-34")

    proto = parse_figma_target(
        "https://www.figma.com/proto/AbCdEfGhIjKlMnOpQr/Name?node-id=1:2"
    )
    assert proto.node_ids == ("1:2",)

    key = parse_figma_target("AbCdEfGhIjKlMnOpQr", extra_ids=["12-34", "56:78"])
    assert key.file_key == "AbCdEfGhIjKlMnOpQr"
    assert key.node_ids == ("12:34", "56:78")

    with pytest.raises(CobooseError):
        parse_figma_target("not a figma link")


def test_get_images_projects_urls_and_drops_failed_nodes():
    http = FakeHttp(
        {
            ("GET", "https://api.figma.com/v1/images/AbCdEfGhIjKlMnOpQr"): _json(
                {
                    "err": None,
                    "images": {
                        "12:34": "https://figma-alpha-api.s3.example/one.png",
                        "56:78": None,
                    },
                }
            )
        }
    )
    client = FigmaClient("figd_test", http=http)
    payload = client.get_images(
        "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr/Name?node-id=12-34",
        ids=["12:34", "56:78"],
        settings=FigmaSettings(),
    )
    assert payload["file_key"] == "AbCdEfGhIjKlMnOpQr"
    assert payload["format"] == "png"
    assert payload["scale"] == 2.0
    assert payload["images"] == [
        {"id": "12:34", "url": "https://figma-alpha-api.s3.example/one.png"}
    ]
    assert payload["missing"] == ["56:78"]
    assert http.calls[0][1].startswith(
        "https://api.figma.com/v1/images/AbCdEfGhIjKlMnOpQr?"
    )
    assert "ids=12%3A34%2C56%3A78" in http.calls[0][1]
    assert "format=png" in http.calls[0][1]
    assert "scale=2" in http.calls[0][1]


def test_get_images_requires_node_id():
    client = FigmaClient("figd_test", http=FakeHttp({}))
    with pytest.raises(CobooseError, match="node id"):
        client.get_images("AbCdEfGhIjKlMnOpQr")


def test_get_images_respects_max_ids():
    client = FigmaClient("figd_test", http=FakeHttp({}))
    with pytest.raises(CobooseError, match="max is 1"):
        client.get_images(
            "AbCdEfGhIjKlMnOpQr",
            ids=["1:1", "1:2"],
            settings=FigmaSettings(max_ids=1),
        )


def test_get_images_rejects_unknown_format():
    client = FigmaClient("figd_test", http=FakeHttp({}))
    with pytest.raises(CobooseError, match="format"):
        client.get_images(
            "AbCdEfGhIjKlMnOpQr",
            ids=["1:1"],
            image_format="gif",
        )


def test_myself_hides_raw_profile_fields():
    http = FakeHttp(
        {
            ("GET", "https://api.figma.com/v1/me"): _json(
                {
                    "id": "123",
                    "email": "ada@acme.test",
                    "handle": "Ada",
                    "img_url": "https://example/avatar.png",
                }
            )
        }
    )
    payload = FigmaClient("figd_test", http=http).myself()
    assert payload == {"authenticated": True, "handle": "Ada", "email": "ada@acme.test"}


def test_images_markdown_lists_urls():
    from coboose.output import render

    payload = {
        "file_key": "AbCdEfGhIjKlMnOpQr",
        "url": "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr?node-id=12-34",
        "format": "png",
        "scale": 2,
        "images": [{"id": "12:34", "url": "https://example/one.png"}],
        "missing": ["56:78"],
    }
    markdown = render(payload, "markdown")
    assert "https://example/one.png" in markdown
    assert "12:34" in markdown
    assert "56:78" in markdown
    assert "Simple Browser" in markdown


def test_auth_failure_does_not_echo_token():
    http = FakeHttp(
        {("GET", "https://api.figma.com/v1/me"): _json({"err": "bad"}, status=403)}
    )
    with pytest.raises(CobooseError, match="denied") as exc:
        FigmaClient("figd_secret", http=http).myself()
    assert "figd_secret" not in str(exc.value)


def test_get_comments_filters_to_node_and_replies():
    http = FakeHttp(
        {
            ("GET", "https://api.figma.com/v1/files/AbCdEfGhIjKlMnOpQr/comments"): _json(
                {
                    "comments": [
                        {
                            "id": "1",
                            "message": "Use the brand navy",
                            "created_at": "2026-01-01T00:00:00Z",
                            "user": {"handle": "Ada", "email": "hidden@example"},
                            "client_meta": {"node_id": "12:34"},
                            "resolved_at": None,
                        },
                        {
                            "id": "2",
                            "parent_id": "1",
                            "message": "Already in the token file",
                            "created_at": "2026-01-02T00:00:00Z",
                            "user": {"handle": "Grace"},
                            "client_meta": {},
                        },
                        {
                            "id": "3",
                            "message": "Other frame",
                            "created_at": "2026-01-03T00:00:00Z",
                            "user": {"handle": "Other"},
                            "client_meta": {"node_id": "56:78"},
                        },
                    ]
                }
            )
        }
    )
    payload = FigmaClient("figd_test", http=http).get_comments(
        "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr/Name?node-id=12-34"
    )
    assert payload["file_key"] == "AbCdEfGhIjKlMnOpQr"
    assert [item["message"] for item in payload["comments"]] == [
        "Use the brand navy",
        "Already in the token file",
    ]
    assert payload["comments"][0] == {
        "author": "Ada",
        "created": "2026-01-01T00:00:00Z",
        "message": "Use the brand navy",
        "node_id": "12:34",
        "resolved": False,
    }
    assert "email" not in str(payload)
    assert "hidden@example" not in str(payload)


def test_get_comments_can_return_whole_file():
    http = FakeHttp(
        {
            ("GET", "https://api.figma.com/v1/files/AbCdEfGhIjKlMnOpQr/comments"): _json(
                {
                    "comments": [
                        {
                            "id": "1",
                            "message": "A",
                            "created_at": "2026-01-01T00:00:00Z",
                            "user": {"handle": "Ada"},
                            "client_meta": {"node_id": "12:34"},
                        },
                        {
                            "id": "2",
                            "message": "B",
                            "created_at": "2026-01-02T00:00:00Z",
                            "user": {"handle": "Grace"},
                            "client_meta": {"node_id": "56:78"},
                        },
                    ]
                }
            )
        }
    )
    payload = FigmaClient("figd_test", http=http).get_comments(
        "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr/Name?node-id=12-34",
        whole_file=True,
    )
    assert [item["message"] for item in payload["comments"]] == ["A", "B"]


def test_get_comments_caps_to_newest():
    http = FakeHttp(
        {
            ("GET", "https://api.figma.com/v1/files/AbCdEfGhIjKlMnOpQr/comments"): _json(
                {
                    "comments": [
                        {
                            "id": "1",
                            "message": "old",
                            "created_at": "2026-01-01T00:00:00Z",
                            "user": {"handle": "Ada"},
                        },
                        {
                            "id": "2",
                            "message": "new",
                            "created_at": "2026-01-03T00:00:00Z",
                            "user": {"handle": "Grace"},
                        },
                    ]
                }
            )
        }
    )
    payload = FigmaClient("figd_test", http=http).get_comments(
        "AbCdEfGhIjKlMnOpQr",
        settings=FigmaSettings(max_comments=1),
    )
    assert [item["message"] for item in payload["comments"]] == ["new"]


def test_comments_403_mentions_file_comments_scope():
    http = FakeHttp(
        {
            ("GET", "https://api.figma.com/v1/files/AbCdEfGhIjKlMnOpQr/comments"): _json(
                {"err": "bad"}, status=403
            )
        }
    )
    with pytest.raises(CobooseError, match="file_comments:read") as exc:
        FigmaClient("figd_secret", http=http).get_comments("AbCdEfGhIjKlMnOpQr")
    assert "figd_secret" not in str(exc.value)


def test_get_nodes_passes_raw_figma_objects():
    document = {
        "id": "12:34",
        "name": "Primary button",
        "type": "FRAME",
        "absoluteBoundingBox": {"x": 0, "y": 0, "width": 160, "height": 40},
        "fills": [{"type": "SOLID", "color": {"r": 0.1, "g": 0.2, "b": 0.4, "a": 1}}],
        "children": [
            {
                "id": "12:35",
                "name": "Label",
                "type": "TEXT",
                "characters": "Continue",
                "style": {"fontFamily": "Inter", "fontSize": 14},
            }
        ],
    }
    raw_entry = {
        "document": document,
        "components": {"12:35": {"name": "Label", "key": "comp"}},
        "styles": {},
        "schemaVersion": 0,
    }
    http = FakeHttp(
        {
            ("GET", "https://api.figma.com/v1/files/AbCdEfGhIjKlMnOpQr/nodes"): _json(
                {"nodes": {"12:34": raw_entry, "56:78": None}}
            )
        }
    )
    payload = FigmaClient("figd_test", http=http).get_nodes(
        "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr/Name?node-id=12-34",
        ids=["12:34", "56:78"],
    )
    assert payload["depth"] == 2
    assert payload["missing"] == ["56:78"]
    assert payload["nodes"]["12:34"] == raw_entry
    assert payload["nodes"]["56:78"] is None
    assert "targeted frame" in payload["note"]
    assert "absoluteBoundingBox" in payload["nodes"]["12:34"]["document"]
    assert "ids=12%3A34%2C56%3A78" in http.calls[0][1]
    assert "depth=2" in http.calls[0][1]


def test_get_nodes_requires_node_id_and_caps_depth():
    client = FigmaClient("figd_test", http=FakeHttp({}))
    with pytest.raises(CobooseError, match="node id"):
        client.get_nodes("AbCdEfGhIjKlMnOpQr")
    with pytest.raises(CobooseError, match="max_depth"):
        client.get_nodes(
            "AbCdEfGhIjKlMnOpQr",
            ids=["1:1"],
            depth=9,
            settings=FigmaSettings(max_depth=3),
        )


def test_nodes_and_comments_markdown():
    from coboose.output import render

    comments = render(
        {
            "file_key": "AbCdEfGhIjKlMnOpQr",
            "url": "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr?node-id=12-34",
            "comments": [
                {
                    "author": "Ada",
                    "created": "2026-01-01",
                    "message": "Use navy",
                    "node_id": "12:34",
                    "resolved": False,
                }
            ],
        },
        "markdown",
    )
    assert "Use navy" in comments
    assert "12:34" in comments

    nodes = render(
        {
            "file_key": "AbCdEfGhIjKlMnOpQr",
            "url": "https://www.figma.com/design/AbCdEfGhIjKlMnOpQr?node-id=12-34",
            "depth": 2,
            "note": "Raw Figma node JSON. Use only on a small targeted frame.",
            "nodes": {
                "12:34": {
                    "document": {
                        "id": "12:34",
                        "name": "Button",
                        "absoluteBoundingBox": {"width": 160, "height": 40},
                    }
                }
            },
            "missing": [],
        },
        "markdown",
    )
    assert "Button" in nodes
    assert "absoluteBoundingBox" in nodes
    assert "targeted frame" in nodes

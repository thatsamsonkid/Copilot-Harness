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

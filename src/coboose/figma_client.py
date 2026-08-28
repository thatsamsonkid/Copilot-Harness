from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import parse_qs, quote, urlparse

from coboose import CobooseError
from coboose.envspec import EnvVar, find_var, resolve_var
from coboose.figma_fields import (
    ALLOWED_FORMATS,
    DEFAULT_FORMAT,
    DEFAULT_SCALE,
    FigmaSettings,
    project_images,
)
from coboose.http import HttpClient, HttpResponse
from coboose.projection import project

FIGMA_API = "https://api.figma.com"
FIGMA_DOC = "docs/figma-access-token.md"
FIGMA_TOKEN_NAMES = ("FIGMA_ACCESS_TOKEN", "FIGMA_TOKEN", "FIGMA_API_TOKEN")

FIGMA_TOKEN_VAR = EnvVar(
    name="FIGMA_ACCESS_TOKEN",
    secret=True,
    required=False,
    aliases=("FIGMA_TOKEN", "FIGMA_API_TOKEN"),
    docs=FIGMA_DOC,
    account="figma-access-token",
    prompt="Figma personal access token",
)

_FILE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?figma\.com/"
    r"(?:file|design|proto|board|deck|files)/([A-Za-z0-9]+)",
    re.IGNORECASE,
)
_FILE_KEY_RE = re.compile(r"^[A-Za-z0-9]{8,}$")


@dataclass(frozen=True)
class FigmaTarget:
    file_key: str
    node_ids: tuple[str, ...]
    url: str


def parse_figma_target(value: str, extra_ids: Iterable[str] | None = None) -> FigmaTarget:
    text = (value or "").strip()
    if not text:
        raise CobooseError("A Figma file key or URL is required")

    file_key = ""
    node_ids: list[str] = []
    match = _FILE_URL_RE.search(text)
    if match:
        file_key = match.group(1)
        parsed = urlparse(text if "://" in text else f"https://{text}")
        query = parse_qs(parsed.query)
        raw_nodes = query.get("node-id") or query.get("node_id") or []
        for item in raw_nodes:
            node_ids.extend(_split_ids(item))
    elif _FILE_KEY_RE.fullmatch(text):
        file_key = text
    else:
        raise CobooseError(f"Could not parse a Figma file key or URL from: {value}")

    if extra_ids:
        node_ids = list(_normalize_ids(extra_ids))
    else:
        node_ids = list(_normalize_ids(node_ids))

    browse = f"https://www.figma.com/design/{file_key}"
    if len(node_ids) == 1:
        browse = f"{browse}?node-id={node_ids[0].replace(':', '-')}"
    return FigmaTarget(file_key=file_key, node_ids=tuple(node_ids), url=browse)


def figma_token_from_env(variables: Iterable[EnvVar] | None = None) -> str:
    variable = FIGMA_TOKEN_VAR
    if variables is not None:
        try:
            variable = find_var(variables, "FIGMA_ACCESS_TOKEN")
        except CobooseError:
            pass
    token, _source = resolve_var(variable)
    if token:
        return token
    raise CobooseError(
        "Missing Figma settings: FIGMA_ACCESS_TOKEN. "
        "Store the personal access token with `uv run coboose figma login` "
        "(macOS Keychain or Windows Credential Manager), or set "
        f"FIGMA_ACCESS_TOKEN in .env as a fallback. See {FIGMA_DOC}. "
        "Do not paste the token into chat."
    )


def figma_var(variables: Iterable[EnvVar] | None = None) -> EnvVar:
    if variables is not None:
        try:
            return find_var(variables, "FIGMA_ACCESS_TOKEN")
        except CobooseError:
            pass
    return FIGMA_TOKEN_VAR


class FigmaClient:
    def __init__(
        self,
        token: str,
        http: HttpClient | None = None,
        timeout: float = 30,
        base_url: str = FIGMA_API,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http or HttpClient()
        self._timeout = timeout
        self._token = token

    def myself(self) -> dict[str, Any]:
        payload = self._json("GET", "/v1/me")
        return {
            "authenticated": True,
            "handle": payload.get("handle"),
            "email": payload.get("email"),
        }

    def get_images(
        self,
        file: str,
        *,
        ids: Iterable[str] | None = None,
        image_format: str | None = None,
        scale: float | None = None,
        settings: FigmaSettings | None = None,
    ) -> dict[str, Any]:
        settings = settings or FigmaSettings()
        target = parse_figma_target(file, extra_ids=ids)
        if not target.node_ids:
            raise CobooseError(
                "A Figma node id is required. Paste a frame URL that includes "
                "`node-id`, or pass `--ids 12:34`."
            )
        if len(target.node_ids) > settings.max_ids:
            raise CobooseError(
                f"Refusing to export {len(target.node_ids)} nodes "
                f"(max is {settings.max_ids} in catalog/stack.yaml figma.max_ids)."
            )
        chosen_format = (image_format or settings.default_format or DEFAULT_FORMAT).lower()
        if chosen_format not in ALLOWED_FORMATS:
            raise CobooseError(
                f"Unsupported Figma image format {chosen_format!r}. "
                f"Use one of: {', '.join(ALLOWED_FORMATS)}."
            )
        chosen_scale = settings.default_scale if scale is None else float(scale)
        if chosen_scale < 0.01 or chosen_scale > 4:
            raise CobooseError("Figma image scale must be between 0.01 and 4.")

        params = {
            "ids": ",".join(target.node_ids),
            "format": chosen_format,
            "scale": _format_scale(chosen_scale),
        }
        payload = self._json(
            "GET",
            f"/v1/images/{quote(target.file_key)}",
            params=params,
        )
        if payload.get("err"):
            raise CobooseError(f"Figma images failed: {payload['err']}")

        raw_images = payload.get("images")
        if not isinstance(raw_images, dict):
            raise CobooseError("Figma returned an images payload without an images map.")

        images: list[dict[str, Any]] = []
        missing: list[str] = []
        item_spec = settings.image_item_projection()
        for node_id in target.node_ids:
            url = raw_images.get(node_id)
            if not url:
                # Figma may echo the hyphen form used in some URLs.
                url = raw_images.get(node_id.replace(":", "-"))
            if url:
                images.append(project({"id": node_id, "url": url}, item_spec))
            else:
                missing.append(node_id)

        return project_images(
            {
                "file_key": target.file_key,
                "url": target.url,
                "format": chosen_format,
                "scale": chosen_scale,
                "images": images,
                "missing": missing,
            },
            settings,
        )

    def _json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> Any:
        return self._decode(self._request(method, path, params=params), method)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> HttpResponse:
        url = self.base_url + path
        if params:
            query = "&".join(
                f"{quote(key)}={quote(value)}" for key, value in params.items()
            )
            url = f"{url}?{query}"
        return self._http.request(
            method,
            url,
            headers={
                "X-Figma-Token": self._token,
                "Accept": "application/json",
            },
            timeout=self._timeout,
        )

    def _decode(self, response: HttpResponse, method: str) -> Any:
        if response.status == 401:
            raise CobooseError(
                "Figma authentication failed. Check the token in the OS keychain "
                "(`coboose figma login`) or .env; do not print them."
            )
        if response.status == 403:
            raise CobooseError(
                "Figma denied access to this file. Confirm the token can read "
                f"file content ({FIGMA_DOC})."
            )
        if response.status == 404:
            raise CobooseError("Figma file or node not found.")
        if response.status >= 400:
            raise CobooseError(
                f"Figma API {method} failed ({response.status}): {_error_message(response)}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise CobooseError("Figma returned a non-JSON response") from exc


def _error_message(response: HttpResponse) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.body[:300] or "no body"
    if isinstance(payload, dict):
        if payload.get("err"):
            return str(payload["err"])
        if payload.get("message"):
            return str(payload["message"])
    return response.body[:300] or "no body"


def _split_ids(value: str) -> list[str]:
    return [item.strip() for item in (value or "").replace(";", ",").split(",") if item.strip()]


def _normalize_ids(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        for item in _split_ids(str(raw)):
            node_id = item.replace("-", ":", 1) if ":" not in item else item
            if node_id in seen:
                continue
            seen.add(node_id)
            result.append(node_id)
    return result


def _format_scale(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)

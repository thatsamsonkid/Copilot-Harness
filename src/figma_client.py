from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import parse_qs, quote, urlparse

from goat import GoatError
from goat.envspec import EnvVar, find_var, resolve_var
from goat.figma_fields import (
    ALLOWED_FORMATS,
    DEFAULT_FORMAT,
    DEFAULT_SCALE,
    NODES_NOTE,
    FigmaSettings,
    project_comments,
    project_images,
)
from goat.http import HttpClient, HttpResponse
from goat.projection import project

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
        raise GoatError("A Figma file key or URL is required")

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
        raise GoatError(f"Could not parse a Figma file key or URL from: {value}")

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
        except GoatError:
            pass
    token, _source = resolve_var(variable)
    if token:
        return token
    raise GoatError(
        "Missing Figma settings: FIGMA_ACCESS_TOKEN. "
        "Store the personal access token with `uv run goat figma login` "
        "(macOS Keychain or Windows Credential Manager), or set "
        f"FIGMA_ACCESS_TOKEN in .env as a fallback. See {FIGMA_DOC}. "
        "Do not paste the token into chat."
    )


def figma_var(variables: Iterable[EnvVar] | None = None) -> EnvVar:
    if variables is not None:
        try:
            return find_var(variables, "FIGMA_ACCESS_TOKEN")
        except GoatError:
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
        target = _require_node_ids(file, ids, settings, action="export")
        chosen_format = (image_format or settings.default_format or DEFAULT_FORMAT).lower()
        if chosen_format not in ALLOWED_FORMATS:
            raise GoatError(
                f"Unsupported Figma image format {chosen_format!r}. "
                f"Use one of: {', '.join(ALLOWED_FORMATS)}."
            )
        chosen_scale = settings.default_scale if scale is None else float(scale)
        if chosen_scale < 0.01 or chosen_scale > 4:
            raise GoatError("Figma image scale must be between 0.01 and 4.")

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
            raise GoatError(f"Figma images failed: {payload['err']}")

        raw_images = payload.get("images")
        if not isinstance(raw_images, dict):
            raise GoatError("Figma returned an images payload without an images map.")

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

    def get_comments(
        self,
        file: str,
        *,
        ids: Iterable[str] | None = None,
        whole_file: bool = False,
        settings: FigmaSettings | None = None,
    ) -> dict[str, Any]:
        settings = settings or FigmaSettings()
        if not settings.wants_comments():
            raise GoatError(
                "Figma comments are disabled in catalog/stack.yaml "
                "(figma.include_comments / figma.comment_fields)."
            )
        target = parse_figma_target(file, extra_ids=ids)
        payload = self._json("GET", f"/v1/files/{quote(target.file_key)}/comments")
        if isinstance(payload, dict) and payload.get("err"):
            raise GoatError(f"Figma comments failed: {payload['err']}")

        raw = payload.get("comments") if isinstance(payload, dict) else None
        if not isinstance(raw, list):
            raise GoatError("Figma returned a comments payload without a comments list.")

        comments = [normalize_comment(item) for item in raw if isinstance(item, dict)]
        if target.node_ids and not whole_file:
            comments = _comments_for_nodes(comments, target.node_ids)
        comments = _newest_comments(comments, settings.max_comments)
        return project_comments(
            {
                "file_key": target.file_key,
                "url": target.url,
                "comments": [
                    project(item, settings.comment_item_projection()) for item in comments
                ],
            },
            settings,
        )

    def get_nodes(
        self,
        file: str,
        *,
        ids: Iterable[str] | None = None,
        depth: int | None = None,
        settings: FigmaSettings | None = None,
    ) -> dict[str, Any]:
        settings = settings or FigmaSettings()
        target = _require_node_ids(file, ids, settings, action="inspect")
        chosen_depth = settings.default_depth if depth is None else int(depth)
        if chosen_depth < 1 or chosen_depth > settings.max_depth:
            raise GoatError(
                f"Figma node depth must be between 1 and {settings.max_depth} "
                "(catalog/stack.yaml figma.max_depth)."
            )

        payload = self._json(
            "GET",
            f"/v1/files/{quote(target.file_key)}/nodes",
            params={
                "ids": ",".join(target.node_ids),
                "depth": str(chosen_depth),
            },
        )
        if isinstance(payload, dict) and payload.get("err"):
            raise GoatError(f"Figma nodes failed: {payload['err']}")

        raw_nodes = payload.get("nodes") if isinstance(payload, dict) else None
        if not isinstance(raw_nodes, dict):
            raise GoatError("Figma returned a nodes payload without a nodes map.")

        missing: list[str] = []
        for node_id in target.node_ids:
            entry = raw_nodes.get(node_id)
            if entry is None:
                entry = raw_nodes.get(node_id.replace(":", "-"))
            if not isinstance(entry, dict):
                missing.append(node_id)

        return {
            "file_key": target.file_key,
            "url": target.url,
            "depth": chosen_depth,
            "note": NODES_NOTE,
            "nodes": raw_nodes,
            "missing": missing,
        }

    def _json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> Any:
        return self._decode(self._request(method, path, params=params), method, path=path)

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

    def _decode(self, response: HttpResponse, method: str, path: str = "") -> Any:
        if response.status == 401:
            raise GoatError(
                "Figma authentication failed. Check the token in the OS keychain "
                "(`goat figma login`) or .env; do not print them."
            )
        if response.status == 403:
            if "/comments" in path:
                raise GoatError(
                    "Figma denied access to comments. Confirm the token includes "
                    f"file_comments:read ({FIGMA_DOC})."
                )
            raise GoatError(
                "Figma denied access to this file. Confirm the token can read "
                f"file content ({FIGMA_DOC})."
            )
        if response.status == 404:
            raise GoatError("Figma file or node not found.")
        if response.status >= 400:
            raise GoatError(
                f"Figma API {method} failed ({response.status}): {_error_message(response)}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise GoatError("Figma returned a non-JSON response") from exc


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


def _require_node_ids(
    file: str,
    ids: Iterable[str] | None,
    settings: FigmaSettings,
    *,
    action: str,
) -> FigmaTarget:
    target = parse_figma_target(file, extra_ids=ids)
    if not target.node_ids:
        raise GoatError(
            "A Figma node id is required. Paste a frame URL that includes "
            "`node-id`, or pass `--ids 12:34`."
        )
    if len(target.node_ids) > settings.max_ids:
        raise GoatError(
            f"Refusing to {action} {len(target.node_ids)} nodes "
            f"(max is {settings.max_ids} in catalog/stack.yaml figma.max_ids)."
        )
    return target


def normalize_comment(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("client_meta") if isinstance(payload.get("client_meta"), dict) else {}
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    return {
        "id": payload.get("id"),
        "parent_id": payload.get("parent_id"),
        "author": user.get("handle") or user.get("email") or user.get("id"),
        "created": payload.get("created_at") or payload.get("createdAt"),
        "message": payload.get("message") or "",
        "node_id": _comment_node_id(meta),
        "resolved": bool(payload.get("resolved_at") or payload.get("resolvedAt")),
    }


def _comment_node_id(meta: dict[str, Any]) -> str | None:
    raw = meta.get("node_id") or meta.get("nodeId")
    if raw is None:
        return None
    return str(raw).replace("-", ":", 1) if ":" not in str(raw) else str(raw)


def _comments_for_nodes(
    comments: list[dict[str, Any]],
    node_ids: Iterable[str],
) -> list[dict[str, Any]]:
    wanted = {item.replace("-", ":", 1) if ":" not in item else item for item in node_ids}
    matched_ids = {
        str(item.get("id"))
        for item in comments
        if item.get("id") is not None and item.get("node_id") in wanted
    }
    changed = True
    while changed:
        changed = False
        for item in comments:
            comment_id = item.get("id")
            parent_id = item.get("parent_id")
            if comment_id is None or str(comment_id) in matched_ids:
                continue
            if parent_id is not None and str(parent_id) in matched_ids:
                matched_ids.add(str(comment_id))
                changed = True
    return [item for item in comments if item.get("id") is not None and str(item["id"]) in matched_ids]


def _newest_comments(comments: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit < 1:
        return []
    ordered = sorted(comments, key=lambda item: str(item.get("created") or ""), reverse=True)
    return list(reversed(ordered[:limit]))

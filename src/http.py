from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse to follow HTTP redirects.

    urllib's default handler replays request headers (including Authorization /
    X-Figma-Token) onto the redirect target even across hosts, which would leak
    credentials to wherever a misconfigured or hostile endpoint points. These
    are JSON APIs that should never redirect, so a 3xx is surfaced as an error
    instead of being followed.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


_OPENER = urllib.request.build_opener(_NoRedirectHandler)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: str
    headers: dict[str, str]

    def json(self) -> Any:
        if not self.body:
            return None
        return json.loads(self.body)


class HttpClient:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: Any = None,
        timeout: float = 30,
    ) -> HttpResponse:
        data = None
        request_headers = dict(headers or {})
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(
            url, data=data, headers=request_headers, method=method.upper()
        )
        try:
            with _OPENER.open(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return HttpResponse(
                    status=response.getcode(),
                    body=body,
                    headers={key: value for key, value in response.headers.items()},
                )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return HttpResponse(
                status=exc.code,
                body=body,
                headers={key: value for key, value in exc.headers.items()}
                if exc.headers
                else {},
            )

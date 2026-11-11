"""
Refuse requests from other web pages before they reach a route.

The API has no authentication: it trusts that only the app's own UI and local
tools (curl, MCP clients) can reach it. CORS alone does not hold that line:
a page on another site can still send a "simple" request (a GET, or a POST
with no body, a form or text/plain), which runs even though the page cannot
read the reply, and a DNS-rebinding page is same-origin, so CORS never applies.

RequestGuard closes both gaps:
- Origin: a browser sends it on every cross-origin request. One that is
  neither an allowed origin (the app's UI) nor the server's own origin is
  refused. Requests without an Origin (curl, MCP clients) pass.
- Host: on a loopback-only server, a Host header that is not a loopback name
  (localhost, 127.x.x.x, ::1) is refused, so a page that resolves its own
  domain to 127.0.0.1 cannot talk to the API.
"""

import json
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from adapters.mcp.server import is_loopback_host
from config import ServerConfig, url_origin
from utils.logger import get_logger

logger = get_logger(__name__)


def _host_name(host_header: str) -> str:
    """The host name of a Host header value, without port or IPv6 brackets."""
    try:
        return urlsplit(f"//{host_header}").hostname or ""
    except ValueError:
        return ""


class RequestGuard:
    """ASGI middleware refusing disallowed Origin and (when loopback-only) Host headers."""

    def __init__(self, app: ASGIApp, allowed_origins: frozenset[str], loopback_only: bool) -> None:
        self.app = app
        self.allowed_origins = allowed_origins
        self.loopback_only = loopback_only

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        reason = self._refusal(scope)
        if reason is None:
            await self.app(scope, receive, send)
            return

        logger.warning("Refused %s %s: %s", scope.get("method", "WS"), scope["path"], reason)
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = json.dumps({"detail": reason}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    def _refusal(self, scope: Scope) -> str | None:
        """Why the request is refused, or None when it may go through."""
        headers = Headers(scope=scope)
        host = headers.get("host", "")
        if self.loopback_only and not is_loopback_host(_host_name(host)):
            return "Host is not a local address."

        origin = headers.get("origin")
        if origin is None:
            return None
        scheme = "https" if scope.get("scheme") in ("https", "wss") else "http"
        normalised = url_origin(origin)
        if normalised is not None and (
            normalised in self.allowed_origins or normalised == url_origin(f"{scheme}://{host}")
        ):
            return None
        return "Origin is not allowed."


def add_browser_guards(app: FastAPI, server: ServerConfig) -> None:
    """
    Let only the app's own UI call the API from a browser: CORS approval for
    the UI origins (server.ui_origins(); a '*' entry is ignored, since the API
    has no authentication) and, outermost so it runs first, RequestGuard.
    """
    allowed_origins = server.ui_origins()
    if "*" in server.cors_origins:
        logger.warning(
            "server.cors_origins '*' is ignored; allowed browser origins: %s. To open the UI"
            " at another origin (e.g. http://127.0.0.1:3100), list it in server.cors_origins",
            sorted(allowed_origins),
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        RequestGuard,
        allowed_origins=allowed_origins,
        loopback_only=is_loopback_host(server.host),
    )

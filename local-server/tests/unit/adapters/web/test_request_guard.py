"""
Browser guards: only the app's own UI may call the API from a web page.

Uses add_browser_guards, the same wiring app.py installs, on a small app.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from adapters.web.request_guard import add_browser_guards
from config import ServerConfig

UI = "http://localhost:3100"
EVIL = "https://evil.example"
API = "http://127.0.0.1:8000"


def _client(server: ServerConfig, base_url: str = API) -> tuple[TestClient, list[str]]:
    """A guarded app with a GET and a bodiless POST; the list records POSTs that ran."""
    app = FastAPI()
    applied: list[str] = []

    @app.get("/api/v1/things")
    def list_things() -> dict:
        return {"things": []}

    @app.post("/api/v1/things/apply")
    def apply_things() -> dict:
        applied.append("applied")
        return {"applied": True}

    @app.websocket("/ws")
    async def socket(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.close()

    add_browser_guards(app, server)
    return TestClient(app, base_url=base_url), applied


@pytest.fixture
def guarded() -> tuple[TestClient, list[str]]:
    """The user's live setup: loopback host, default UI, cors_origins ['*']."""
    return _client(ServerConfig(host="127.0.0.1", cors_origins=["*"]))


class TestOtherOrigins:
    """A page on another site gets no CORS approval and its requests do not run."""

    def test_simple_get_is_refused_without_cors_approval(self, guarded) -> None:
        client, _ = guarded
        response = client.get("/api/v1/things", headers={"Origin": EVIL})
        assert response.status_code == 403
        assert "access-control-allow-origin" not in response.headers

    def test_preflight_for_a_post_gets_no_cors_approval(self, guarded) -> None:
        client, _ = guarded
        response = client.options(
            "/api/v1/things/apply",
            headers={
                "Origin": EVIL,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 403
        assert "access-control-allow-origin" not in response.headers

    def test_simple_post_does_not_run(self, guarded) -> None:
        """A bodiless POST needs no preflight, so CORS alone would let it run."""
        client, applied = guarded
        response = client.post("/api/v1/things/apply", headers={"Origin": EVIL})
        assert response.status_code == 403
        assert "access-control-allow-origin" not in response.headers
        assert applied == []

    @pytest.mark.parametrize("origin", ["null", "http://localhost:3101", "https://localhost:3100"])
    def test_lookalike_and_opaque_origins_are_refused(self, guarded, origin: str) -> None:
        client, _ = guarded
        assert client.get("/api/v1/things", headers={"Origin": origin}).status_code == 403

    def test_websocket_from_another_origin_is_closed(self, guarded) -> None:
        client, _ = guarded
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws", headers={"Origin": EVIL}):
                pass


class TestTheAppsOwnUi:
    """The UI on :3100 keeps working across origins."""

    def test_simple_get_is_approved(self, guarded) -> None:
        client, _ = guarded
        response = client.get("/api/v1/things", headers={"Origin": UI})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == UI
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_preflight_for_a_post_is_approved(self, guarded) -> None:
        client, _ = guarded
        response = client.options(
            "/api/v1/things/apply",
            headers={
                "Origin": UI,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == UI

    def test_post_runs(self, guarded) -> None:
        client, applied = guarded
        response = client.post("/api/v1/things/apply", headers={"Origin": UI})
        assert response.status_code == 200
        assert applied == ["applied"]

    def test_listed_origins_are_allowed_too(self) -> None:
        """A packaged desktop shell's origin is added through cors_origins."""
        client, _ = _client(ServerConfig(cors_origins=["tauri://localhost"]))
        response = client.get("/api/v1/things", headers={"Origin": "tauri://localhost"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "tauri://localhost"

    def test_no_ui_means_no_browser_origin_is_allowed(self) -> None:
        client, _ = _client(ServerConfig(ui_base_url=None, cors_origins=["*"]))
        assert client.get("/api/v1/things", headers={"Origin": UI}).status_code == 403


class TestNonBrowserAndSameOriginCallers:
    """Callers that send no Origin, or the server's own origin, are not affected."""

    def test_no_origin_passes(self, guarded) -> None:
        """curl, scripts and MCP clients send no Origin header."""
        client, applied = guarded
        assert client.get("/api/v1/things").status_code == 200
        assert client.post("/api/v1/things/apply").status_code == 200
        assert applied == ["applied"]

    def test_the_servers_own_origin_passes(self, guarded) -> None:
        """Same-origin pages such as /docs send their own origin on a POST."""
        client, _ = guarded
        response = client.post("/api/v1/things/apply", headers={"Origin": API})
        assert response.status_code == 200


class TestHostHeader:
    """On a loopback server, a non-local Host header (DNS rebinding) is refused."""

    def test_rebinding_host_is_refused_even_as_same_origin(self) -> None:
        client, applied = _client(ServerConfig(host="127.0.0.1"), base_url="http://evil.example:8000")
        response = client.post("/api/v1/things/apply", headers={"Origin": "http://evil.example:8000"})
        assert response.status_code == 403
        assert applied == []
        assert client.get("/api/v1/things").status_code == 403

    @pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1:8000", "[::1]:8000", "localhost"])
    def test_loopback_hosts_pass(self, host: str) -> None:
        client, _ = _client(ServerConfig(host="127.0.0.1"))
        assert client.get("/api/v1/things", headers={"Host": host}).status_code == 200

    @pytest.mark.parametrize("host", ["localhost.evil.example:8000", "0.0.0.0:8000", ""])
    def test_other_hosts_are_refused(self, host: str) -> None:
        client, _ = _client(ServerConfig(host="127.0.0.1"))
        assert client.get("/api/v1/things", headers={"Host": host}).status_code == 403

    def test_host_is_not_checked_when_the_server_listens_beyond_loopback(self) -> None:
        client, _ = _client(ServerConfig(host="0.0.0.0"), base_url="http://192.168.1.20:8000")
        assert client.get("/api/v1/things").status_code == 200
        assert client.get("/api/v1/things", headers={"Origin": EVIL}).status_code == 403

"""
Integration tests for the MCP server (#1337): JSON-RPC over streamable HTTP to the
/mcp endpoint, serving the chat's real read-only tools over a DR-shaped
workspace in SQLite.
"""

import json
from contextlib import asynccontextmanager

import httpx
from starlette.applications import Starlette
from starlette.routing import Route

from adapters.chat.tools import build_chat_tools
from adapters.mcp.links import EntityLinks
from adapters.mcp.server import (
    McpEndpoint,
    build_mcp_server,
    build_session_manager,
    loopback_security,
)
from tests.integration.chat.conftest import DR_VISION, OPERATION_ID, TAXONOMY_ID

TOKEN = "test-mcp-token"
HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
    "authorization": f"Bearer {TOKEN}",
}
UI = "http://localhost:3100"


@asynccontextmanager
async def mcp_client(workspace):
    """
    An HTTP client for /mcp with the session manager running.

    A context manager rather than a fixture: the manager's task group must be
    entered and exited in the same task, and async fixtures tear down in another.
    """
    tools = build_chat_tools(workspace.ontology, workspace.graph)
    server = build_mcp_server(tools, workspace.ontology, EntityLinks(UI))
    manager = build_session_manager(server, loopback_security())
    endpoint = McpEndpoint()
    app = Starlette(routes=[Route("/mcp", endpoint)])
    async with manager.run():
        endpoint.session_manager = manager
        endpoint.auth_token = TOKEN
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
            yield c


async def rpc(client, method, params=None, headers=None):
    """POST one JSON-RPC request to /mcp and return the HTTP response."""
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return await client.post("/mcp", json=body, headers={**HEADERS, **(headers or {})})


async def result_of(client, method, params=None):
    response = await rpc(client, method, params)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "error" not in payload, payload
    return payload["result"]


async def test_initialize_names_the_server_and_its_instructions(
    dr_workspace,
):
    async with mcp_client(dr_workspace) as client:
        result = await result_of(
            client,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        )

        assert result["serverInfo"]["name"] == "context-studio"
        assert "list_taxonomies" in result["instructions"]
        assert {"tools", "resources"} <= result["capabilities"].keys()


async def test_lists_the_chat_tools_with_their_schemas(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        result = await result_of(client, "tools/list")

        chat_tools = build_chat_tools(dr_workspace.ontology, dr_workspace.graph)
        assert [t["name"] for t in result["tools"]] == [t.spec.name for t in chat_tools]
        by_name = {t["name"]: t for t in result["tools"]}
        for tool in chat_tools:
            assert by_name[tool.spec.name]["inputSchema"] == dict(tool.spec.input_schema)
            assert by_name[tool.spec.name]["description"] == tool.spec.description


async def test_tool_call_returns_the_chat_result_plus_page_links(
    dr_workspace,
):
    async with mcp_client(dr_workspace) as client:
        result = await result_of(
            client, "tools/call", {"name": "get_entity", "arguments": {"id": OPERATION_ID}}
        )

        assert result["isError"] is False
        text = result["content"][0]["text"]
        payload, links = text.split("\n\nPages in Context Studio:\n")
        assert json.loads(payload)["id"] == OPERATION_ID
        assert f"Operation (class): {UI}/app/schema/classes/{OPERATION_ID}" in links
        assert f"{UI}/app/schema/taxonomies/{TAXONOMY_ID}" in links


async def test_list_taxonomies_then_vision_through_get_entity(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        listed = await result_of(client, "tools/call", {"name": "list_taxonomies", "arguments": {}})
        taxonomies = json.loads(listed["content"][0]["text"].split("\n\nPages")[0])["taxonomies"]
        assert [t["id"] for t in taxonomies] == [TAXONOMY_ID]

        details = await result_of(
            client, "tools/call", {"name": "get_entity", "arguments": {"id": TAXONOMY_ID}}
        )
        assert (
            json.loads(details["content"][0]["text"].split("\n\nPages")[0])["vision"] == DR_VISION
        )


async def test_tool_errors_are_reported_as_error_results(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        result = await result_of(
            client, "tools/call", {"name": "get_entity", "arguments": {"id": "no-such-id"}}
        )

        assert result["isError"] is True
        assert "no-such-id" in result["content"][0]["text"]
        assert "Pages in Context Studio" not in result["content"][0]["text"]


async def test_unknown_tool_is_an_error_result(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        result = await result_of(
            client, "tools/call", {"name": "delete_everything", "arguments": {}}
        )

        assert result["isError"] is True


async def test_taxonomy_vision_is_a_markdown_resource(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        listed = await result_of(client, "resources/list")
        uri = f"contextstudio://taxonomies/{TAXONOMY_ID}/vision"
        assert [r["uri"] for r in listed["resources"]] == [uri]
        assert listed["resources"][0]["mimeType"] == "text/markdown"

        read = await result_of(client, "resources/read", {"uri": uri})

        assert read["contents"][0]["text"] == DR_VISION
        assert read["contents"][0]["mimeType"] == "text/markdown"


async def test_unknown_resource_is_an_error(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        response = await rpc(
            client, "resources/read", {"uri": "contextstudio://taxonomies/missing/vision"}
        )

        assert "error" in response.json()


async def test_foreign_host_header_is_refused(dr_workspace):
    """DNS rebinding: a page on another host that resolves to 127.0.0.1 is refused."""
    async with mcp_client(dr_workspace) as client:
        response = await rpc(client, "tools/list", headers={"host": "attacker.example:8000"})

        assert response.status_code == 421


async def test_foreign_origin_is_refused(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        response = await rpc(client, "tools/list", headers={"origin": "https://attacker.example"})

        assert response.status_code == 403


async def test_endpoint_refuses_requests_before_the_server_runs():
    app = Starlette(routes=[Route("/mcp", McpEndpoint())])
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        response = await rpc(c, "tools/list")

    assert response.status_code == 503


async def test_request_without_a_token_is_refused(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        response = await rpc(client, "tools/list", headers={"authorization": ""})

        assert response.status_code == 401
        assert response.headers["www-authenticate"].startswith("Bearer")


async def test_request_with_a_wrong_token_is_refused(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        response = await rpc(client, "tools/list", headers={"authorization": "Bearer nope"})

        assert response.status_code == 401


async def test_request_with_a_non_bearer_scheme_is_refused(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        response = await rpc(client, "tools/list", headers={"authorization": f"Basic {TOKEN}"})

        assert response.status_code == 401


async def test_resource_reads_need_the_token_too(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        response = await rpc(
            client,
            "resources/read",
            {"uri": f"contextstudio://taxonomies/{TAXONOMY_ID}/vision"},
            headers={"authorization": ""},
        )

        assert response.status_code == 401


async def test_request_with_the_token_is_served(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        response = await rpc(client, "tools/list", headers={"authorization": f"bearer {TOKEN}"})

        assert response.status_code == 200
        assert response.json()["result"]["tools"]

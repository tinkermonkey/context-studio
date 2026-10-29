"""
Integration tests for the MCP server (#1337, #1357): JSON-RPC over streamable
HTTP to the /mcp endpoint, serving the chat's real read-only tools and proposal
tools, and the taxonomy vision and bundle (#1363) resources, over a DR-shaped
workspace in SQLite.
"""

import json
from contextlib import AsyncExitStack, asynccontextmanager
from types import SimpleNamespace

import httpx
from starlette.applications import Starlette
from starlette.routing import Route

from adapters.chat.proposal_tools import build_proposal_tools
from adapters.chat.tools import build_chat_tools
from adapters.mcp.links import EntityLinks
from adapters.mcp.server import (
    PROPOSE_INSTRUCTIONS,
    READ_ONLY_INSTRUCTIONS,
    McpEndpoint,
    build_mcp_server,
    build_session_manager,
    loopback_security,
    start_mcp_server,
)
from config import ConfigurationManager
from domain.interchange.bundle import BundleExporter
from domain.versioning.approval_policy import ApprovalPolicy, AutoApplyRule
from domain.versioning.proposals import ChangeScope, ProposalSource
from tests.integration.chat.conftest import (
    ADMIN_HEALTH_ID,
    API_SCHEME_ID,
    DR_VISION,
    HEALTH_MONITORING_ID,
    OPERATION_ID,
    SERVICE_CLASS_ID,
    TAXONOMY_ID,
)

TOKEN = "test-mcp-token"
HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
    "authorization": f"Bearer {TOKEN}",
}
UI = "http://localhost:3100"
READ_TOOLS = [
    "list_taxonomies",
    "search_entities",
    "get_entity",
    "list_children",
    "list_relationships",
    "list_relationship_types",
    "get_neighbors",
    "find_path",
]
WRITE_TOOLS = ["propose_changes", "get_proposal", "list_proposals"]
INITIALIZE = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "test", "version": "0"},
}


@asynccontextmanager
async def mcp_client(workspace, write_tools=()):
    """
    An HTTP client for /mcp with the session manager running.

    A context manager rather than a fixture: the manager's task group must be
    entered and exited in the same task, and async fixtures tear down in another.
    """
    tools = build_chat_tools(workspace.ontology, workspace.graph)
    server = build_mcp_server(
        tools,
        workspace.ontology,
        EntityLinks(UI),
        BundleExporter(workspace.repository),
        write_tools,
    )
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
        by_uri = {r["uri"]: r for r in listed["resources"]}
        assert by_uri[uri]["mimeType"] == "text/markdown"

        read = await result_of(client, "resources/read", {"uri": uri})

        assert read["contents"][0]["text"] == DR_VISION
        assert read["contents"][0]["mimeType"] == "text/markdown"


async def test_taxonomy_bundle_is_a_json_resource(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        listed = await result_of(client, "resources/list")
        uri = f"contextstudio://taxonomies/{TAXONOMY_ID}/bundle"
        assert [r["uri"] for r in listed["resources"]] == [
            f"contextstudio://taxonomies/{TAXONOMY_ID}/vision",
            uri,
        ]
        assert listed["resources"][1]["mimeType"] == "application/json"
        assert listed["resources"][1]["name"] == "Documentation Robotics bundle"

        read = await result_of(client, "resources/read", {"uri": uri})

        assert read["contents"][0]["mimeType"] == "application/json"
        bundle = json.loads(read["contents"][0]["text"])
        assert bundle == BundleExporter(dr_workspace.repository).export(TAXONOMY_ID)
        assert bundle["taxonomy"]["identifier"] == "dr_spec"
        assert bundle["relationships"] == [
            {
                "source": ADMIN_HEALTH_ID,
                "property": "operation_realizes_service",
                "target": HEALTH_MONITORING_ID,
            }
        ]


async def test_taxonomy_without_a_vision_still_lists_its_bundle(dr_workspace):
    dr_workspace.ontology.update_taxonomy(TAXONOMY_ID, vision="")
    async with mcp_client(dr_workspace) as client:
        listed = await result_of(client, "resources/list")

        assert [r["uri"] for r in listed["resources"]] == [
            f"contextstudio://taxonomies/{TAXONOMY_ID}/bundle"
        ]


async def test_bundle_that_cannot_be_exported_is_an_error_with_the_reason(dr_workspace):
    dr_workspace.ontology.create_class(concept_scheme_id=API_SCHEME_ID, title="Unkeyed")
    async with mcp_client(dr_workspace) as client:
        response = await rpc(
            client,
            "resources/read",
            {"uri": f"contextstudio://taxonomies/{TAXONOMY_ID}/bundle"},
        )

        error = response.json()["error"]
        assert "no stored identifier" in error["message"]
        assert "Class 'Unkeyed'" in error["message"]


async def test_bundle_of_an_unknown_taxonomy_is_an_error(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        response = await rpc(
            client, "resources/read", {"uri": "contextstudio://taxonomies/missing/bundle"}
        )

        assert "missing" in response.json()["error"]["message"]


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
        for kind in ("vision", "bundle"):
            response = await rpc(
                client,
                "resources/read",
                {"uri": f"contextstudio://taxonomies/{TAXONOMY_ID}/{kind}"},
                headers={"authorization": ""},
            )

            assert response.status_code == 401


async def test_request_with_the_token_is_served(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        response = await rpc(client, "tools/list", headers={"authorization": f"bearer {TOKEN}"})

        assert response.status_code == 200
        assert response.json()["result"]["tools"]


async def test_startup_generates_the_token_and_wires_endpoint_and_state(
    dr_workspace, proposals, tmp_path
):
    """The lifespan helper: ensure_mcp_auth_token, then the endpoint and app.state."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"server": {"host": "127.0.0.1", "port": 8123}}))
    config_manager = ConfigurationManager(config_file=str(config_file))
    tools = build_chat_tools(dr_workspace.ontology, dr_workspace.graph)
    write_tools = build_proposal_tools(proposals.service, ProposalSource.MCP)
    endpoint = McpEndpoint()
    state = SimpleNamespace()

    async with AsyncExitStack() as stack:
        connection = await start_mcp_server(
            stack,
            endpoint,
            state,
            config_manager,
            tools,
            dr_workspace.ontology,
            BundleExporter(dr_workspace.repository),
            write_tools=write_tools,
        )

        token = json.loads(config_file.read_text())["mcp"]["auth_token"]
        assert token and endpoint.auth_token == token
        assert state.mcp_connection is connection
        assert connection.url == "http://127.0.0.1:8123/mcp"
        assert connection.auth_token == token
        assert connection.ui_origins == frozenset({"http://localhost:3100"})

        app = Starlette(routes=[Route("/mcp", endpoint)])
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8123") as c:
            body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
            refused = await c.post("/mcp", json=body, headers={**HEADERS, "authorization": ""})
            served = await c.post(
                "/mcp", json=body, headers={**HEADERS, "authorization": f"Bearer {token}"}
            )
        assert refused.status_code == 401
        assert served.status_code == 200
        # The token is enforced, so the proposal tools are served
        names = [t["name"] for t in served.json()["result"]["tools"]]
        assert names == READ_TOOLS + WRITE_TOOLS


# ============================================================================
# Proposal tools (#1357)
# ============================================================================


def tool_payload(result):
    """The JSON payload of a tool result and its page-links block ('' if none)."""
    text = result["content"][0]["text"]
    payload, _, links = text.partition("\n\nPages in Context Studio:\n")
    return json.loads(payload), links


def call_params(name, arguments):
    return {"name": name, "arguments": arguments}


def update_operation(seq, target_id, **fields):
    return {"seq": seq, "op": "update", "kind": "class", "target_id": target_id, "fields": fields}


async def test_without_write_tools_the_server_is_read_only(dr_workspace):
    async with mcp_client(dr_workspace) as client:
        tools = await result_of(client, "tools/list")
        init = await result_of(client, "initialize", INITIALIZE)

    assert [t["name"] for t in tools["tools"]] == READ_TOOLS
    assert init["instructions"].endswith(READ_ONLY_INSTRUCTIONS)
    assert "propose_changes" not in init["instructions"]


async def test_with_write_tools_the_full_tool_set_and_propose_instructions(dr_workspace, proposals):
    write_tools = build_proposal_tools(proposals.service, ProposalSource.MCP)
    async with mcp_client(dr_workspace, write_tools) as client:
        tools = await result_of(client, "tools/list")
        init = await result_of(client, "initialize", INITIALIZE)

    # Exactly these: no accept, reject, apply, revert or policy tool
    assert [t["name"] for t in tools["tools"]] == READ_TOOLS + WRITE_TOOLS
    by_name = {t["name"]: t for t in tools["tools"]}
    for tool in write_tools:
        assert by_name[tool.spec.name]["inputSchema"] == dict(tool.spec.input_schema)
    instructions = init["instructions"]
    assert instructions.endswith(PROPOSE_INSTRUCTIONS)
    assert "read its vision" in instructions
    assert "read-only" not in instructions


async def test_startup_without_a_token_serves_no_write_tools(
    dr_workspace, proposals, tmp_path, monkeypatch
):
    """The gate: write tools are only served while there is a token to enforce."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"server": {"host": "127.0.0.1", "port": 8123}}))
    config_manager = ConfigurationManager(config_file=str(config_file))
    monkeypatch.setattr(config_manager, "ensure_mcp_auth_token", lambda: "")
    built = {}

    def recording_build(tools, ontology, links, bundles, write_tools=()):
        built["write_tools"] = list(write_tools)
        return build_mcp_server(tools, ontology, links, bundles, write_tools)

    monkeypatch.setattr("adapters.mcp.server.build_mcp_server", recording_build)
    endpoint = McpEndpoint()

    async with AsyncExitStack() as stack:
        await start_mcp_server(
            stack,
            endpoint,
            SimpleNamespace(),
            config_manager,
            build_chat_tools(dr_workspace.ontology, dr_workspace.graph),
            dr_workspace.ontology,
            BundleExporter(dr_workspace.repository),
            write_tools=build_proposal_tools(proposals.service, ProposalSource.MCP),
        )
        app = Starlette(routes=[Route("/mcp", endpoint)])
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8123") as c:
            response = await rpc(c, "tools/call", call_params("propose_changes", {}))

    assert built["write_tools"] == []
    assert response.status_code == 503
    assert proposals.service.count_proposals() == 0


async def test_propose_through_mcp_stores_a_pending_proposal_with_a_review_link(
    dr_workspace, proposals
):
    write_tools = build_proposal_tools(proposals.service, ProposalSource.MCP)
    arguments = {
        "taxonomy_id": TAXONOMY_ID,
        "title": "Define Operation",
        "rationale": "The vision asks for curated definitions",
        "operations": [
            {
                **update_operation(1, OPERATION_ID, description="One endpoint and method"),
                "probability": 0.9,
            },
            {
                "seq": 2,
                "op": "create",
                "kind": "individual",
                "fields": {"class_ids": [SERVICE_CLASS_ID], "title": "Billing"},
            },
        ],
    }
    async with mcp_client(dr_workspace, write_tools) as client:
        result = await result_of(client, "tools/call", call_params("propose_changes", arguments))

    assert result["isError"] is False
    payload, links = tool_payload(result)
    proposal_id = payload["id"]
    assert payload["stored"] is True
    assert payload["status"] == "open"
    assert payload["operations"] == [
        {"seq": 1, "status": "pending", "scope": "editorial"},
        {"seq": 2, "status": "pending", "scope": "additive"},
    ]
    assert links == f"- Define Operation (proposal): {UI}/app/proposals/{proposal_id}"

    stored = proposals.service.get(proposal_id)
    assert stored.source is ProposalSource.MCP
    assert stored.rationale == "The vision asks for curated definitions"
    # Nothing changed: a person reviews it
    description = dr_workspace.ontology.get_class(OPERATION_ID).description
    assert description == "An API operation (endpoint + method)"


async def test_policy_applies_editorial_changes_at_once(dr_workspace, proposals):
    proposals.policies.save(
        ApprovalPolicy(TAXONOMY_ID, auto_apply=(AutoApplyRule(scope=ChangeScope.EDITORIAL),))
    )
    write_tools = build_proposal_tools(proposals.service, ProposalSource.MCP)
    arguments = {
        "taxonomy_id": TAXONOMY_ID,
        "title": "Reword Operation",
        "operations": [update_operation(1, OPERATION_ID, description="One endpoint and method")],
    }
    async with mcp_client(dr_workspace, write_tools) as client:
        result = await result_of(client, "tools/call", call_params("propose_changes", arguments))

    payload, _ = tool_payload(result)
    assert payload["status"] == "done"
    assert payload["operations"] == [
        {"seq": 1, "status": "applied", "scope": "editorial", "result_entity_id": OPERATION_ID}
    ]
    assert dr_workspace.ontology.get_class(OPERATION_ID).description == "One endpoint and method"


async def test_invalid_proposal_through_mcp_lists_what_to_fix(dr_workspace, proposals):
    write_tools = build_proposal_tools(proposals.service, ProposalSource.MCP)
    arguments = {
        "taxonomy_id": TAXONOMY_ID,
        "title": "Bad",
        "operations": [
            update_operation(1, OPERATION_ID, description="Fine"),
            update_operation(2, "no-such-class", title="X"),
        ],
    }
    async with mcp_client(dr_workspace, write_tools) as client:
        result = await result_of(client, "tools/call", call_params("propose_changes", arguments))

    assert result["isError"] is False
    payload, links = tool_payload(result)
    assert payload["stored"] is False and payload["id"] is None
    assert [(o["seq"], o["status"], o["code"]) for o in payload["operations"]] == [
        (2, "invalid", "target_not_found")
    ]
    assert payload["valid_seqs"] == [1]
    assert links == ""
    assert proposals.service.count_proposals() == 0


def evidence_arguments(evidence):
    return {
        "taxonomy_id": TAXONOMY_ID,
        "title": "Bad evidence",
        "operations": [
            {**update_operation(1, OPERATION_ID, description="A"), "evidence": evidence},
            {
                **update_operation(2, SERVICE_CLASS_ID, description="B"),
                "evidence": [{"quote": "fine", "url": "https://example.com"}],
            },
        ],
    }


def assert_evidence_refused(payload, proposals):
    assert payload["stored"] is False
    (invalid,) = payload["operations"]
    assert (invalid["seq"], invalid["code"]) == (1, "invalid")
    assert "evidence" in invalid["message"]
    assert payload["valid_seqs"] == [2]
    assert proposals.service.count_proposals() == 0


async def test_evidence_that_is_not_objects_of_text_is_invalid(dr_workspace, proposals):
    """
    Stored evidence must stay readable by GET /api/proposals (objects of text).
    The MCP SDK checks the input schema (items are objects), so through MCP a
    non-text value is what reaches the service; the chat has no schema check.
    """
    write_tools = build_proposal_tools(proposals.service, ProposalSource.MCP)
    arguments = evidence_arguments([{"quote": "q", "page": 4}])
    async with mcp_client(dr_workspace, write_tools) as client:
        result = await result_of(client, "tools/call", call_params("propose_changes", arguments))
    assert_evidence_refused(tool_payload(result)[0], proposals)

    chat_tool = build_proposal_tools(proposals.service, ProposalSource.CHAT)[0]
    outcome = await chat_tool.execute(evidence_arguments(["text", 3]))
    assert outcome.is_error is False
    assert_evidence_refused(json.loads(outcome.content), proposals)


async def test_a_huge_seq_is_an_invalid_operation_not_a_server_error(dr_workspace, proposals):
    chat_tool = build_proposal_tools(proposals.service, ProposalSource.CHAT)[0]

    outcome = await chat_tool.execute(
        {
            "taxonomy_id": TAXONOMY_ID,
            "title": "Huge seq",
            "operations": [update_operation(10**30, OPERATION_ID, description="A")],
        }
    )

    assert outcome.is_error is False
    payload = json.loads(outcome.content)
    assert payload["stored"] is False
    assert [(o["seq"], o["code"]) for o in payload["operations"]] == [(10**30, "invalid")]
    assert proposals.service.count_proposals() == 0


async def test_get_and_list_proposals_through_mcp(dr_workspace, proposals):
    write_tools = build_proposal_tools(proposals.service, ProposalSource.MCP)
    arguments = {
        "taxonomy_id": TAXONOMY_ID,
        "title": "Define Operation",
        "operations": [update_operation(1, OPERATION_ID, description="One endpoint and method")],
    }
    async with mcp_client(dr_workspace, write_tools) as client:
        proposed = await result_of(client, "tools/call", call_params("propose_changes", arguments))
        proposal_id = tool_payload(proposed)[0]["id"]
        # The class changes after the proposal: its operation is now stale
        dr_workspace.ontology.update_class(OPERATION_ID, description="Changed meanwhile")

        got = await result_of(
            client, "tools/call", call_params("get_proposal", {"id": proposal_id})
        )
        listed = await result_of(
            client,
            "tools/call",
            call_params("list_proposals", {"taxonomy_id": TAXONOMY_ID, "status": "open"}),
        )
        missing = await result_of(client, "tools/call", call_params("get_proposal", {"id": "x"}))

    detail, detail_links = tool_payload(got)
    assert detail["id"] == proposal_id
    assert detail["source"] == "mcp"
    (operation,) = detail["operations"]
    assert (operation["status"], operation["stale"]) == ("pending", True)
    assert operation["fields"] == {"description": "One endpoint and method"}
    assert f"{UI}/app/proposals/{proposal_id}" in detail_links

    summary, list_links = tool_payload(listed)
    assert [i["id"] for i in summary["items"]] == [proposal_id]
    assert summary["total"] == 1
    assert f"{UI}/app/proposals/{proposal_id}" in list_links

    assert missing["isError"] is True

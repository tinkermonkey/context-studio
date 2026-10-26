"""
MCP server for Context Studio.

Serves the same read-only tools as the in-app chat, so an MCP client such as
Claude Code can do everything the chat can. Each taxonomy's vision statement is
also offered as a markdown resource. The server runs over streamable HTTP,
mounted at /mcp on the running app, and only on a loopback host.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from typing import Any, Iterable, Optional, Sequence

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyUrl
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from adapters.mcp.links import EntityLinks
from domain.chat.ports import ChatTool
from domain.ontology.entities import Taxonomy
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.services import OntologyService
from utils.async_executor import run_sync_in_executor

_logger = logging.getLogger(__name__)

SERVER_NAME = "context-studio"
VISION_URI = "contextstudio://taxonomies/{id}/vision"
_VISION_URI_PATTERN = re.compile(r"^contextstudio://taxonomies/(?P<id>[^/]+)/vision$")

INSTRUCTIONS = (
    "Context Studio holds ontologies: taxonomies, their concept schemes, classes,"
    " relationship types (properties) and individuals, each with a curated"
    " definition. Start with list_taxonomies to see what exists, use"
    " search_entities to find anything by name or meaning, and get_entity for"
    " details. A taxonomy's description is its one-paragraph summary; its full"
    " vision statement (what it is for, what its classes and relationships model,"
    " how changes are judged) is in get_entity and in the taxonomy's vision"
    " resource. Read the vision before proposing changes to a taxonomy. All tools"
    " are read-only. Results include links to the entity pages in the app."
)


def build_mcp_server(
    tools: Sequence[ChatTool],
    ontology: OntologyService,
    links: EntityLinks,
) -> Server:
    """
    Build the MCP server over the given tools.

    Args:
        tools: The chat's tools; each is listed with its spec verbatim
        ontology: Ontology service, for the taxonomy vision resources
        links: Builds entity page links appended to tool results
    """
    server: Server = Server(SERVER_NAME, instructions=INSTRUCTIONS)
    by_name = {tool.spec.name: tool for tool in tools}

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=tool.spec.name,
                description=tool.spec.description,
                inputSchema=dict(tool.spec.input_schema),
            )
            for tool in tools
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        tool = by_name.get(name)
        if tool is None:
            return _error_result(f"Unknown tool: {name}")
        outcome = await tool.execute(arguments or {})
        text = outcome.content
        if not outcome.is_error:
            text += links.block(outcome.entities)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)],
            isError=outcome.is_error,
        )

    @server.list_resources()
    async def list_resources() -> list[types.Resource]:
        taxonomies = await run_sync_in_executor(
            lambda: ontology.list_taxonomies(limit=None, sort_by="title")
        )
        return [_vision_resource(t) for t in taxonomies if t.vision]

    @server.read_resource()
    async def read_resource(uri: AnyUrl) -> Iterable[ReadResourceContents]:
        taxonomy_id = _taxonomy_id_from_uri(str(uri))
        try:
            taxonomy = await run_sync_in_executor(ontology.get_taxonomy, taxonomy_id)
        except EntityNotFoundError:
            raise ValueError(f"No taxonomy with id {taxonomy_id!r}") from None
        if not taxonomy.vision:
            raise ValueError(f"Taxonomy {taxonomy.title!r} has no vision statement")
        return [ReadResourceContents(content=taxonomy.vision, mime_type="text/markdown")]

    return server


def _error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)], isError=True
    )


def _vision_resource(taxonomy: Taxonomy) -> types.Resource:
    return types.Resource(
        uri=AnyUrl(VISION_URI.format(id=taxonomy.id)),
        name=f"{taxonomy.title} vision",
        description=taxonomy.description,
        mimeType="text/markdown",
    )


def _taxonomy_id_from_uri(uri: str) -> str:
    match = _VISION_URI_PATTERN.match(uri)
    if match is None:
        raise ValueError(f"Unknown resource: {uri}")
    return match.group("id")


def is_loopback_host(host: str) -> bool:
    """Whether the server's bind address only accepts local connections."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def loopback_security(ui_origins: Sequence[str] = ()) -> TransportSecuritySettings:
    """
    DNS-rebinding protection: accept only loopback Host headers, and Origin
    headers from loopback pages (plus any listed UI origins).
    """
    loopback = ("127.0.0.1", "localhost", "[::1]")
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[h for host in loopback for h in (host, f"{host}:*")],
        allowed_origins=[
            *(o for host in loopback for o in (f"http://{host}", f"http://{host}:*")),
            *ui_origins,
        ],
    )


def build_session_manager(server: Server, security: TransportSecuritySettings):
    """A stateless, JSON-response streamable HTTP session manager for the server."""
    return StreamableHTTPSessionManager(
        app=server, stateless=True, json_response=True, security_settings=security
    )


class McpEndpoint:
    """
    ASGI app for /mcp.

    It is mounted when the app module loads, but the session manager only
    exists inside the lifespan, so requests are refused until one is attached.
    """

    def __init__(self) -> None:
        self.session_manager: Optional[StreamableHTTPSessionManager] = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.session_manager is None:
            response = JSONResponse(
                {"detail": "The MCP server is not running on this host."}, status_code=503
            )
            await response(scope, receive, send)
            return
        await self.session_manager.handle_request(scope, receive, send)

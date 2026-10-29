"""
MCP server for Context Studio.

Serves the same read-only tools as the in-app chat, so an MCP client such as
Claude Code can do everything the chat can. Each taxonomy's vision statement is
also offered as a markdown resource, and each taxonomy as a JSON bundle
resource (too large for a tool result). The server runs over streamable HTTP,
mounted at /mcp on the running app, and only on a loopback host. Every request
must carry the configured bearer token.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import logging
import re
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyUrl
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from adapters.mcp.links import EntityLinks
from config import ConfigurationManager
from domain.chat.ports import ChatTool
from domain.interchange.bundle import BundleError, BundleExporter
from domain.ontology.entities import Taxonomy
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.services import OntologyService
from utils.async_executor import run_sync_in_executor

_logger = logging.getLogger(__name__)

SERVER_NAME = "context-studio"
VISION_URI = "contextstudio://taxonomies/{id}/vision"
BUNDLE_URI = "contextstudio://taxonomies/{id}/bundle"
_TAXONOMY_URI_PATTERN = re.compile(
    r"^contextstudio://taxonomies/(?P<id>[^/]+)/(?P<kind>vision|bundle)$"
)

INSTRUCTIONS = (
    "Context Studio holds ontologies: taxonomies, their concept schemes, classes,"
    " relationship types (properties) and individuals, each with a curated"
    " definition. Start with list_taxonomies to see what exists, use"
    " search_entities to find anything by name or meaning, and get_entity for"
    " details. A taxonomy's description is its one-paragraph summary; its full"
    " vision statement (what it is for, what its classes and relationships model,"
    " how changes are judged) is in get_entity and in the taxonomy's vision"
    " resource. Read the vision before proposing changes to a taxonomy. A"
    " taxonomy's full contents are its bundle resource (JSON). All tools"
    " are read-only. Results include links to the entity pages in the app."
)


def build_mcp_server(
    tools: Sequence[ChatTool],
    ontology: OntologyService,
    links: EntityLinks,
    bundles: BundleExporter,
) -> Server:
    """
    Build the MCP server over the given tools.

    Args:
        tools: The chat's tools; each is listed with its spec verbatim
        ontology: Ontology service, for the taxonomy vision resources
        links: Builds entity page links appended to tool results
        bundles: Exports the taxonomy bundle resources
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
        return [_vision_resource(t) for t in taxonomies if t.vision] + [
            _bundle_resource(t) for t in taxonomies
        ]

    @server.read_resource()
    async def read_resource(uri: AnyUrl) -> Iterable[ReadResourceContents]:
        taxonomy_id, kind = _parse_taxonomy_uri(str(uri))
        try:
            taxonomy = await run_sync_in_executor(ontology.get_taxonomy, taxonomy_id)
        except EntityNotFoundError:
            raise ValueError(f"No taxonomy with id {taxonomy_id!r}") from None
        if kind == "bundle":
            try:
                bundle = await run_sync_in_executor(bundles.export, taxonomy_id)
            except BundleError as exc:
                raise ValueError(str(exc)) from None
            text = json.dumps(bundle, indent=2, ensure_ascii=False) + "\n"
            return [ReadResourceContents(content=text, mime_type="application/json")]
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


def _bundle_resource(taxonomy: Taxonomy) -> types.Resource:
    return types.Resource(
        uri=AnyUrl(BUNDLE_URI.format(id=taxonomy.id)),
        name=f"{taxonomy.title} bundle",
        description=f"The {taxonomy.title} taxonomy as a Context Studio bundle",
        mimeType="application/json",
    )


def _parse_taxonomy_uri(uri: str) -> tuple[str, str]:
    """Split a taxonomy resource URI into the taxonomy id and the resource kind."""
    match = _TAXONOMY_URI_PATTERN.match(uri)
    if match is None:
        raise ValueError(f"Unknown resource: {uri}")
    return match.group("id"), match.group("kind")


def is_loopback_host(host: str) -> bool:
    """Whether the server's bind address only accepts local connections."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class McpConnection:
    """
    What an MCP client needs to connect: the endpoint URL and the bearer token.

    ui_origins are the browser origins allowed to read it (the app's own UI);
    they are not part of the connection details handed out.
    """

    url: str
    auth_token: str
    ui_origins: frozenset[str] = frozenset()


def mcp_url(host: str, port: int) -> str:
    """The /mcp URL for a server bound to host and port."""
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    return f"http://{host}:{port}/mcp"


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

    It is mounted when the app module loads, but the session manager and the
    auth token only exist inside the lifespan, so requests are refused until
    they are attached. Every request, reads included, needs
    ``Authorization: Bearer <auth_token>``.
    """

    def __init__(self) -> None:
        self.session_manager: Optional[StreamableHTTPSessionManager] = None
        self.auth_token: Optional[str] = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.session_manager is None or not self.auth_token:
            response = JSONResponse(
                {"detail": "The MCP server is not running on this host."}, status_code=503
            )
            await response(scope, receive, send)
            return
        if not self._is_authorized(Headers(scope=scope)):
            response = JSONResponse(
                {"detail": "Missing or invalid MCP bearer token."},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="context-studio"'},
            )
            await response(scope, receive, send)
            return
        await self.session_manager.handle_request(scope, receive, send)

    def _is_authorized(self, headers: Headers) -> bool:
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return False
        return hmac.compare_digest(token.strip().encode(), (self.auth_token or "").encode())


async def start_mcp_server(
    stack: AsyncExitStack,
    endpoint: McpEndpoint,
    state: Any,
    config_manager: ConfigurationManager,
    tools: Sequence[ChatTool],
    ontology: OntologyService,
    bundles: BundleExporter,
) -> McpConnection:
    """
    Start the MCP server for the app lifespan and attach it to /mcp.

    Runs the session manager inside `stack`, makes sure an auth token exists
    (generating and saving one if config.json has none), arms the endpoint
    with it, and stores the connection details on `state` (app.state) for
    the settings endpoint.
    """
    settings = config_manager.get_settings()
    server = build_mcp_server(tools, ontology, EntityLinks(settings.server.ui_base_url), bundles)
    session_manager = build_session_manager(server, loopback_security())
    await stack.enter_async_context(session_manager.run())
    auth_token = config_manager.ensure_mcp_auth_token()
    endpoint.auth_token = auth_token
    endpoint.session_manager = session_manager
    connection = McpConnection(
        url=mcp_url(settings.server.host, settings.server.port),
        auth_token=auth_token,
        ui_origins=settings.server.ui_origins(),
    )
    state.mcp_connection = connection
    return connection

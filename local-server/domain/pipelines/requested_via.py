"""
Who asked for a pipeline run, and whether it may propose changes to a taxonomy.

A mirrored taxonomy follows a client's source of truth (DR's spec, say), and its
client drives the proposals. The client may run a refinement on it, over MCP;
Context Studio doesn't run one on its own, from the chat or the UI.
"""

from collections.abc import Mapping
from enum import Enum
from typing import Any

from domain.ontology.entities import Taxonomy
from domain.pipelines.exceptions import PipelineInputError

# The run input key that records who asked for the run. The entry point that
# starts the run sets it, after any caller-supplied input, so a caller can't
# claim to be someone else.
REQUESTED_VIA = "requested_via"


class RequestedVia(str, Enum):
    """The entry point a pipeline run was started from."""

    MCP = "mcp"
    CHAT = "chat"
    API = "api"


def ensure_may_propose_to(taxonomy: Taxonomy, input_data: Mapping[str, Any]) -> None:
    """
    Refuse a run that would propose changes to a mirrored taxonomy for someone
    other than its client.

    Args:
        taxonomy: The taxonomy the run proposes changes to
        input_data: The run's input, with `requested_via` set by its entry point

    Raises:
        PipelineInputError: If the taxonomy is mirrored and the run wasn't
            requested over MCP
    """
    if not taxonomy.mirrored:
        return
    requested_via = input_data.get(REQUESTED_VIA)
    if requested_via == RequestedVia.MCP.value:
        return
    asked = f"this run came from {requested_via}" if requested_via else "this run names no caller"
    raise PipelineInputError(
        f"{taxonomy.title} mirrors an external source: its client proposes changes, so only"
        f" the client may start a refinement on it, over MCP ({asked})"
    )

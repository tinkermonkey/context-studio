"""
Integration test (#1357): the chat assistant proposes; a person reviews.

The chat is wired as in app.py (the read-only tools, then the proposal tools
with the chat source) over real SQLite. A scripted model proposes a change and
answers linking the proposal, which must resolve to the ref the tool returned.
"""

import json
import re

from adapters.chat.context import OntologyWorkspaceContext
from adapters.chat.proposal_tools import build_proposal_tools
from adapters.chat.tools import build_chat_tools
from domain.chat.services import SYSTEM_PROMPT, ChatService
from domain.chat.value_objects import (
    ModelTurnEnded,
    StopReason,
    TextBlock,
    TextDelta,
    ToolFinished,
    ToolResultBlock,
    ToolUseBlock,
)
from domain.versioning.proposals import OperationStatus, ProposalSource
from tests.integration.chat.conftest import OPERATION_ID, TAXONOMY_ID

LINK = re.compile(r"\[([^\]]+)\]\(entity:([a-z]+)/([^)\s]+)\)")

CHAT_TOOLS = [
    "list_taxonomies",
    "search_entities",
    "get_entity",
    "list_children",
    "list_relationships",
    "list_relationship_types",
    "get_neighbors",
    "find_path",
    "propose_changes",
    "get_proposal",
    "list_proposals",
]


class ProposingModel:
    """Proposes a definition for Operation, then answers linking the proposal."""

    def __init__(self):
        self.requests = []

    def supports_model(self, model):
        return True

    def list_models(self):
        return ["scripted"]

    async def stream_chat(self, *, system, messages, tools, model, max_tokens=16000):
        self.requests.append({"system": system, "tools": [t.name for t in tools]})
        results = [b for b in messages[-1].blocks if isinstance(b, ToolResultBlock)]
        if not results:
            use = ToolUseBlock(
                id="tu-propose",
                name="propose_changes",
                input={
                    "taxonomy_id": TAXONOMY_ID,
                    "title": "Define Operation",
                    "operations": [
                        {
                            "seq": 1,
                            "op": "update",
                            "kind": "class",
                            "target_id": OPERATION_ID,
                            "fields": {"description": "One endpoint and method of an API"},
                        }
                    ],
                },
            )
            yield ModelTurnEnded(StopReason.TOOL_USE, 40, 10, (use,))
            return
        result = json.loads(results[0].content)
        text = (
            f"I proposed [{result['title']}](entity:{result['kind']}/{result['id']});"
            f" {result['counts']['pending']} change is pending your review."
        )
        yield TextDelta(text)
        yield ModelTurnEnded(StopReason.END_TURN, 50, 20, (TextBlock(text),))


class FixedSettings:
    def model(self):
        return "scripted"

    def max_tool_rounds(self):
        return 4


async def test_chat_offers_read_and_proposal_tools_and_links_the_proposal(dr_workspace, proposals):
    model = ProposingModel()
    service = ChatService(
        model=model,
        tools=[
            *build_chat_tools(dr_workspace.ontology, dr_workspace.graph),
            *build_proposal_tools(proposals.service, ProposalSource.CHAT),
        ],
        repository=dr_workspace.conversations,
        settings=FixedSettings(),
        workspace=OntologyWorkspaceContext(dr_workspace.ontology),
    )
    conversation = await service.create_conversation()

    events = [e async for e in service.send(conversation.id, "Define the Operation class")]

    # Exactly the read tools and the proposal tools: nothing that decides
    assert model.requests[0]["tools"] == CHAT_TOOLS
    assert model.requests[0]["system"] == SYSTEM_PROMPT
    assert "You propose; a person reviews." in SYSTEM_PROMPT

    (finished,) = [e for e in events if isinstance(e, ToolFinished)]
    assert finished.name == "propose_changes" and not finished.is_error
    (ref,) = finished.entities
    assert (ref.kind, ref.title) == ("proposal", "Define Operation")

    answer = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert LINK.findall(answer) == [("Define Operation", "proposal", ref.id)]

    stored = proposals.service.get(ref.id)
    assert stored.source is ProposalSource.CHAT
    assert [o.status for o in stored.operations] == [OperationStatus.PENDING]
    description = dr_workspace.ontology.get_class(OPERATION_ID).description
    assert description == "An API operation (endpoint + method)"

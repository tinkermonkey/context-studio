"""
Integration tests for the chat API: a full streamed, tool-calling conversation
over real SQLite repositories with a DR-shaped workspace.

The chat model is scripted (no LLM), but it behaves like one: it reads the tool
results it is given and cites the entities it found as entity links. The test
asserts every link in the answer resolves to an entity a tool returned.
"""

import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.chat.context import OntologyWorkspaceContext
from adapters.chat.tools import build_chat_tools
from adapters.web.chat_routes import router
from domain.chat.services import ChatService
from domain.chat.value_objects import (
    ChatRole,
    ModelTurnEnded,
    StopReason,
    TextBlock,
    TextDelta,
    ToolResultBlock,
    ToolUseBlock,
)
from tests.integration.chat.conftest import (
    ADMIN_HEALTH_ID,
    LIST_CLASSES_ID,
    OPERATION_ID,
)

LINK = re.compile(r"\[([^\]]+)\]\(entity:([a-z]+)/([^)\s]+)\)")


class DrScriptedModel:
    """
    Answers "which operations are there?" the way an LLM would: search for the
    Operation class, list its children, then answer citing what it found.
    """

    def __init__(self):
        self.requests = []

    def supports_model(self, model):
        return model == "claude-sonnet-5-5"

    async def stream_chat(self, *, system, messages, tools, model, max_tokens=16000):
        self.requests.append(list(messages))
        last = messages[-1]
        results = [b for b in last.blocks if isinstance(b, ToolResultBlock)]
        if not results:
            yield _tool_call(
                "tu-search", "search_entities", {"query": "Operation", "kinds": ["class"]}
            )
            return
        content = json.loads(results[0].content)
        if "query" in content:
            class_id = content["results"][0]["id"]
            yield _tool_call("tu-children", "list_children", {"id": class_id})
            return
        parent = content["parent"]
        items = ", ".join(f"[{i['title']}](entity:{i['kind']}/{i['id']})" for i in content["items"])
        text = (
            f"The [{parent['title']}](entity:{parent['kind']}/{parent['id']}) class has"
            f" {content['total']} individuals: {items}."
        )
        for start in range(0, len(text), 25):
            yield TextDelta(text[start : start + 25])
        yield ModelTurnEnded(StopReason.END_TURN, 50, 20, (TextBlock(text),))


def _tool_call(tool_id, name, args):
    use = ToolUseBlock(id=tool_id, name=name, input=args)
    return ModelTurnEnded(StopReason.TOOL_USE, 40, 10, (use,))


class FixedSettings:
    def model(self):
        return "claude-sonnet-5-5"

    def max_tool_rounds(self):
        return 8


@pytest.fixture
def client(dr_workspace):
    app = FastAPI()
    app.include_router(router)
    app.state.chat_service = ChatService(
        model=DrScriptedModel(),
        tools=build_chat_tools(dr_workspace.ontology, dr_workspace.graph),
        repository=dr_workspace.conversations,
        settings=FixedSettings(),
        workspace=OntologyWorkspaceContext(dr_workspace.ontology),
    )
    with TestClient(app) as test_client:
        yield test_client


def stream_events(client, conversation_id, text, page_context=None):
    """POST a message and parse the SSE stream into (event, data) pairs."""
    body = {"text": text}
    if page_context:
        body["page_context"] = page_context
    with client.stream(
        "POST", f"/api/chat/conversations/{conversation_id}/messages", json=body
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = "".join(response.iter_text())
    events = []
    for frame in raw.split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in frame.splitlines() if line and not line.startswith(":")
        )
        if "data" in fields:
            data = json.loads(fields["data"])
            assert fields["event"] == data["type"]
            events.append(data)
    return events


def test_streamed_tool_calling_conversation_returns_valid_entity_links(client):
    conversation = client.post("/api/chat/conversations").json()

    events = stream_events(
        client,
        conversation["id"],
        "Which operations does the API layer have?",
        page_context={"route": "/app/schema/schemes"},
    )

    types = [e["type"] for e in events]
    assert types[0] == "message_start" and types[-1] == "message_end"
    assert types[1:5] == ["tool_start", "tool_end", "tool_start", "tool_end"]
    assert set(types[5:-1]) == {"text_delta"}
    assert events[1]["name"] == "search_entities"
    assert events[-1]["stop_reason"] == "end_turn"

    # Every link in the answer resolves to an entity some tool_end returned
    returned = {
        (e["kind"], e["id"]): e["title"]
        for t in events
        if t["type"] == "tool_end"
        for e in t["entities"]
    }
    answer = "".join(e["text"] for e in events if e["type"] == "text_delta")
    links = LINK.findall(answer)
    assert {(kind, entity_id) for _, kind, entity_id in links} == {
        ("class", OPERATION_ID),
        ("individual", ADMIN_HEALTH_ID),
        ("individual", LIST_CLASSES_ID),
    }
    for title, kind, entity_id in links:
        assert returned[(kind, entity_id)] == title

    # The stored conversation keeps the answer and the entity refs for resuming
    detail = client.get(f"/api/chat/conversations/{conversation['id']}").json()
    assert detail["title"] == "Which operations does the API layer have?"
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]
    first = detail["messages"][0]
    assert first["blocks"] == [
        {"type": "text", "text": "Which operations does the API layer have?"}
    ]
    assert first["page_context"] == {
        "route": "/app/schema/schemes",
        "entity_kind": None,
        "entity_id": None,
    }
    stored_refs = {
        (e["kind"], e["id"])
        for m in detail["messages"]
        for b in m["blocks"]
        if b["type"] == "tool_result"
        for e in b["entities"]
    }
    assert {(kind, entity_id) for _, kind, entity_id in links} <= stored_refs
    assert detail["messages"][-1]["blocks"] == [{"type": "text", "text": answer}]
    tool_use = detail["messages"][1]["blocks"][0]
    assert tool_use == {
        "type": "tool_use",
        "id": "tu-search",
        "name": "search_entities",
        "input": {"query": "Operation", "kinds": ["class"]},
    }


def test_page_context_names_the_viewed_entity_for_the_model(client, dr_workspace):
    conversation = client.post("/api/chat/conversations").json()
    model = client.app.state.chat_service._model

    stream_events(
        client,
        conversation["id"],
        "What is this?",
        page_context={
            "route": f"/app/schema/classes/{OPERATION_ID}",
            "entity_kind": "class",
            "entity_id": OPERATION_ID,
        },
    )

    first_request = model.requests[0]
    user = first_request[0]
    assert user.role == ChatRole.USER
    notes = [b.text for b in user.blocks if type(b).__name__ == "ContextBlock"]
    assert notes[0] == (
        "Workspace counts: taxonomies 1, concept schemes 2, classes 2, individuals 3,"
        " relationships 1, relationship types 1. Taxonomies: Documentation Robotics."
    )
    assert f"entity:class/{OPERATION_ID}" in notes[1]
    assert "Operation" in notes[1]


def test_status(client):
    assert client.get("/api/chat/status").json() == {
        "model": "claude-sonnet-5-5",
        "available": True,
        "max_tool_rounds": 8,
    }


def test_conversation_list_resume_and_delete(client):
    first = client.post("/api/chat/conversations")
    assert first.status_code == 201
    second = client.post("/api/chat/conversations").json()
    stream_events(client, first.json()["id"], "Which operations are there?")

    listed = client.get("/api/chat/conversations").json()
    assert [c["id"] for c in listed] == [first.json()["id"], second["id"]]  # latest first

    assert client.delete(f"/api/chat/conversations/{second['id']}").status_code == 204
    assert client.get(f"/api/chat/conversations/{second['id']}").status_code == 404
    assert client.delete(f"/api/chat/conversations/{second['id']}").status_code == 404


def test_message_errors(client):
    response = client.post("/api/chat/conversations/missing/messages", json={"text": "hi"})
    assert response.status_code == 404

    conversation = client.post("/api/chat/conversations").json()
    response = client.post(
        f"/api/chat/conversations/{conversation['id']}/messages", json={"text": ""}
    )
    assert response.status_code == 422
    response = client.post(
        f"/api/chat/conversations/{conversation['id']}/messages",
        json={"text": "hi", "page_context": {"route": "/x", "entity_kind": "table"}},
    )
    assert response.status_code == 422


def test_model_failure_streams_error_event(client):
    class FailingModel(DrScriptedModel):
        async def stream_chat(self, **kwargs):
            raise ValueError("No provider available for model: claude-sonnet-5-5")
            yield  # pragma: no cover

    client.app.state.chat_service._model = FailingModel()
    conversation = client.post("/api/chat/conversations").json()

    events = stream_events(client, conversation["id"], "hi")

    assert [e["type"] for e in events] == ["message_start", "error"]
    assert "No provider available" in events[-1]["message"]

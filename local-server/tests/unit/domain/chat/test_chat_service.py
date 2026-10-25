"""
Unit tests for ChatService (the agent loop), using in-memory fakes for every port.
"""

import copy
import json

import pytest

from domain.chat.exceptions import ChatModelError, ConversationNotFoundError
from domain.chat.services import LIMIT_NOTE, NEW_CONVERSATION_TITLE, SYSTEM_PROMPT, ChatService
from domain.chat.value_objects import (
    ChatFailed,
    ChatRole,
    ContextBlock,
    EntityRef,
    ModelTurnEnded,
    PageContext,
    ReasoningBlock,
    StopReason,
    TextBlock,
    TextDelta,
    ToolCallRequested,
    ToolFinished,
    ToolOutcome,
    ToolResultBlock,
    ToolSpec,
    ToolStarted,
    ToolUseBlock,
    TurnCompleted,
)

OPERATION = EntityRef(id="cls-1", kind="class", title="Operation")


# ============================================================================
# Fakes
# ============================================================================


class ScriptedModel:
    """Chat model that replays scripted turns and records each request."""

    def __init__(self, *turns, supported=("claude-sonnet-5-5",)):
        self._turns = list(turns)
        self._supported = supported
        self.requests: list[dict] = []

    def supports_model(self, model):
        return model in self._supported

    def list_models(self):
        return list(self._supported)

    async def stream_chat(self, *, system, messages, tools, model, max_tokens=16000):
        self.requests.append(
            {
                "system": system,
                "messages": copy.deepcopy(list(messages)),
                "tools": list(tools),
                "model": model,
            }
        )
        turn = self._turns.pop(0)
        for event in turn:
            if isinstance(event, Exception):
                raise event
            yield event


def answer(text, *, stop=StopReason.END_TURN, extra_blocks=()):
    return [
        TextDelta(text),
        ModelTurnEnded(
            stop_reason=stop, tokens_in=10, tokens_out=5, blocks=(*extra_blocks, TextBlock(text))
        ),
    ]


def tool_call(*uses, stop=StopReason.TOOL_USE):
    return [
        *(ToolCallRequested(u) for u in uses),
        ModelTurnEnded(stop_reason=stop, tokens_in=20, tokens_out=8, blocks=tuple(uses)),
    ]


class FakeTool:
    def __init__(self, name="search_entities", outcome=None, error=None):
        self.name = name
        self.calls: list[dict] = []
        self._outcome = outcome or ToolOutcome(
            content=json.dumps([{"id": OPERATION.id, "kind": "class", "title": "Operation"}]),
            summary="Found 1",
            entities=(OPERATION,),
        )
        self._error = error

    @property
    def spec(self):
        return ToolSpec(name=self.name, description="d", input_schema={"type": "object"})

    async def execute(self, args):
        self.calls.append(dict(args))
        if self._error:
            raise self._error
        return self._outcome


class InMemoryRepository:
    def __init__(self):
        self.conversations = {}
        self.messages = {}

    async def save_conversation(self, conversation):
        self.conversations[conversation.id] = copy.copy(conversation)

    async def get_conversation(self, conversation_id):
        c = self.conversations.get(conversation_id)
        return copy.copy(c) if c else None

    async def list_conversations(self, limit):
        ordered = sorted(self.conversations.values(), key=lambda c: c.updated_at, reverse=True)
        return ordered[:limit]

    async def delete_conversation(self, conversation_id):
        self.messages.pop(conversation_id, None)
        return self.conversations.pop(conversation_id, None) is not None

    async def add_message(self, message):
        self.messages.setdefault(message.conversation_id, []).append(message)

    async def list_messages(self, conversation_id):
        return list(self.messages.get(conversation_id, []))


class FakeSettings:
    def __init__(self, model="claude-sonnet-5-5", rounds=8):
        self._model = model
        self._rounds = rounds

    def model(self):
        return self._model

    def max_tool_rounds(self):
        return self._rounds


class FakeWorkspace:
    async def summarize(self):
        return "Workspace contents: 1 taxonomy."

    async def describe_page(self, page_context):
        if page_context.entity_id:
            return f"The user is viewing the {page_context.entity_kind} {page_context.entity_id}."
        return None


def make_service(model, tools=None, rounds=8):
    repository = InMemoryRepository()
    service = ChatService(
        model=model,
        tools=tools if tools is not None else [FakeTool()],
        repository=repository,
        settings=FakeSettings(rounds=rounds),
        workspace=FakeWorkspace(),
    )
    return service, repository


async def run(service, conversation_id, text="Is there an Operation class?", page=None):
    return [e async for e in service.send(conversation_id, text, page)]


def use(tool_id="tu-1", name="search_entities", **args):
    return ToolUseBlock(id=tool_id, name=name, input=args or {"query": "Operation"})


# ============================================================================
# Tests
# ============================================================================


class TestSimpleAnswer:
    async def test_streams_text_and_completes(self):
        model = ScriptedModel(answer("Hello."))
        service, repository = make_service(model)
        conversation = await service.create_conversation()

        events = await run(service, conversation.id)

        assert events == [TextDelta("Hello."), TurnCompleted(StopReason.END_TURN, 10, 5)]
        user, assistant = repository.messages[conversation.id]
        assert user.role == ChatRole.USER and user.seq == 0
        assert user.blocks == (
            ContextBlock("Workspace contents: 1 taxonomy."),
            TextBlock("Is there an Operation class?"),
        )
        assert assistant.role == ChatRole.ASSISTANT and assistant.seq == 1
        assert assistant.blocks == (TextBlock("Hello."),)
        assert (assistant.tokens_in, assistant.tokens_out) == (10, 5)

    async def test_sets_title_from_first_message_only(self):
        model = ScriptedModel(answer("a"), answer("b"))
        service, repository = make_service(model)
        conversation = await service.create_conversation()
        assert conversation.title == NEW_CONVERSATION_TITLE

        await run(service, conversation.id, text="  What   classes are in the API layer?  ")
        await run(service, conversation.id, text="And the business layer?")

        stored = repository.conversations[conversation.id]
        assert stored.title == "What classes are in the API layer?"

    async def test_long_title_is_cut(self):
        service, repository = make_service(ScriptedModel(answer("a")))
        conversation = await service.create_conversation()

        await run(service, conversation.id, text="word " * 40)

        title = repository.conversations[conversation.id].title
        assert len(title) == 60 and title.endswith("…")

    async def test_system_prompt_requires_entity_links(self):
        model = ScriptedModel(answer("a"))
        service, _ = make_service(model)
        conversation = await service.create_conversation()

        await run(service, conversation.id)

        assert model.requests[0]["system"] == SYSTEM_PROMPT
        assert "[Title](entity:<kind>/<id>)" in SYSTEM_PROMPT
        assert "read-only" in SYSTEM_PROMPT
        for kind in ("taxonomy", "scheme", "class", "individual", "property"):
            assert kind in SYSTEM_PROMPT

    async def test_reasoning_blocks_are_stored_for_replay(self):
        thinking = ReasoningBlock(provider="anthropic", data={"type": "thinking", "signature": "s"})
        model = ScriptedModel(answer("a", extra_blocks=(thinking,)), answer("b"))
        service, _ = make_service(model)
        conversation = await service.create_conversation()

        await run(service, conversation.id)
        await run(service, conversation.id, text="more")

        replayed = model.requests[1]["messages"][1]
        assert replayed.blocks[0] == thinking


class TestContext:
    async def test_summary_only_on_first_message_and_page_context_each_time(self):
        model = ScriptedModel(answer("a"), answer("b"))
        service, repository = make_service(model)
        conversation = await service.create_conversation()
        page = PageContext(
            route="/app/schema/classes/cls-1", entity_kind="class", entity_id="cls-1"
        )

        await run(service, conversation.id, page=page)
        await run(service, conversation.id, text="And its individuals?", page=page)

        first, _, second, _ = repository.messages[conversation.id]
        assert first.blocks[0] == ContextBlock("Workspace contents: 1 taxonomy.")
        assert first.blocks[1] == ContextBlock("The user is viewing the class cls-1.")
        assert second.blocks == (
            ContextBlock("The user is viewing the class cls-1."),
            TextBlock("And its individuals?"),
        )
        assert second.page_context == page

    async def test_history_is_append_only_across_turns(self):
        """Each request starts with exactly the previous request's messages."""
        model = ScriptedModel(tool_call(use()), answer("a"), answer("b"))
        service, _ = make_service(model)
        conversation = await service.create_conversation()

        await run(service, conversation.id)
        await run(service, conversation.id, text="next")

        requests = model.requests
        for earlier, later in zip(requests, requests[1:]):
            assert later["messages"][: len(earlier["messages"])] == earlier["messages"]
            assert later["system"] == earlier["system"]
            assert later["tools"] == earlier["tools"]


class TestToolRounds:
    async def test_runs_tools_and_reports_entities(self):
        model = ScriptedModel(
            tool_call(use()),
            answer("Yes: [Operation](entity:class/cls-1)."),
        )
        tool = FakeTool()
        service, repository = make_service(model, tools=[tool])
        conversation = await service.create_conversation()

        events = await run(service, conversation.id)

        assert events[0] == ToolStarted("tu-1", "search_entities", {"query": "Operation"})
        assert events[1] == ToolFinished("tu-1", "search_entities", "Found 1", (OPERATION,), False)
        assert events[-1] == TurnCompleted(StopReason.END_TURN, 30, 13)
        assert tool.calls == [{"query": "Operation"}]

        stored = repository.messages[conversation.id]
        assert [m.role for m in stored] == [
            ChatRole.USER,
            ChatRole.ASSISTANT,
            ChatRole.USER,
            ChatRole.ASSISTANT,
        ]
        result = stored[2].blocks[0]
        assert isinstance(result, ToolResultBlock)
        assert result.tool_use_id == "tu-1"
        assert result.entities == (OPERATION,)
        assert result.summary == "Found 1"
        # The second request carries the tool result
        assert model.requests[1]["messages"][-1].blocks == (result,)

    async def test_parallel_tool_calls_answered_in_one_message(self):
        model = ScriptedModel(tool_call(use("a"), use("b")), answer("done"))
        service, repository = make_service(model)
        conversation = await service.create_conversation()

        await run(service, conversation.id)

        results = repository.messages[conversation.id][2].blocks
        assert [r.tool_use_id for r in results] == ["a", "b"]

    async def test_unknown_tool_and_tool_crash_become_error_results(self):
        model = ScriptedModel(
            tool_call(use("a", name="drop_table"), use("b", name="broken")), answer("sorry")
        )
        service, repository = make_service(
            model, tools=[FakeTool(), FakeTool(name="broken", error=RuntimeError("boom"))]
        )
        conversation = await service.create_conversation()

        events = await run(service, conversation.id)

        finished = [e for e in events if isinstance(e, ToolFinished)]
        assert [f.is_error for f in finished] == [True, True]
        unknown, crashed = repository.messages[conversation.id][2].blocks
        assert "Unknown tool 'drop_table'" in unknown.content
        assert "RuntimeError: boom" in crashed.content
        assert isinstance(events[-1], TurnCompleted)

    async def test_tool_round_limit_adds_note_then_fails(self):
        model = ScriptedModel(tool_call(use("a")), tool_call(use("b")))
        tool = FakeTool()
        service, repository = make_service(model, tools=[tool], rounds=1)
        conversation = await service.create_conversation()

        events = await run(service, conversation.id)

        assert len(tool.calls) == 1  # round 2's call is not run
        assert isinstance(events[-1], ChatFailed)
        assert "1 tool rounds" in events[-1].message
        stored = repository.messages[conversation.id]
        assert stored[2].blocks[-1] == ContextBlock(LIMIT_NOTE)
        unrun = stored[4].blocks[0]
        assert unrun.tool_use_id == "b" and unrun.is_error
        assert "limit" in unrun.content

    async def test_cut_off_tool_call_is_answered_but_not_run(self):
        model = ScriptedModel(tool_call(use("a"), stop=StopReason.MAX_TOKENS))
        tool = FakeTool()
        service, repository = make_service(model, tools=[tool])
        conversation = await service.create_conversation()

        events = await run(service, conversation.id)

        assert tool.calls == []
        assert events[-1] == TurnCompleted(StopReason.MAX_TOKENS, 20, 8)
        unrun = repository.messages[conversation.id][2].blocks[0]
        assert unrun.tool_use_id == "a" and unrun.is_error


class TestFailures:
    async def test_missing_conversation_raises_before_events(self):
        service, _ = make_service(ScriptedModel())

        with pytest.raises(ConversationNotFoundError):
            await run(service, "nope")

    @pytest.mark.parametrize(
        "error, expected",
        [
            (ChatModelError("bad", status_code=401), "rejected its API key"),
            (ChatModelError("slow", status_code=429), "rate limiting"),
            (ValueError("No provider available for model: x"), "No provider available"),
            (RuntimeError("boom"), "RuntimeError"),
        ],
    )
    async def test_model_error_yields_chat_failed(self, error, expected):
        model = ScriptedModel([TextDelta("partial"), error])
        service, repository = make_service(model)
        conversation = await service.create_conversation()

        events = await run(service, conversation.id)

        assert events[0] == TextDelta("partial")
        assert isinstance(events[-1], ChatFailed)
        assert expected in events[-1].message
        # The user message is kept; no partial assistant message is stored
        assert [m.role for m in repository.messages[conversation.id]] == [ChatRole.USER]

    async def test_stream_without_turn_end_fails(self):
        service, _ = make_service(ScriptedModel([TextDelta("x")]))
        conversation = await service.create_conversation()

        events = await run(service, conversation.id)

        assert isinstance(events[-1], ChatFailed)


class TestConversations:
    async def test_status_reports_model_availability(self):
        service, _ = make_service(ScriptedModel())
        status = service.status()
        assert (status.model, status.available, status.max_tool_rounds) == (
            "claude-sonnet-5-5",
            True,
            8,
        )
        assert status.available_models == ("claude-sonnet-5-5",)

        unsupported, _ = make_service(ScriptedModel(supported=()))
        assert unsupported.status().available is False

    async def test_list_latest_first_and_delete(self):
        model = ScriptedModel(answer("a"))
        service, repository = make_service(model)
        older = await service.create_conversation()
        newer = await service.create_conversation()
        await run(service, older.id)  # updating makes it the latest

        listed = await service.list_conversations()
        assert [c.id for c in listed] == [older.id, newer.id]

        await service.delete_conversation(older.id)
        assert older.id not in repository.conversations
        with pytest.raises(ConversationNotFoundError):
            await service.delete_conversation(older.id)
        with pytest.raises(ConversationNotFoundError):
            await service.list_messages(older.id)

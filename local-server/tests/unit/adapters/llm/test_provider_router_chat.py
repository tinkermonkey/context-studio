"""
Unit tests for LLMProviderRouter.stream_chat.

Tests verify:
- Chat routes to the first chat-capable provider that supports the model
- A 401/403 before the first event falls through to the next provider
- A connection error or timeout before the first event falls through for that call
  only, with a warning, without rejecting the provider
- Errors after streaming started, and other errors, propagate unchanged
- A model only a non-chat provider (OpenAI) supports is rejected clearly
- A multi-turn tool-calling exchange runs end to end over recorded OpenRouter streams
- Model suggestions come from the chat adapters, deduplicated
"""

import logging
from pathlib import Path

import anthropic
import httpx
import pytest

from adapters.llm.openrouter_chat import OpenRouterChatModel
from adapters.llm.provider_router import LLMProviderRouter
from domain.chat.entities import ChatMessage
from domain.chat.exceptions import ChatModelError
from domain.chat.value_objects import (
    ChatRole,
    ModelTurnEnded,
    StopReason,
    TextBlock,
    TextDelta,
    ToolCallRequested,
    ToolResultBlock,
    ToolSpec,
)

FIXTURES = Path(__file__).parent / "fixtures" / "chat_streams"
MODEL = "claude-sonnet-5-5"
QUESTION = ChatMessage(
    id="m0", conversation_id="c1", seq=0, role=ChatRole.USER, blocks=(TextBlock("hi"),)
)


class StubProvider:
    """Completion provider stub; the router only asks it which models it supports."""

    def __init__(self, models):
        self._models = models

    def is_model_available(self, model):
        return model in self._models


class FakeChatModel:
    """Chat model that yields events, optionally raising before or after them."""

    def __init__(self, events=(), error=None, raise_after_events=False, models=()):
        self._events = list(events)
        self._error = error
        self._raise_after_events = raise_after_events
        self._models = list(models)
        self.calls = 0

    def list_models(self):
        return list(self._models)

    async def stream_chat(self, **kwargs):
        self.calls += 1
        if self._error is not None and not self._raise_after_events:
            raise self._error
        for event in self._events:
            yield event
        if self._error is not None:
            raise self._error


def _end(text="ok"):
    return ModelTurnEnded(
        stop_reason=StopReason.END_TURN, tokens_in=1, tokens_out=1, blocks=(TextBlock(text),)
    )


def _router(providers, chat_models):
    router = LLMProviderRouter(openai_api_key="dummy-key")
    router._providers.clear()
    router._providers.update(providers)
    router._chat_models.clear()
    router._chat_models.update(chat_models)
    return router


async def _collect(router, messages=(QUESTION,), tools=(), model=MODEL):
    return [
        event
        async for event in router.stream_chat(
            system="sys", messages=list(messages), tools=list(tools), model=model
        )
    ]


@pytest.mark.llm
class TestRouterStreamChat:
    def test_chat_models_created_for_anthropic_and_openrouter_keys(self):
        router = LLMProviderRouter(
            openai_api_key="o-key", anthropic_api_key="a-key", openrouter_api_key="r-key"
        )
        assert sorted(router._chat_models) == ["anthropic", "openrouter"]

    async def test_routes_to_first_supporting_chat_provider(self):
        anthropic = FakeChatModel([TextDelta("a"), _end("a")])
        openrouter = FakeChatModel([TextDelta("r"), _end("r")])
        router = _router(
            {"anthropic": StubProvider([MODEL]), "openrouter": StubProvider([MODEL])},
            {"anthropic": anthropic, "openrouter": openrouter},
        )

        events = await _collect(router)

        assert events[0] == TextDelta("a")
        assert openrouter.calls == 0

    @pytest.mark.parametrize("status_code", [401, 403])
    async def test_auth_failure_before_first_event_falls_through(self, status_code):
        anthropic = FakeChatModel(error=ChatModelError("bad key", status_code=status_code))
        openrouter = FakeChatModel([TextDelta("r"), _end("r")])
        router = _router(
            {"anthropic": StubProvider([MODEL]), "openrouter": StubProvider([MODEL])},
            {"anthropic": anthropic, "openrouter": openrouter},
        )

        events = await _collect(router)
        await _collect(router)

        assert events[0] == TextDelta("r")
        assert anthropic.calls == 1  # rejected provider skipped on the second turn
        assert router._rejected_providers == {"anthropic"}

    async def test_auth_failure_after_streaming_started_propagates(self):
        error = ChatModelError("bad key", status_code=401)
        anthropic = FakeChatModel([TextDelta("partial")], error=error, raise_after_events=True)
        openrouter = FakeChatModel([_end()])
        router = _router(
            {"anthropic": StubProvider([MODEL]), "openrouter": StubProvider([MODEL])},
            {"anthropic": anthropic, "openrouter": openrouter},
        )

        with pytest.raises(ChatModelError) as exc_info:
            await _collect(router)

        assert exc_info.value is error
        assert openrouter.calls == 0

    @pytest.mark.parametrize(
        "error",
        [ChatModelError("rate", status_code=429), RuntimeError("boom")],
        ids=["rate-limit", "other"],
    )
    async def test_non_auth_errors_propagate(self, error):
        anthropic = FakeChatModel(error=error)
        openrouter = FakeChatModel([_end()])
        router = _router(
            {"anthropic": StubProvider([MODEL]), "openrouter": StubProvider([MODEL])},
            {"anthropic": anthropic, "openrouter": openrouter},
        )

        with pytest.raises(type(error)):
            await _collect(router)

        assert openrouter.calls == 0
        assert router._rejected_providers == set()

    @pytest.mark.parametrize(
        "error",
        [
            anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com")),
            anthropic.APIConnectionError(
                request=httpx.Request("POST", "https://api.anthropic.com")
            ),
            httpx.ConnectError("no route"),
            httpx.ReadTimeout("slow"),
        ],
        ids=["anthropic-timeout", "anthropic-connection", "httpx-connect", "httpx-timeout"],
    )
    async def test_connection_failure_falls_through_without_rejecting(self, error, caplog):
        anthropic_model = FakeChatModel(error=error)
        openrouter = FakeChatModel([TextDelta("r"), _end("r")])
        router = _router(
            {"anthropic": StubProvider([MODEL]), "openrouter": StubProvider([MODEL])},
            {"anthropic": anthropic_model, "openrouter": openrouter},
        )

        with caplog.at_level(logging.WARNING, logger="adapters.llm.provider_router"):
            events = await _collect(router)
            await _collect(router)

        assert events[0] == TextDelta("r")
        assert anthropic_model.calls == 2  # not rejected: tried again on the next turn
        assert router._rejected_providers == set()
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("'anthropic' could not be reached" in w for w in warnings)

    async def test_wrapped_connection_failure_falls_through(self):
        """The OpenRouter adapter wraps httpx errors in a ChatModelError raised from them."""
        try:
            try:
                raise httpx.ConnectTimeout("connect timed out")
            except httpx.ConnectTimeout as e:
                raise ChatModelError("OpenRouter request failed") from e
        except ChatModelError as wrapped:
            error = wrapped
        first = FakeChatModel(error=error)
        second = FakeChatModel([_end("ok")])
        router = _router(
            {"openrouter": StubProvider([MODEL]), "other": StubProvider([MODEL])},
            {"openrouter": first, "other": second},
        )

        events = await _collect(router)

        assert events[-1] == _end("ok")
        assert router._rejected_providers == set()

    async def test_connection_failure_after_streaming_started_propagates(self):
        error = httpx.ReadTimeout("stalled")
        anthropic_model = FakeChatModel([TextDelta("partial")], error=error, raise_after_events=True)
        openrouter = FakeChatModel([_end()])
        router = _router(
            {"anthropic": StubProvider([MODEL]), "openrouter": StubProvider([MODEL])},
            {"anthropic": anthropic_model, "openrouter": openrouter},
        )

        with pytest.raises(httpx.ReadTimeout):
            await _collect(router)

        assert openrouter.calls == 0

    async def test_every_provider_unreachable_raises_last_error(self):
        last = httpx.ConnectError("down too")
        router = _router(
            {"anthropic": StubProvider([MODEL]), "openrouter": StubProvider([MODEL])},
            {
                "anthropic": FakeChatModel(error=httpx.ConnectError("down")),
                "openrouter": FakeChatModel(error=last),
            },
        )

        with pytest.raises(httpx.ConnectError) as exc_info:
            await _collect(router)

        assert exc_info.value is last
        assert router._rejected_providers == set()

    async def test_all_providers_rejecting_raises_last_auth_error(self):
        last = ChatModelError("bad", status_code=401)
        router = _router(
            {"anthropic": StubProvider([MODEL]), "openrouter": StubProvider([MODEL])},
            {
                "anthropic": FakeChatModel(error=ChatModelError("bad", status_code=401)),
                "openrouter": FakeChatModel(error=last),
            },
        )

        with pytest.raises(ChatModelError) as exc_info:
            await _collect(router)

        assert exc_info.value is last

    async def test_model_only_supported_by_non_chat_provider_is_rejected(self):
        router = _router({"openai": StubProvider(["gpt-4o"])}, {})

        with pytest.raises(ValueError, match="No chat-capable provider available"):
            await _collect(router, model="gpt-4o")

    async def test_unknown_model_is_rejected(self):
        router = _router({"anthropic": StubProvider([MODEL])}, {"anthropic": FakeChatModel()})

        with pytest.raises(ValueError, match="No provider available for model"):
            await _collect(router, model="claude-unknown")


@pytest.mark.llm
class TestRouterMultiTurnToolExchange:
    async def test_tool_calling_exchange_over_recorded_openrouter_streams(self):
        """Turn 1 requests tools; the tool results go back; turn 2 answers with a link."""
        responses = iter(
            [
                (FIXTURES / "openrouter_tool_call.sse").read_bytes(),
                (FIXTURES / "openrouter_answer.sse").read_bytes(),
            ]
        )

        def handler(request):
            return httpx.Response(200, content=next(responses))

        router = _router(
            {"openrouter": StubProvider([MODEL])},
            {"openrouter": OpenRouterChatModel("k", transport=httpx.MockTransport(handler))},
        )
        search = ToolSpec(name="search_entities", description="Search.", input_schema={})
        messages = [QUESTION]

        first = await _collect(router, messages, tools=[search])
        calls = [e.tool_use for e in first if isinstance(e, ToolCallRequested)]
        assert first[-1].stop_reason == StopReason.TOOL_USE and len(calls) == 2

        messages.append(
            ChatMessage(
                id="m1",
                conversation_id="c1",
                seq=1,
                role=ChatRole.ASSISTANT,
                blocks=first[-1].blocks,
            )
        )
        messages.append(
            ChatMessage(
                id="m2",
                conversation_id="c1",
                seq=2,
                role=ChatRole.USER,
                blocks=tuple(ToolResultBlock(tool_use_id=c.id, content="[]") for c in calls),
            )
        )
        second = await _collect(router, messages, tools=[search])

        assert second[-1].stop_reason == StopReason.END_TURN
        answer = "".join(e.text for e in second if isinstance(e, TextDelta))
        assert "(entity:class/6f1c2a9e-0000-4000-8000-000000000001)" in answer


@pytest.mark.llm
class TestRouterSupportsModel:
    def test_only_chat_capable_unrejected_providers_count(self):
        router = _router(
            {
                "openai": StubProvider(["gpt-4o"]),
                "anthropic": StubProvider([MODEL]),
                "openrouter": StubProvider(["openai/gpt-5"]),
            },
            {"anthropic": FakeChatModel(), "openrouter": FakeChatModel()},
        )

        assert router.supports_model(MODEL)
        assert router.supports_model("openai/gpt-5")
        assert not router.supports_model("gpt-4o")  # OpenAI has no chat adapter

        router._rejected_providers.add("anthropic")
        assert not router.supports_model(MODEL)

    def test_list_models_from_chat_adapters_deduplicated(self):
        router = _router(
            {
                "openai": StubProvider(["gpt-4o"]),
                "anthropic": StubProvider([MODEL]),
                "openrouter": StubProvider([MODEL]),
            },
            {
                "anthropic": FakeChatModel(models=[MODEL, "claude-opus-4-7"]),
                "openrouter": FakeChatModel(models=[MODEL, "google/gemini-3-flash-preview"]),
            },
        )

        assert router.list_models() == [MODEL, "claude-opus-4-7", "google/gemini-3-flash-preview"]
        router._rejected_providers.add("anthropic")
        assert router.list_models() == [MODEL, "google/gemini-3-flash-preview"]

    def test_openrouter_only_router_suggests_claude_models(self):
        router = LLMProviderRouter(openrouter_api_key="r-key")

        models = router.list_models()

        assert "claude-sonnet-5-5" in models and "claude-opus-4-7" in models
        assert len(models) == len(set(models))
        assert all(router.supports_model(m) for m in models)

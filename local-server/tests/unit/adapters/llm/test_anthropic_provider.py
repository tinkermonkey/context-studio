"""
Unit tests for AnthropicProvider request building.

Tests verify:
- `temperature` is sent via `extra_body` (the anthropic SDK 1.x removed it from
  `messages.create()`), and not at all for models that reject it
- `seed` is never sent (the Messages API has no seed parameter)
- The real installed SDK accepts the request the provider builds and puts
  `temperature` in the request JSON (guards against SDK signature drift)
- The response's text is read from its text blocks, wherever they are: a model
  that thinks by default opens its response with a thinking block
- The system prompt is sent as a block the API may cache, and a response's
  input tokens include those written to and read from the cache
"""

import json
from types import SimpleNamespace

import pytest

from adapters.llm.anthropic_provider import AnthropicProvider


def _fake_message(text: str = "ok") -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=3, output_tokens=4),
        stop_reason="end_turn",
    )


class FakeMessages:
    """Records the kwargs passed to `messages.create()`."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _fake_message()


def _provider_with_fake_client() -> tuple[AnthropicProvider, FakeMessages]:
    provider = AnthropicProvider("test-key")
    messages = FakeMessages()
    provider._client = SimpleNamespace(messages=messages)
    return provider, messages


@pytest.mark.llm
class TestAnthropicProviderRequest:
    """Kwargs AnthropicProvider sends to the SDK."""

    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize(
        "model", ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"]
    )
    async def test_temperature_sent_via_extra_body(self, model, use_async):
        provider, messages = _provider_with_fake_client()
        kwargs = dict(system_prompt="sys", user_prompt="hi", model=model, temperature=0.2, seed=7)

        if use_async:
            response = await provider.complete_async(**kwargs)
        else:
            response = provider.complete(**kwargs)

        assert response.content == "ok"
        sent = messages.calls[0]
        assert sent["extra_body"] == {"temperature": 0.2}
        assert "temperature" not in sent
        assert "seed" not in sent
        assert sent["model"] == model
        assert sent["system"] == [
            {"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}
        ]
        assert sent["messages"] == [{"role": "user", "content": "hi"}]

    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize(
        "model", ["claude-opus-4-7", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
    )
    async def test_no_temperature_for_models_that_reject_it(self, model, use_async):
        provider, messages = _provider_with_fake_client()
        kwargs = dict(system_prompt="sys", user_prompt="hi", model=model, temperature=0.2)

        if use_async:
            await provider.complete_async(**kwargs)
        else:
            provider.complete(**kwargs)

        sent = messages.calls[0]
        assert "temperature" not in sent
        assert "extra_body" not in sent

    @pytest.mark.parametrize(
        "model, expected_temperature",
        [("claude-sonnet-4-6", 0.0), ("claude-opus-4-7", None), ("claude-sonnet-5-5", None)],
    )
    def test_installed_sdk_accepts_request(self, model, expected_temperature):
        """The real SDK builds the request without a TypeError; check its JSON body."""
        anthropic = pytest.importorskip("anthropic")
        httpx2 = pytest.importorskip("httpx2")  # the HTTP client anthropic 1.x uses
        bodies: list[dict] = []

        def handler(request):
            bodies.append(json.loads(request.content))
            return httpx2.Response(
                200,
                json={
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "model": model,
                    "content": [{"type": "text", "text": "hi"}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 1, "output_tokens": 2},
                },
            )

        provider = AnthropicProvider("test-key")
        provider._client = anthropic.Anthropic(
            api_key="test-key",
            http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
            max_retries=0,
        )

        response = provider.complete(
            system_prompt="sys", user_prompt="hi", model=model, temperature=0.0, seed=1
        )

        assert response.content == "hi"
        body = bodies[0]
        assert body.get("temperature") == expected_temperature
        assert "seed" not in body
        assert body["model"] == model


def _sdk_provider(content: list[dict]) -> AnthropicProvider:
    """A provider whose real SDK client is answered with the given content blocks."""
    anthropic = pytest.importorskip("anthropic")
    httpx2 = pytest.importorskip("httpx2")

    def handler(request):
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5-5",
                "content": content,
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 2},
            },
        )

    provider = AnthropicProvider("test-key")
    provider._client = anthropic.Anthropic(
        api_key="test-key",
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        max_retries=0,
    )
    return provider


@pytest.mark.llm
class TestAnthropicProviderResponseText:
    """What AnthropicProvider returns as the content of a response."""

    THINKING = {"type": "thinking", "thinking": "", "signature": "sig"}

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_text_after_a_thinking_block_is_returned(self, use_async):
        """A response that opens with a thinking block still yields its text."""
        provider, messages = _provider_with_fake_client()
        messages.create = lambda **kwargs: SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking="", signature="sig"),
                SimpleNamespace(type="text", text='{"triples": []}'),
            ],
            usage=SimpleNamespace(input_tokens=3, output_tokens=4),
            stop_reason="end_turn",
        )
        kwargs = {"system_prompt": "sys", "user_prompt": "hi", "model": "claude-sonnet-5-5"}

        if use_async:
            response = await provider.complete_async(**kwargs)
        else:
            response = provider.complete(**kwargs)

        assert response.content == '{"triples": []}'
        assert response.finish_reason == "end_turn"

    def test_thinking_block_from_the_installed_sdk_is_skipped(self):
        """The real SDK's thinking block has no `text`; reading it used to raise."""
        provider = _sdk_provider([self.THINKING, {"type": "text", "text": "hi"}])

        response = provider.complete(
            system_prompt="sys", user_prompt="hi", model="claude-sonnet-5-5"
        )

        assert response.content == "hi"

    def test_text_blocks_are_joined_in_order(self):
        provider = _sdk_provider(
            [
                {"type": "text", "text": "one "},
                self.THINKING,
                {"type": "text", "text": "two"},
            ]
        )

        response = provider.complete(
            system_prompt="sys", user_prompt="hi", model="claude-sonnet-5-5"
        )

        assert response.content == "one two"

    @pytest.mark.parametrize("content", [[], [THINKING]])
    def test_a_response_with_no_text_block_is_empty(self, content):
        provider = _sdk_provider(content)

        response = provider.complete(
            system_prompt="sys", user_prompt="hi", model="claude-sonnet-5-5"
        )

        assert response.content == ""


@pytest.mark.llm
class TestAnthropicProviderPromptCaching:
    """The system prompt is cacheable, and cached tokens are counted as input."""

    def test_an_empty_system_prompt_is_sent_as_it_is(self):
        """The API rejects an empty text block."""
        provider, messages = _provider_with_fake_client()

        provider.complete(system_prompt="", user_prompt="hi", model="claude-sonnet-5-5")

        assert messages.calls[0]["system"] == ""

    def test_the_installed_sdk_sends_the_cacheable_system_block(self):
        anthropic = pytest.importorskip("anthropic")
        httpx2 = pytest.importorskip("httpx2")
        bodies: list[dict] = []

        def handler(request):
            bodies.append(json.loads(request.content))
            return httpx2.Response(
                200,
                json={
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-haiku-5-5",
                    "content": [{"type": "text", "text": "hi"}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": 40,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 19000,
                        "output_tokens": 5,
                    },
                },
            )

        provider = AnthropicProvider("test-key")
        provider._client = anthropic.Anthropic(
            api_key="test-key",
            http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
            max_retries=0,
        )

        response = provider.complete(
            system_prompt="the catalog", user_prompt="hi", model="claude-haiku-5-5"
        )

        assert bodies[0]["system"] == [
            {"type": "text", "text": "the catalog", "cache_control": {"type": "ephemeral"}}
        ]
        # 40 uncached + 19,000 read from the cache
        assert response.tokens_in == 19040
        assert response.tokens_out == 5

    def test_tokens_written_to_the_cache_count_as_input(self):
        provider, messages = _provider_with_fake_client()
        messages.create = lambda **kwargs: SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(
                input_tokens=10,
                cache_creation_input_tokens=500,
                cache_read_input_tokens=0,
                output_tokens=4,
            ),
            stop_reason="end_turn",
        )

        response = provider.complete(
            system_prompt="sys", user_prompt="hi", model="claude-sonnet-5-5"
        )

        assert response.tokens_in == 510

    def test_a_response_without_cache_fields_counts_its_input_tokens(self):
        provider, _ = _provider_with_fake_client()

        response = provider.complete(
            system_prompt="sys", user_prompt="hi", model="claude-sonnet-5-5"
        )

        assert response.tokens_in == 3

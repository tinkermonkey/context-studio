"""
Unit tests for AnthropicProvider request building.

Tests verify:
- `temperature` is sent via `extra_body` (the anthropic SDK 1.x removed it from
  `messages.create()`), and not at all for models that reject it
- `seed` is never sent (the Messages API has no seed parameter)
- The real installed SDK accepts the request the provider builds and puts
  `temperature` in the request JSON (guards against SDK signature drift)
"""

import json
from types import SimpleNamespace

import pytest

from adapters.llm.anthropic_provider import AnthropicProvider


def _fake_message(text: str = "ok") -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
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
        assert sent["system"] == "sys"
        assert sent["messages"] == [{"role": "user", "content": "hi"}]

    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize("model", ["claude-opus-4-7", "claude-sonnet-5-5"])
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

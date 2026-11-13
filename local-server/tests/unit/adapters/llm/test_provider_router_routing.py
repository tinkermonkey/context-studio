"""
Unit tests for LLMProviderRouter adapter.

Tests verify:
- Provider initialization with API keys
- Model routing to correct providers
- Model availability checking
- Union of available models from all providers
- Initialization errors are logged and tolerated if at least one provider succeeds
- ValueError is raised when all configured providers fail to initialize
- An auth failure (401/403) falls through to the next provider that supports the model
- A completion's failure that every request for the model will meet is raised as
  the domain's error for it
"""

from unittest.mock import Mock, patch

import anthropic as anthropic_sdk
import httpx
import openai as openai_sdk
import pytest

from adapters.llm.provider_router import LLMProviderRouter
from domain.pipelines.exceptions import (
    LLMProviderError,
    LLMRateLimitError,
    LLMRequestRefusedError,
    LLMTransientError,
)
from domain.pipelines.ports import LLMResponse


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, available_models: list[str]):
        self._available_models = available_models

    def complete(
        self,
        system_prompt,
        user_prompt,
        model,
        temperature=0.0,
        max_tokens=2000,
        response_format=None,
        timeout=None,
        seed=None,
    ):
        """Mock complete method."""
        return LLMResponse(
            content="mock response",
            tokens_in=10,
            tokens_out=20,
            duration_ms=0.0,
            finish_reason="stop",
            model=model,
        )

    async def complete_async(
        self,
        system_prompt,
        user_prompt,
        model,
        temperature=0.0,
        max_tokens=2000,
        response_format=None,
        timeout=None,
        seed=None,
    ):
        """Mock complete_async method."""
        return self.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
            seed=seed,
        )

    def is_model_available(self, model: str) -> bool:
        """Check if model is available."""
        return model in self._available_models

    def list_available_models(self) -> list[str]:
        """List available models."""
        return self._available_models


@pytest.mark.llm
class TestLLMProviderRouter:
    """Tests for LLMProviderRouter adapter."""

    @staticmethod
    def create_test_router():
        """Create a router with a dummy API key for testing routing logic."""
        router = LLMProviderRouter(openai_api_key="dummy-key")
        router._providers.clear()
        return router

    def test_forget_reaches_every_provider(self):
        """Any provider may hold the response, so each is told to drop it."""
        router = self.create_test_router()
        router._providers["openrouter"] = Mock()
        router._providers["anthropic"] = Mock()

        router.forget(
            "sys", "user", "gpt-4", temperature=0.0, max_tokens=8000, response_format="json"
        )

        for provider in router._providers.values():
            provider.forget.assert_called_once_with(
                system_prompt="sys",
                user_prompt="user",
                model="gpt-4",
                temperature=0.0,
                max_tokens=8000,
                response_format="json",
            )

    def test_router_init_with_no_keys(self):
        """Router raises ValueError when initialized with no API keys."""
        with pytest.raises(ValueError) as exc_info:
            LLMProviderRouter()

        assert "At least one LLM provider API key must be configured" in str(exc_info.value)

    @patch("adapters.llm.provider_router.OpenAIProvider")
    def test_router_init_with_valid_openai_key(self, mock_openai_class):
        """Router initializes OpenAI provider with valid key starting with 'sk-'."""
        mock_provider = Mock()
        mock_openai_class.return_value = mock_provider

        router = LLMProviderRouter(openai_api_key="sk-test-key-123")

        # OpenAI provider should be initialized
        assert "openai" in router._providers
        mock_openai_class.assert_called_once_with("sk-test-key-123")

    @patch("adapters.llm.provider_router.AnthropicProvider")
    def test_router_init_with_anthropic_key(self, mock_anthropic_class):
        """Router initializes Anthropic provider with API key."""
        mock_provider = Mock()
        mock_anthropic_class.return_value = mock_provider

        router = LLMProviderRouter(anthropic_api_key="sk-ant-test-key-123")

        # Anthropic provider should be initialized
        assert "anthropic" in router._providers
        mock_anthropic_class.assert_called_once_with("sk-ant-test-key-123")

    @patch("adapters.llm.provider_router.OpenAIProvider")
    @patch("adapters.llm.provider_router.AnthropicProvider")
    def test_router_init_with_both_keys(self, mock_anthropic_class, mock_openai_class):
        """Router initializes both providers when both keys are provided."""
        mock_openai_provider = Mock()
        mock_anthropic_provider = Mock()
        mock_openai_class.return_value = mock_openai_provider
        mock_anthropic_class.return_value = mock_anthropic_provider

        router = LLMProviderRouter(
            openai_api_key="sk-test-key", anthropic_api_key="sk-ant-test-key"
        )

        # Both providers should be initialized
        assert "openai" in router._providers
        assert "anthropic" in router._providers

    def test_router_is_model_available_with_no_providers(self):
        """is_model_available returns False when no providers are configured."""
        router = self.create_test_router()

        assert router.is_model_available("gpt-4o") is False
        assert router.is_model_available("claude-opus-4-6") is False

    def test_router_list_available_models_with_no_providers(self):
        """list_available_models returns empty list when no providers are configured."""
        router = self.create_test_router()

        assert router.list_available_models() == []

    def test_router_routes_to_openai_provider(self):
        """Router routes OpenAI models to OpenAI provider."""
        router = self.create_test_router()
        openai_provider = MockLLMProvider(["gpt-4o", "gpt-3.5-turbo"])
        router._providers["openai"] = openai_provider

        candidates = router._providers_for("gpt-4o")

        assert candidates == [("openai", openai_provider)]

    def test_router_routes_to_anthropic_provider(self):
        """Router routes Anthropic models to Anthropic provider."""
        router = self.create_test_router()
        anthropic_provider = MockLLMProvider(["claude-opus-4-6"])
        router._providers["anthropic"] = anthropic_provider

        candidates = router._providers_for("claude-opus-4-6")

        assert candidates == [("anthropic", anthropic_provider)]

    def test_router_raises_for_unavailable_model(self):
        """Router raises ValueError when model is not available from any provider."""
        router = self.create_test_router()
        openai_provider = MockLLMProvider(["gpt-4o"])
        router._providers["openai"] = openai_provider

        with pytest.raises(ValueError) as exc_info:
            router._providers_for("claude-opus-4-6")

        assert "No provider available for model: claude-opus-4-6" in str(exc_info.value)

    def test_router_is_model_available_openai(self):
        """is_model_available returns True for OpenAI models."""
        router = self.create_test_router()
        openai_provider = MockLLMProvider(["gpt-4o", "gpt-3.5-turbo"])
        router._providers["openai"] = openai_provider

        assert router.is_model_available("gpt-4o") is True
        assert router.is_model_available("gpt-3.5-turbo") is True
        assert router.is_model_available("claude-opus-4-6") is False

    def test_router_is_model_available_anthropic(self):
        """is_model_available returns True for Anthropic models."""
        router = self.create_test_router()
        anthropic_provider = MockLLMProvider(["claude-opus-4-6", "claude-sonnet-4-6"])
        router._providers["anthropic"] = anthropic_provider

        assert router.is_model_available("claude-opus-4-6") is True
        assert router.is_model_available("claude-sonnet-4-6") is True
        assert router.is_model_available("gpt-4o") is False

    def test_router_list_available_models_single_provider(self):
        """list_available_models returns union when only one provider is configured."""
        router = self.create_test_router()
        openai_provider = MockLLMProvider(["gpt-4o", "gpt-3.5-turbo"])
        router._providers["openai"] = openai_provider

        models = router.list_available_models()

        assert sorted(models) == sorted(["gpt-4o", "gpt-3.5-turbo"])

    def test_router_list_available_models_multiple_providers(self):
        """list_available_models returns union of models from all providers."""
        router = self.create_test_router()
        openai_provider = MockLLMProvider(["gpt-4o", "gpt-3.5-turbo"])
        anthropic_provider = MockLLMProvider(["claude-opus-4-6", "claude-sonnet-4-6"])
        router._providers["openai"] = openai_provider
        router._providers["anthropic"] = anthropic_provider

        models = router.list_available_models()

        expected = ["gpt-4o", "gpt-3.5-turbo", "claude-opus-4-6", "claude-sonnet-4-6"]
        assert sorted(models) == sorted(expected)

    def test_router_complete_routes_to_correct_provider(self):
        """complete method routes to correct provider based on model."""
        router = self.create_test_router()
        openai_provider = MockLLMProvider(["gpt-4o"])
        openai_provider.complete = Mock(
            return_value=LLMResponse(
                content="OpenAI response",
                tokens_in=10,
                tokens_out=20,
                duration_ms=0.0,
                finish_reason="stop",
                model="gpt-4o",
            )
        )
        router._providers["openai"] = openai_provider

        response = router.complete(
            system_prompt="You are helpful",
            user_prompt="Hello",
            model="gpt-4o",
        )

        assert response.content == "OpenAI response"
        assert response.model == "gpt-4o"
        openai_provider.complete.assert_called_once()

    def test_router_complete_raises_for_unavailable_model(self):
        """complete method raises ValueError for unavailable models."""
        router = self.create_test_router()

        with pytest.raises(ValueError) as exc_info:
            router.complete(
                system_prompt="You are helpful",
                user_prompt="Hello",
                model="unknown-model",
            )

        assert "No provider available for model: unknown-model" in str(exc_info.value)

    def test_router_complete_with_all_parameters(self):
        """complete method passes all parameters to provider."""
        router = self.create_test_router()
        openai_provider = Mock()
        openai_provider.is_model_available.return_value = True
        expected_response = LLMResponse(
            content="response",
            tokens_in=10,
            tokens_out=20,
            duration_ms=0.0,
            finish_reason="stop",
            model="gpt-4o",
        )
        openai_provider.complete.return_value = expected_response
        router._providers["openai"] = openai_provider

        response = router.complete(
            system_prompt="System",
            user_prompt="User",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000,
            response_format="json",
        )

        openai_provider.complete.assert_called_once_with(
            system_prompt="System",
            user_prompt="User",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000,
            response_format="json",
            timeout=None,
            seed=None,
        )
        assert response is expected_response

    @patch("adapters.llm.provider_router.OpenAIProvider")
    def test_router_init_single_configured_provider_fails(self, mock_openai_class):
        """Router raises ValueError when single configured provider fails to initialize."""
        mock_openai_class.side_effect = ValueError("Invalid API key")

        with pytest.raises(ValueError) as exc_info:
            LLMProviderRouter(openai_api_key="invalid-key")

        error_msg = str(exc_info.value)
        assert "No LLM providers could be initialized" in error_msg
        assert "openai" in error_msg
        assert "ValueError: Invalid API key" in error_msg

    @patch("adapters.llm.provider_router.OpenAIProvider")
    @patch("adapters.llm.provider_router.AnthropicProvider")
    def test_router_init_both_configured_providers_fail(
        self, mock_anthropic_class, mock_openai_class
    ):
        """Router raises ValueError with all error details when both providers fail."""
        mock_openai_class.side_effect = ValueError("OpenAI key invalid")
        mock_anthropic_class.side_effect = RuntimeError("Anthropic connection failed")

        with pytest.raises(ValueError) as exc_info:
            LLMProviderRouter(
                openai_api_key="invalid-openai-key",
                anthropic_api_key="invalid-anthropic-key",
            )

        error_msg = str(exc_info.value)
        assert "No LLM providers could be initialized" in error_msg
        assert "openai" in error_msg
        assert "ValueError: OpenAI key invalid" in error_msg
        assert "anthropic" in error_msg
        assert "RuntimeError: Anthropic connection failed" in error_msg

    @patch("adapters.llm.provider_router.OpenAIProvider")
    @patch("adapters.llm.provider_router.AnthropicProvider")
    def test_router_init_one_provider_succeeds_one_fails(
        self, mock_anthropic_class, mock_openai_class
    ):
        """Router initializes successfully with only the working provider when one fails."""
        mock_openai_provider = Mock()
        mock_openai_class.return_value = mock_openai_provider
        mock_anthropic_class.side_effect = ValueError("Anthropic key invalid")

        router = LLMProviderRouter(
            openai_api_key="valid-openai-key",
            anthropic_api_key="invalid-anthropic-key",
        )

        # OpenAI should be initialized and working
        assert "openai" in router._providers
        assert "anthropic" not in router._providers
        assert router._providers["openai"] is mock_openai_provider


class FakeAuthError(Exception):
    """Stands in for the SDKs' AuthenticationError / PermissionDeniedError."""

    def __init__(self, status_code: int = 401):
        super().__init__(f"HTTP {status_code}: invalid x-api-key")
        self.status_code = status_code


class FailingLLMProvider(MockLLMProvider):
    """Provider whose calls always raise the given error, counting attempts."""

    def __init__(self, available_models: list[str], error: Exception):
        super().__init__(available_models)
        self._error = error
        self.calls = 0

    def complete(self, *args, **kwargs):
        self.calls += 1
        raise self._error


@pytest.mark.llm
class TestLLMProviderRouterAuthFallback:
    """An auth failure on one provider falls through to the next supporting provider."""

    @staticmethod
    def create_router(**providers):
        router = LLMProviderRouter(openai_api_key="dummy-key")
        router._providers.clear()
        router._providers.update(providers)
        return router

    @staticmethod
    async def call(router, model, use_async):
        if use_async:
            return await router.complete_async(system_prompt="s", user_prompt="u", model=model)
        return router.complete(system_prompt="s", user_prompt="u", model=model)

    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize("status_code", [401, 403])
    async def test_auth_failure_falls_through_to_next_provider(self, use_async, status_code):
        anthropic = FailingLLMProvider(["claude-opus-4-7"], FakeAuthError(status_code))
        openrouter = MockLLMProvider(["claude-opus-4-7"])
        router = self.create_router(anthropic=anthropic, openrouter=openrouter)

        response = await self.call(router, "claude-opus-4-7", use_async)

        assert response.content == "mock response"
        assert anthropic.calls == 1

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_rejected_provider_is_skipped_on_later_calls(self, use_async):
        anthropic = FailingLLMProvider(["claude-opus-4-7"], FakeAuthError())
        openrouter = MockLLMProvider(["claude-opus-4-7"])
        router = self.create_router(anthropic=anthropic, openrouter=openrouter)

        await self.call(router, "claude-opus-4-7", use_async)
        await self.call(router, "claude-opus-4-7", use_async)

        assert anthropic.calls == 1

    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize(
        "error",
        [
            FakeAuthError(400),
            FakeAuthError(422),
            RuntimeError("boom"),
            # The domain errors a provider raises itself (OpenRouterProvider)
            LLMRequestRefusedError("OpenRouter API key is invalid or unauthorized"),
            LLMRateLimitError("OpenRouter rate limit exceeded"),
            LLMTransientError("OpenRouter API error: 503"),
        ],
        ids=["bad-request", "unprocessable", "other", "refused", "rate-limit", "transient"],
    )
    async def test_non_auth_errors_are_not_swallowed(self, use_async, error):
        anthropic = FailingLLMProvider(["claude-opus-4-7"], error)
        openrouter = FailingLLMProvider(["claude-opus-4-7"], RuntimeError("must not be called"))
        router = self.create_router(anthropic=anthropic, openrouter=openrouter)

        with pytest.raises(type(error)) as exc_info:
            await self.call(router, "claude-opus-4-7", use_async)

        assert exc_info.value is error
        assert openrouter.calls == 0
        assert router._rejected_providers == set()

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_all_supporting_providers_rejecting_raises_auth_error(self, use_async):
        last_error = FakeAuthError()
        anthropic = FailingLLMProvider(["claude-opus-4-7"], FakeAuthError())
        openrouter = FailingLLMProvider(["claude-opus-4-7"], last_error)
        router = self.create_router(anthropic=anthropic, openrouter=openrouter)

        with pytest.raises(LLMRequestRefusedError) as exc_info:
            await self.call(router, "claude-opus-4-7", use_async)
        assert str(exc_info.value) == "The openrouter provider rejected its API key"
        assert exc_info.value.__cause__ is last_error

        # Later calls are refused too, with no request sent, naming the
        # rejecting providers: a run still learns that every request will fail
        with pytest.raises(LLMRequestRefusedError) as exc_info:
            await self.call(router, "claude-opus-4-7", use_async)
        message = str(exc_info.value)
        assert "No provider available for model: claude-opus-4-7" in message
        assert "rejected their API key: anthropic, openrouter" in message
        assert anthropic.calls == 1
        assert openrouter.calls == 1

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_a_model_no_provider_supports_is_not_a_refusal(self, use_async):
        # A rejected key elsewhere does not make an unsupported model a refusal:
        # no provider that supports it was ever asked
        anthropic = FailingLLMProvider(["claude-opus-4-7"], FakeAuthError())
        router = self.create_router(anthropic=anthropic)
        with pytest.raises(LLMRequestRefusedError):
            await self.call(router, "claude-opus-4-7", use_async)

        with pytest.raises(ValueError, match="No provider available for model: gpt-4o"):
            await self.call(router, "gpt-4o", use_async)

    async def test_chat_for_a_model_left_without_a_provider_is_still_a_value_error(self):
        # Chat reports a ValueError's message to the user as it is
        anthropic = FailingLLMProvider(["claude-opus-4-7"], FakeAuthError())
        router = self.create_router(anthropic=anthropic)
        with pytest.raises(LLMRequestRefusedError):
            await self.call(router, "claude-opus-4-7", use_async=False)

        with pytest.raises(ValueError, match="rejected their API key: anthropic"):
            async for _ in router.stream_chat(
                system="", messages=[], tools=[], model="claude-opus-4-7"
            ):
                pass

    _REQUEST = httpx.Request("POST", "https://api.example.invalid/v1/messages")
    _SECRET = "sk-ant-0123456789abcdef"

    # A failure of the direct provider that outlasted the SDK's own retries,
    # as the SDK raises it, with a text that must not be shown
    SDK_OUTAGES = {
        "anthropic-overloaded": (
            lambda: anthropic_sdk.InternalServerError(
                f"Overloaded {TestLLMProviderRouterAuthFallback._SECRET}",
                response=httpx.Response(529, request=TestLLMProviderRouterAuthFallback._REQUEST),
                body=None,
            ),
            "The anthropic provider answered with a server error: 529",
        ),
        "openai-unavailable": (
            lambda: openai_sdk.InternalServerError(
                f"upstream {TestLLMProviderRouterAuthFallback._SECRET}",
                response=httpx.Response(503, request=TestLLMProviderRouterAuthFallback._REQUEST),
                body=None,
            ),
            "The anthropic provider answered with a server error: 503",
        ),
        "anthropic-timeout": (
            lambda: anthropic_sdk.APITimeoutError(
                request=TestLLMProviderRouterAuthFallback._REQUEST
            ),
            "The anthropic provider did not answer in time",
        ),
        "openai-timeout": (
            lambda: openai_sdk.APITimeoutError(request=TestLLMProviderRouterAuthFallback._REQUEST),
            "The anthropic provider did not answer in time",
        ),
        "anthropic-connection": (
            lambda: anthropic_sdk.APIConnectionError(
                message=f"Illegal header value b'{TestLLMProviderRouterAuthFallback._SECRET}'",
                request=TestLLMProviderRouterAuthFallback._REQUEST,
            ),
            "The anthropic provider could not be reached",
        ),
        "openai-connection": (
            lambda: openai_sdk.APIConnectionError(
                message=f"Illegal header value b'{TestLLMProviderRouterAuthFallback._SECRET}'",
                request=TestLLMProviderRouterAuthFallback._REQUEST,
            ),
            "The anthropic provider could not be reached",
        ),
    }

    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize("outage", list(SDK_OUTAGES))
    async def test_an_sdk_outage_is_a_provider_failure_with_a_fixed_message(
        self, use_async, outage
    ):
        make_error, message = self.SDK_OUTAGES[outage]
        error = make_error()
        anthropic = FailingLLMProvider(["claude-opus-4-7"], error)
        openrouter = FailingLLMProvider(["claude-opus-4-7"], RuntimeError("must not be called"))
        router = self.create_router(anthropic=anthropic, openrouter=openrouter)

        with pytest.raises(LLMProviderError) as exc_info:
            await self.call(router, "claude-opus-4-7", use_async)

        # Named by provider and kind, with none of the SDK error's text
        assert str(exc_info.value) == message
        assert self._SECRET not in str(exc_info.value)
        assert exc_info.value.__cause__ is error
        # The SDK already retried it, and the next request may be answered:
        # neither one to ask again nor a refusal
        assert type(exc_info.value) is LLMProviderError
        assert not isinstance(exc_info.value, (LLMTransientError, LLMRequestRefusedError))
        # No rejected key: the provider stays in use, with no fall-through
        assert openrouter.calls == 0
        assert router._rejected_providers == set()

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_providers_not_supporting_model_are_not_tried(self, use_async):
        anthropic = FailingLLMProvider(["claude-opus-4-7"], FakeAuthError())
        openai = FailingLLMProvider(["gpt-4o"], RuntimeError("must not be called"))
        router = self.create_router(openai=openai, anthropic=anthropic)

        with pytest.raises(LLMRequestRefusedError, match="The anthropic provider rejected"):
            await self.call(router, "claude-opus-4-7", use_async)

        assert openai.calls == 0

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_an_sdk_rate_limit_is_raised_as_the_domains_rate_limit(self, use_async):
        error = FakeAuthError(429)
        anthropic = FailingLLMProvider(["claude-opus-4-7"], error)
        openrouter = FailingLLMProvider(["claude-opus-4-7"], RuntimeError("must not be called"))
        router = self.create_router(anthropic=anthropic, openrouter=openrouter)

        with pytest.raises(LLMRateLimitError) as exc_info:
            await self.call(router, "claude-opus-4-7", use_async)

        assert str(exc_info.value) == "The anthropic provider's rate limit was exceeded"
        assert exc_info.value.__cause__ is error
        # A rate limit is no rejected key: the provider stays in use, with no fall-through
        assert openrouter.calls == 0
        assert router._rejected_providers == set()

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_an_sdk_unknown_model_is_raised_as_a_refusal(self, use_async):
        error = FakeAuthError(404)
        anthropic = FailingLLMProvider(["claude-opus-4-7"], error)
        router = self.create_router(anthropic=anthropic)

        with pytest.raises(LLMRequestRefusedError) as exc_info:
            await self.call(router, "claude-opus-4-7", use_async)

        assert str(exc_info.value) == "The anthropic provider has no model claude-opus-4-7"
        assert exc_info.value.__cause__ is error
        assert router._rejected_providers == set()

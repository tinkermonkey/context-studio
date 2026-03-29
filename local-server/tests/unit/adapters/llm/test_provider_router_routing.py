"""
Unit tests for LLMProviderRouter adapter.

Tests verify:
- Provider initialization with valid and invalid API keys
- Model routing to correct providers
- Model availability checking
- Union of available models from all providers
- API key format validation (OpenAI must start with 'sk-')
- Invalid OpenAI keys log warning but do not raise
"""

import sys
import os
import pytest
from unittest.mock import Mock, patch

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)

from adapters.llm.provider_router import LLMProviderRouter
from domain.extraction.ports import LLMResponse


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, available_models: list[str]):
        self._available_models = available_models

    def complete(self, system_prompt, user_prompt, model, temperature=0.0, max_tokens=2000, response_format=None, timeout=None):
        """Mock complete method."""
        return LLMResponse(
            content="mock response",
            tokens_in=10,
            tokens_out=20,
            finish_reason="stop",
            model=model,
        )

    def is_model_available(self, model: str) -> bool:
        """Check if model is available."""
        return model in self._available_models

    def list_available_models(self) -> list[str]:
        """List available models."""
        return self._available_models


class TestLLMProviderRouter:
    """Tests for LLMProviderRouter adapter."""

    def test_router_init_with_no_keys(self):
        """Router initializes with no keys and has no providers."""
        router = LLMProviderRouter()
        assert router.list_available_models() == []

    @patch("adapters.llm.provider_router.OpenAIProvider")
    def test_router_init_with_valid_openai_key(self, mock_openai_class):
        """Router initializes OpenAI provider with valid key starting with 'sk-'."""
        mock_provider = Mock()
        mock_openai_class.return_value = mock_provider

        router = LLMProviderRouter(openai_api_key="sk-test-key-123")

        # OpenAI provider should be initialized
        assert "openai" in router._providers
        mock_openai_class.assert_called_once_with("sk-test-key-123")

    @patch("adapters.llm.provider_router.logger")
    def test_router_init_with_invalid_openai_key_logs_warning(self, mock_logger):
        """Router logs warning for invalid OpenAI key (not starting with 'sk-')."""
        router = LLMProviderRouter(openai_api_key="invalid-key-123")

        # Should log warning, not raise
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "OpenAI API key format invalid" in warning_message

        # OpenAI provider should NOT be initialized
        assert "openai" not in router._providers

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
        router = LLMProviderRouter()

        assert router.is_model_available("gpt-4o") is False
        assert router.is_model_available("claude-opus-4-6") is False

    def test_router_list_available_models_with_no_providers(self):
        """list_available_models returns empty list when no providers are configured."""
        router = LLMProviderRouter()

        assert router.list_available_models() == []

    def test_router_routes_to_openai_provider(self):
        """Router routes OpenAI models to OpenAI provider."""
        router = LLMProviderRouter()
        openai_provider = MockLLMProvider(["gpt-4o", "gpt-3.5-turbo"])
        router._providers["openai"] = openai_provider

        provider = router._route_to_provider("gpt-4o")

        assert provider is openai_provider

    def test_router_routes_to_anthropic_provider(self):
        """Router routes Anthropic models to Anthropic provider."""
        router = LLMProviderRouter()
        anthropic_provider = MockLLMProvider(["claude-opus-4-6"])
        router._providers["anthropic"] = anthropic_provider

        provider = router._route_to_provider("claude-opus-4-6")

        assert provider is anthropic_provider

    def test_router_raises_for_unavailable_model(self):
        """Router raises ValueError when model is not available from any provider."""
        router = LLMProviderRouter()
        openai_provider = MockLLMProvider(["gpt-4o"])
        router._providers["openai"] = openai_provider

        with pytest.raises(ValueError) as exc_info:
            router._route_to_provider("claude-opus-4-6")

        assert "No provider available for model: claude-opus-4-6" in str(exc_info.value)

    def test_router_is_model_available_openai(self):
        """is_model_available returns True for OpenAI models."""
        router = LLMProviderRouter()
        openai_provider = MockLLMProvider(["gpt-4o", "gpt-3.5-turbo"])
        router._providers["openai"] = openai_provider

        assert router.is_model_available("gpt-4o") is True
        assert router.is_model_available("gpt-3.5-turbo") is True
        assert router.is_model_available("claude-opus-4-6") is False

    def test_router_is_model_available_anthropic(self):
        """is_model_available returns True for Anthropic models."""
        router = LLMProviderRouter()
        anthropic_provider = MockLLMProvider(["claude-opus-4-6", "claude-sonnet-4-6"])
        router._providers["anthropic"] = anthropic_provider

        assert router.is_model_available("claude-opus-4-6") is True
        assert router.is_model_available("claude-sonnet-4-6") is True
        assert router.is_model_available("gpt-4o") is False

    def test_router_list_available_models_single_provider(self):
        """list_available_models returns union when only one provider is configured."""
        router = LLMProviderRouter()
        openai_provider = MockLLMProvider(["gpt-4o", "gpt-3.5-turbo"])
        router._providers["openai"] = openai_provider

        models = router.list_available_models()

        assert sorted(models) == sorted(["gpt-4o", "gpt-3.5-turbo"])

    def test_router_list_available_models_multiple_providers(self):
        """list_available_models returns union of models from all providers."""
        router = LLMProviderRouter()
        openai_provider = MockLLMProvider(["gpt-4o", "gpt-3.5-turbo"])
        anthropic_provider = MockLLMProvider(["claude-opus-4-6", "claude-sonnet-4-6"])
        router._providers["openai"] = openai_provider
        router._providers["anthropic"] = anthropic_provider

        models = router.list_available_models()

        expected = ["gpt-4o", "gpt-3.5-turbo", "claude-opus-4-6", "claude-sonnet-4-6"]
        assert sorted(models) == sorted(expected)

    def test_router_complete_routes_to_correct_provider(self):
        """complete method routes to correct provider based on model."""
        router = LLMProviderRouter()
        openai_provider = MockLLMProvider(["gpt-4o"])
        openai_provider.complete = Mock(
            return_value=LLMResponse(
                content="OpenAI response",
                tokens_in=10,
                tokens_out=20,
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
        router = LLMProviderRouter()

        with pytest.raises(ValueError) as exc_info:
            router.complete(
                system_prompt="You are helpful",
                user_prompt="Hello",
                model="unknown-model",
            )

        assert "No provider available for model: unknown-model" in str(exc_info.value)

    def test_router_complete_with_all_parameters(self):
        """complete method passes all parameters to provider."""
        router = LLMProviderRouter()
        openai_provider = Mock()
        openai_provider.is_model_available.return_value = True
        expected_response = LLMResponse(
            content="response",
            tokens_in=10,
            tokens_out=20,
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
            response_format={"type": "json_object"},
        )

        openai_provider.complete.assert_called_once_with(
            system_prompt="System",
            user_prompt="User",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000,
            response_format={"type": "json_object"},
            timeout=None,
        )
        assert response is expected_response

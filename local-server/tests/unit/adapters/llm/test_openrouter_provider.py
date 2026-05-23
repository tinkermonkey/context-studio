"""
Unit tests for OpenRouter LLM provider adapter.

Tests verify:
- API key validation (requires config-based key, no env var fallback)
- Cache key generation with all parameters
- Cache hit/miss behavior
- LRU cache eviction
- Error handling (401, 404, 429 status codes)
- Timeout handling
- Model availability checking
- Response parsing and token counting
"""

from unittest.mock import Mock, patch

import httpx
import pytest

from adapters.llm.openrouter_provider import OpenRouterProvider
from domain.pipeline.exceptions import PipelineExternalServiceError
from domain.pipeline.ports import LLMResponse


@pytest.mark.llm
class TestOpenRouterProviderInit:
    """Tests for OpenRouter provider initialization."""

    def test_init_with_valid_api_key(self):
        """Provider initializes successfully with valid API key."""
        provider = OpenRouterProvider(api_key="test-api-key-123")
        assert provider._api_key == "test-api-key-123"
        assert provider._client is not None
        assert len(provider._response_cache) == 0

    def test_init_with_empty_api_key_raises_valueerror(self):
        """Provider raises ValueError when initialized with empty API key."""
        with pytest.raises(ValueError) as exc_info:
            OpenRouterProvider(api_key="")

        error_msg = str(exc_info.value)
        assert "OpenRouter API key not configured" in error_msg
        assert "config.json" in error_msg

    def test_init_requires_explicit_api_key(self):
        """Provider requires API key argument, does not read environment."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-api-key"}, clear=False):
            with pytest.raises(ValueError) as exc_info:
                OpenRouterProvider(api_key="")

            error_msg = str(exc_info.value)
            assert "OpenRouter API key not configured" in error_msg


@pytest.mark.llm
class TestOpenRouterCacheKey:
    """Tests for cache key generation."""

    @staticmethod
    def create_provider():
        """Create a provider for testing."""
        return OpenRouterProvider(api_key="test-key")

    def test_cache_key_includes_all_parameters(self):
        """Cache key includes all request parameters.

        Verifies: system_prompt, user_prompt, model, temperature, max_tokens,
        and response_format.
        """
        provider = self.create_provider()

        key1 = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="json",
        )

        assert ":" in key1
        parts = key1.split(":")
        assert len(parts) == 5
        assert parts[1] == "gpt-4"
        assert parts[2] == "0.7"
        assert parts[3] == "200"
        assert parts[4] == "json"

    def test_cache_key_differs_by_max_tokens(self):
        """Different max_tokens values produce different cache keys."""
        provider = self.create_provider()

        key_200 = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        key_500 = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=500,
            response_format="text",
        )

        assert key_200 != key_500
        assert "200" in key_200
        assert "500" in key_500

    def test_cache_key_differs_by_response_format(self):
        """Different response_format values produce different cache keys."""
        provider = self.create_provider()

        key_json = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="json",
        )

        key_text = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        assert key_json != key_text
        assert "json" in key_json
        assert "text" in key_text

    def test_cache_key_none_response_format(self):
        """Cache key with None response_format converts to 'text'."""
        provider = self.create_provider()

        key_none = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format=None,
        )

        key_text = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        assert key_none == key_text

    def test_cache_key_differs_by_prompt(self):
        """Different prompts produce different cache keys."""
        provider = self.create_provider()

        key1 = provider._make_cache_key(
            system_prompt="sys1",
            user_prompt="user1",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        key2 = provider._make_cache_key(
            system_prompt="sys2",
            user_prompt="user2",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        assert key1 != key2

    def test_cache_key_differs_by_model(self):
        """Different models produce different cache keys."""
        provider = self.create_provider()

        key_gpt = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        key_claude = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="claude-opus-4-7",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        assert key_gpt != key_claude

    def test_cache_key_differs_by_temperature(self):
        """Different temperature values produce different cache keys."""
        provider = self.create_provider()

        key_0 = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.0,
            max_tokens=200,
            response_format="text",
        )

        key_1 = provider._make_cache_key(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=1.0,
            max_tokens=200,
            response_format="text",
        )

        assert key_0 != key_1


@pytest.mark.llm
class TestOpenRouterCaching:
    """Tests for response caching behavior."""

    @staticmethod
    def create_provider_with_mock_client():
        """Create a provider with mocked HTTP client."""
        provider = OpenRouterProvider(api_key="test-key")
        provider._client = Mock(spec=httpx.Client)
        return provider

    def test_cache_hit_returns_cached_response(self):
        """Completing identical requests returns cached response."""
        provider = self.create_provider_with_mock_client()

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "cached response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        # First call should hit the API
        response1 = provider.complete(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        assert response1.content == "cached response"
        assert provider._client.post.call_count == 1

        # Second identical call should hit cache
        response2 = provider.complete(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        assert response2.content == "cached response"
        assert provider._client.post.call_count == 1  # No new API call

    def test_cache_miss_different_max_tokens(self):
        """Identical prompts with different max_tokens miss cache."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        # First call with max_tokens=200
        provider.complete(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        # Second call with max_tokens=500 (different)
        provider.complete(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=500,
            response_format="text",
        )

        assert provider._client.post.call_count == 2  # Both API calls made

    def test_cache_miss_different_response_format(self):
        """Identical prompts with different response_format miss cache."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        # First call with response_format="text"
        provider.complete(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        # Second call with response_format="json" (different)
        provider.complete(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="json",
        )

        assert provider._client.post.call_count == 2  # Both API calls made

    def test_lru_eviction_removes_oldest_entry(self):
        """Cache evicts oldest entry when max size is reached."""
        provider = self.create_provider_with_mock_client()
        provider.CACHE_MAX_SIZE = 3  # Small cache for testing

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        # Fill cache with 3 entries
        for i in range(3):
            provider.complete(
                system_prompt=f"sys{i}",
                user_prompt=f"user{i}",
                model="gpt-4",
                temperature=0.7,
                max_tokens=200,
                response_format="text",
            )

        assert len(provider._response_cache) == 3

        # Add 4th entry (should evict oldest)
        provider.complete(
            system_prompt="sys3",
            user_prompt="user3",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        assert len(provider._response_cache) == 3

    def test_lru_eviction_removes_least_recently_used(self):
        """Cache evicts least recently used entry."""
        provider = self.create_provider_with_mock_client()
        provider.CACHE_MAX_SIZE = 2

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        # Create key1 and key2
        key1 = provider._make_cache_key("sys1", "user1", "gpt-4", 0.7, 200, "text")
        key2 = provider._make_cache_key("sys2", "user2", "gpt-4", 0.7, 200, "text")

        # Add entries
        provider.complete(
            system_prompt="sys1",
            user_prompt="user1",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        provider.complete(
            system_prompt="sys2",
            user_prompt="user2",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        # Access key1 again (makes it most recently used)
        provider.complete(
            system_prompt="sys1",
            user_prompt="user1",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        # Add key3 (should evict key2, not key1)
        provider.complete(
            system_prompt="sys3",
            user_prompt="user3",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
            response_format="text",
        )

        assert key1 in provider._response_cache
        assert key2 not in provider._response_cache


@pytest.mark.llm
class TestOpenRouterCompletion:
    """Tests for completion requests and response parsing."""

    @staticmethod
    def create_provider_with_mock_client():
        """Create a provider with mocked HTTP client."""
        provider = OpenRouterProvider(api_key="test-key")
        provider._client = Mock(spec=httpx.Client)
        return provider

    def test_complete_successful_request(self):
        """Complete successfully processes API response."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Generated response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 15, "completion_tokens": 25},
        }
        provider._client.post.return_value = mock_response

        response = provider.complete(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="gpt-4",
            temperature=0.5,
            max_tokens=200,
        )

        assert isinstance(response, LLMResponse)
        assert response.content == "Generated response"
        assert response.tokens_in == 15
        assert response.tokens_out == 25
        assert response.model == "gpt-4"
        assert response.finish_reason == "stop"

    def test_complete_sends_correct_request_body(self):
        """Complete constructs correct request body."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        provider.complete(
            system_prompt="system",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=500,
            response_format="json",
            seed=42,
        )

        # Verify the POST call
        assert provider._client.post.call_count == 1
        call_args = provider._client.post.call_args

        # Check endpoint
        assert call_args[0][0] == "/chat/completions"

        # Check request body
        json_arg = call_args[1]["json"]
        assert json_arg["model"] == "gpt-4"
        assert json_arg["temperature"] == 0.7
        assert json_arg["max_tokens"] == 500
        assert json_arg["seed"] == 42
        assert json_arg["response_format"] == {"type": "json_object"}
        assert len(json_arg["messages"]) == 2
        assert json_arg["messages"][0]["role"] == "system"
        assert json_arg["messages"][1]["role"] == "user"

    def test_complete_without_seed(self):
        """Complete request without seed omits seed from body."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        provider.complete(
            system_prompt="system",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=500,
        )

        json_arg = provider._client.post.call_args[1]["json"]
        assert "seed" not in json_arg

    def test_complete_without_response_format(self):
        """Complete request without response_format omits it from body."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        provider.complete(
            system_prompt="system",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=500,
            response_format=None,
        )

        json_arg = provider._client.post.call_args[1]["json"]
        assert "response_format" not in json_arg


@pytest.mark.llm
class TestOpenRouterAsyncCompletion:
    """Tests for async completion requests."""

    @staticmethod
    def create_provider():
        """Create a provider for testing."""
        return OpenRouterProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_complete_async_returns_awaitable(self):
        """complete_async returns a coroutine that resolves to LLMResponse."""
        provider = self.create_provider()
        provider._client = Mock(spec=httpx.Client)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Async response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        # complete_async should be awaitable
        result = await provider.complete_async(
            system_prompt="You are helpful",
            user_prompt="What is 2+2?",
            model="gpt-4",
            temperature=0.5,
            max_tokens=200,
        )

        assert isinstance(result, LLMResponse)
        assert result.content == "Async response"
        assert result.tokens_in == 10
        assert result.tokens_out == 20

    @pytest.mark.asyncio
    async def test_complete_async_delegates_to_complete(self):
        """complete_async delegates to complete method."""
        provider = self.create_provider()
        provider._client = Mock(spec=httpx.Client)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        await provider.complete_async(
            system_prompt="system",
            user_prompt="user",
            model="gpt-4",
            temperature=0.5,
            max_tokens=200,
        )

        # Verify HTTP call was made via complete()
        assert provider._client.post.call_count == 1


@pytest.mark.llm
class TestOpenRouterErrorHandling:
    """Tests for error handling."""

    @staticmethod
    def create_provider_with_mock_client():
        """Create a provider with mocked HTTP client."""
        provider = OpenRouterProvider(api_key="test-key")
        provider._client = Mock(spec=httpx.Client)
        return provider

    def test_complete_handles_401_invalid_key(self):
        """Complete raises ValueError on 401 Unauthorized."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=Mock(), response=mock_response
        )
        provider._client.post.return_value = mock_response

        with pytest.raises(ValueError) as exc_info:
            provider.complete(
                system_prompt="sys",
                user_prompt="user",
                model="gpt-4",
            )

        assert "OpenRouter API key is invalid or unauthorized" in str(exc_info.value)

    def test_complete_handles_404_model_not_found(self):
        """Complete raises ValueError on 404 Model Not Found."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Model not found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=mock_response
        )
        provider._client.post.return_value = mock_response

        with pytest.raises(ValueError) as exc_info:
            provider.complete(
                system_prompt="sys",
                user_prompt="user",
                model="unknown-model",
            )

        assert "Model not found on OpenRouter" in str(exc_info.value)
        assert "unknown-model" in str(exc_info.value)

    def test_complete_handles_429_rate_limit(self):
        """Complete raises RuntimeError on 429 Rate Limited."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", request=Mock(), response=mock_response
        )
        provider._client.post.return_value = mock_response

        with pytest.raises(RuntimeError) as exc_info:
            provider.complete(
                system_prompt="sys",
                user_prompt="user",
                model="gpt-4",
            )

        assert "OpenRouter rate limit exceeded" in str(exc_info.value)

    def test_complete_handles_generic_http_error(self):
        """Complete raises RuntimeError on other HTTP errors."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error", request=Mock(), response=mock_response
        )
        provider._client.post.return_value = mock_response

        with pytest.raises(RuntimeError) as exc_info:
            provider.complete(
                system_prompt="sys",
                user_prompt="user",
                model="gpt-4",
            )

        assert "OpenRouter API error: 500" in str(exc_info.value)

    def test_complete_handles_timeout(self):
        """Complete wraps httpx.TimeoutException in PipelineExternalServiceError."""
        provider = self.create_provider_with_mock_client()

        provider._client.post.side_effect = httpx.TimeoutException("Request timeout")

        with pytest.raises(PipelineExternalServiceError) as exc_info:
            provider.complete(
                system_prompt="sys",
                user_prompt="user",
                model="gpt-4",
            )

        assert "TimeoutException" in str(exc_info.value)

    def test_complete_handles_unexpected_error(self):
        """Complete wraps unexpected errors in RuntimeError."""
        provider = self.create_provider_with_mock_client()

        provider._client.post.side_effect = ValueError("Unexpected error")

        with pytest.raises(RuntimeError) as exc_info:
            provider.complete(
                system_prompt="sys",
                user_prompt="user",
                model="gpt-4",
            )

        assert "ValueError: Unexpected error" in str(exc_info.value)


@pytest.mark.llm
class TestOpenRouterModelAvailability:
    """Tests for model availability checking."""

    @staticmethod
    def create_provider():
        """Create a provider for testing."""
        return OpenRouterProvider(api_key="test-key")

    def test_is_model_available_accepts_valid_model_identifiers(self):
        """is_model_available accepts identifiers matching the valid format regex."""
        provider = self.create_provider()

        assert provider.is_model_available("gpt-4") is True
        assert provider.is_model_available("claude-opus-4-7") is True
        assert provider.is_model_available("google/gemini-3-flash-preview") is True
        assert provider.is_model_available("custom-model") is True
        assert provider.is_model_available("x") is True
        assert provider.is_model_available("model_name") is True
        assert provider.is_model_available("model:v1") is True
        assert provider.is_model_available("model.name") is True

    def test_is_model_available_rejects_whitespace_only_strings(self):
        """is_model_available rejects strings that are only whitespace."""
        provider = self.create_provider()

        assert provider.is_model_available("   ") is False
        assert provider.is_model_available("\t") is False
        assert provider.is_model_available("\n") is False

    def test_is_model_available_rejects_invalid_special_characters(self):
        """is_model_available rejects strings with invalid special characters."""
        provider = self.create_provider()

        assert provider.is_model_available("model name") is False
        assert provider.is_model_available("model;rm -rf") is False
        assert provider.is_model_available("model@host") is False
        assert provider.is_model_available("model#tag") is False
        assert provider.is_model_available("model$var") is False

    def test_is_model_available_returns_false_for_empty_string(self):
        """is_model_available returns False for empty string."""
        provider = self.create_provider()

        assert provider.is_model_available("") is False

    def test_is_model_available_returns_false_for_non_string(self):
        """is_model_available returns False for non-string input."""
        provider = self.create_provider()

        assert provider.is_model_available(None) is False
        assert provider.is_model_available(123) is False
        assert provider.is_model_available([]) is False

    def test_list_available_models_returns_empty_list(self):
        """list_available_models returns empty list (OpenRouter has dynamic catalog)."""
        provider = self.create_provider()

        models = provider.list_available_models()

        assert models == []
        assert isinstance(models, list)


@pytest.mark.llm
class TestOpenRouterClearCache:
    """Tests for cache clearing."""

    @staticmethod
    def create_provider_with_mock_client():
        """Create a provider with mocked HTTP client."""
        provider = OpenRouterProvider(api_key="test-key")
        provider._client = Mock(spec=httpx.Client)
        return provider

    def test_clear_cache_removes_all_entries(self):
        """clear_cache removes all cached responses."""
        provider = self.create_provider_with_mock_client()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        provider._client.post.return_value = mock_response

        # Add entries to cache
        provider.complete(
            system_prompt="sys1",
            user_prompt="user1",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
        )

        provider.complete(
            system_prompt="sys2",
            user_prompt="user2",
            model="gpt-4",
            temperature=0.7,
            max_tokens=200,
        )

        assert len(provider._response_cache) == 2

        # Clear cache
        provider.clear_cache()

        assert len(provider._response_cache) == 0

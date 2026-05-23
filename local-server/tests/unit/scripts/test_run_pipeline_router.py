"""
Unit tests for run_pipeline router integration.

Tests verify:
- LLMProviderRouter is instantiated with correct API keys
- Error handling when no provider is configured
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import Mock, patch

from adapters.llm.provider_router import LLMProviderRouter


@pytest.mark.llm
class TestRunPipelineRouterIntegration:
    """Tests for router integration in run_pipeline script."""

    def test_router_instantiates_with_valid_api_keys(self):
        """LLMProviderRouter instantiates when at least one API key is provided."""
        router = LLMProviderRouter(
            openrouter_api_key="test-key",
            anthropic_api_key=None,
            openai_api_key=None,
        )

        assert router is not None

    def test_router_instantiates_with_multiple_api_keys(self):
        """LLMProviderRouter instantiates with multiple API keys."""
        router = LLMProviderRouter(
            openrouter_api_key="test-key-1",
            anthropic_api_key="test-key-2",
            openai_api_key="test-key-3",
        )

        assert router is not None

    def test_router_raises_when_no_api_keys_provided(self):
        """LLMProviderRouter raises ValueError when no API keys are provided."""
        with pytest.raises(ValueError):
            LLMProviderRouter(
                openrouter_api_key=None,
                anthropic_api_key=None,
                openai_api_key=None,
            )

    def test_router_raises_when_all_api_keys_empty(self):
        """LLMProviderRouter raises ValueError when all API keys are empty strings."""
        with pytest.raises(ValueError):
            LLMProviderRouter(
                openrouter_api_key="",
                anthropic_api_key="",
                openai_api_key="",
            )

"""
Minimal conftest for Phase 1 integration tests
Avoids loading full app dependencies
"""

import sys
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Set up mock environment BEFORE any imports
os.environ["OPENAI_API_KEY"] = "sk-test1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN"

# Add local-server to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Module-level patches to ensure they're active during all imports
_mock_provider_router = None
_provider_router_patcher = None


def _create_mock_provider_router():
    """Create a mock provider router with proper configuration"""
    mock_router = MagicMock()
    mock_router.get_enabled_models.return_value = ["gpt-3.5-turbo", "gpt-4"]

    # Import ProviderType for proper mocking
    from llm.enabled_models import ProviderType

    # Create a mock model config for validation
    mock_model_config = MagicMock()
    mock_model_config.provider_type = ProviderType.NATIVE_OPENAI
    mock_model_config.api_key_env_var = "OPENAI_API_KEY"

    mock_router.models_manager = MagicMock()
    mock_router.models_manager.get_model_config.return_value = mock_model_config

    # Mock LLM creation to avoid actual API calls
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test response"))

    async def mock_astream(*args, **kwargs):
        """Mock streaming response"""
        yield MagicMock(content="Test")
        yield MagicMock(content=" streaming")
        yield MagicMock(content=" response")

    mock_llm.astream = mock_astream
    mock_router.get_llm_for_model.return_value = mock_llm

    return mock_router


def pytest_configure(config):
    """
    Called before test collection starts.
    Set up global mocks that need to be active during module imports.
    """
    global _mock_provider_router, _provider_router_patcher

    # Create mock provider router
    _mock_provider_router = _create_mock_provider_router()

    # Patch the get_provider_router function before any LLM service imports
    _provider_router_patcher = patch('llm.service.get_provider_router', return_value=_mock_provider_router)
    _provider_router_patcher.start()


def pytest_unconfigure(config):
    """
    Called after all tests complete.
    Clean up global mocks.
    """
    global _provider_router_patcher

    if _provider_router_patcher:
        _provider_router_patcher.stop()

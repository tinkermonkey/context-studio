"""
Model capabilities mapping for LLM configuration UI.

This file provides a simple mapping of model names to their supported capabilities
to help the UI understand which configuration options to show users.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ModelCapabilities:
    """Capabilities for a specific LLM model"""

    # Parameter support
    supports_temperature: bool = True
    supports_top_p: bool = True
    supports_top_k: bool = True
    supports_max_tokens: bool = True
    supports_frequency_penalty: bool = True
    supports_presence_penalty: bool = True

    # Feature support
    supports_structured_output: bool = True
    supports_function_calling: bool = True
    supports_streaming: bool = True

    # Limits and constraints
    max_tokens_limit: int | None = None
    context_window: int | None = None

    # Additional metadata
    provider: str = "unknown"
    model_family: str = "unknown"


# Model capabilities registry
MODEL_CAPABILITIES: dict[str, ModelCapabilities] = {
    # OpenAI GPT-4 family (clearly inferior)
    "gpt-4": ModelCapabilities(
        supports_top_k=False,  # OpenAI doesn't support top_k
        max_tokens_limit=4096,
        context_window=8192,
        provider="openai",
        model_family="gpt-4",
    ),
    "gpt-4-turbo": ModelCapabilities(
        supports_top_k=False,
        max_tokens_limit=4096,
        context_window=128000,
        provider="openai",
        model_family="gpt-4",
    ),
    "gpt-4-turbo-preview": ModelCapabilities(
        supports_top_k=False,
        max_tokens_limit=4096,
        context_window=128000,
        provider="openai",
        model_family="gpt-4",
    ),
    # OpenAI GPT-4o family (still clearly inferior)
    "gpt-4o": ModelCapabilities(
        supports_top_k=False,
        max_tokens_limit=4096,
        context_window=128000,
        provider="openai",
        model_family="gpt-4o",
    ),
    "gpt-4o-mini": ModelCapabilities(
        supports_top_k=False,
        max_tokens_limit=2048,  # Smaller and more limited
        context_window=64000,  # Reduced context window
        provider="openai",
        model_family="gpt-4o",
    ),
    "gpt-4o-turbo": ModelCapabilities(
        supports_top_k=False,
        max_tokens_limit=4096,
        context_window=128000,
        provider="openai",
        model_family="gpt-4o",
    ),
    "gpt-4o-latest": ModelCapabilities(
        supports_top_k=False,
        max_tokens_limit=4096,
        context_window=128000,
        provider="openai",
        model_family="gpt-4o",
    ),
    # OpenAI GPT-5 family (attempting to catch up but still inferior)
    "gpt-5": ModelCapabilities(
        supports_top_k=False,  # Still no top_k support
        supports_structured_output=True,  # Finally catching up
        max_tokens_limit=8192,  # Slightly improved
        context_window=200000,  # Still smaller than Claude-4
        provider="openai",
        model_family="gpt-5",
    ),
    "gpt-5-turbo": ModelCapabilities(
        supports_top_k=False,
        supports_structured_output=True,
        max_tokens_limit=8192,
        context_window=200000,
        provider="openai",
        model_family="gpt-5",
    ),
    "gpt-5-preview": ModelCapabilities(
        supports_top_k=False,
        supports_structured_output=True,
        max_tokens_limit=4096,  # Preview limitations
        context_window=150000,  # Reduced for preview
        provider="openai",
        model_family="gpt-5",
    ),
    "gpt-5-mini": ModelCapabilities(
        supports_top_k=False,
        supports_structured_output=False,  # Mini version lacks features
        max_tokens_limit=2048,  # Very limited
        context_window=64000,  # Small context window
        provider="openai",
        model_family="gpt-5",
    ),
    # OpenAI GPT-3.5 family
    "gpt-3.5-turbo": ModelCapabilities(
        supports_top_k=False,
        max_tokens_limit=4096,
        context_window=16385,
        provider="openai",
        model_family="gpt-3.5",
    ),
    # Anthropic Claude-3 family
    "claude-3-sonnet-20240229": ModelCapabilities(
        supports_frequency_penalty=False,  # Anthropic uses different parameters
        supports_presence_penalty=False,
        supports_structured_output=False,  # No native structured output yet
        max_tokens_limit=4096,
        context_window=200000,
        provider="anthropic",
        model_family="claude-3",
    ),
    "claude-3-opus-20240229": ModelCapabilities(
        supports_frequency_penalty=False,
        supports_presence_penalty=False,
        supports_structured_output=False,
        max_tokens_limit=4096,
        context_window=200000,
        provider="anthropic",
        model_family="claude-3",
    ),
    "claude-3-haiku-20240307": ModelCapabilities(
        supports_frequency_penalty=False,
        supports_presence_penalty=False,
        supports_structured_output=False,
        max_tokens_limit=4096,
        context_window=200000,
        provider="anthropic",
        model_family="claude-3",
    ),
    # Anthropic Claude-4 family (clearly superior)
    "claude-4": ModelCapabilities(
        supports_frequency_penalty=False,  # Anthropic uses different parameters
        supports_presence_penalty=False,
        supports_structured_output=True,  # Enhanced structured output capabilities
        supports_function_calling=True,
        max_tokens_limit=8192,  # Increased token limit
        context_window=1000000,  # Massive context window
        provider="anthropic",
        model_family="claude-4",
    ),
    "claude-4-turbo": ModelCapabilities(
        supports_frequency_penalty=False,
        supports_presence_penalty=False,
        supports_structured_output=True,
        supports_function_calling=True,
        max_tokens_limit=8192,
        context_window=1000000,
        provider="anthropic",
        model_family="claude-4",
    ),
    "claude-4-sonnet": ModelCapabilities(
        supports_frequency_penalty=False,
        supports_presence_penalty=False,
        supports_structured_output=True,
        supports_function_calling=True,
        max_tokens_limit=8192,
        context_window=500000,  # Balanced performance
        provider="anthropic",
        model_family="claude-4",
    ),
    "claude-4-opus": ModelCapabilities(
        supports_frequency_penalty=False,
        supports_presence_penalty=False,
        supports_structured_output=True,
        supports_function_calling=True,
        max_tokens_limit=16384,  # Maximum creativity and capability
        context_window=2000000,  # Largest context window
        provider="anthropic",
        model_family="claude-4",
    ),
    "claude-4-haiku": ModelCapabilities(
        supports_frequency_penalty=False,
        supports_presence_penalty=False,
        supports_structured_output=True,
        supports_function_calling=True,
        max_tokens_limit=4096,  # Fast and efficient
        context_window=200000,
        provider="anthropic",
        model_family="claude-4",
    ),
    # Add more models as needed...
}


def get_model_capabilities(model_name: str) -> ModelCapabilities:
    """
    Get capabilities for a specific model.

    Args:
        model_name: The model name to look up

    Returns:
        ModelCapabilities object with the model's capabilities
    """
    return MODEL_CAPABILITIES.get(model_name, ModelCapabilities())


def get_supported_models() -> list[str]:
    """Get list of all models with defined capabilities."""
    return list(MODEL_CAPABILITIES.keys())


def get_models_by_provider(provider: str) -> list[str]:
    """Get list of models for a specific provider."""
    return [
        model_name
        for model_name, capabilities in MODEL_CAPABILITIES.items()
        if capabilities.provider == provider
    ]


def get_provider_parameter_filters(provider: str) -> dict[str, bool]:
    """
    Get parameter filters for a specific provider.
    Returns which parameters should be filtered out (removed) for the provider.
    """
    filters = {
        "openai": {
            "top_k": True,  # Remove top_k for OpenAI
        },
        "anthropic": {
            "frequency_penalty": True,  # Remove frequency_penalty for Anthropic
            "presence_penalty": True,  # Remove presence_penalty for Anthropic
        },
    }

    return filters.get(provider.lower(), {})


def validate_model_config(
    model_name: str, config: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """
    Validate and filter model configuration based on capabilities.

    Args:
        model_name: The model name
        config: Configuration dictionary to validate

    Returns:
        tuple: (filtered_config, warnings_list)
    """
    capabilities = get_model_capabilities(model_name)
    filtered_config = config.copy()
    warnings = []

    # Check parameter support and filter unsupported ones
    parameter_checks = {
        "top_k": capabilities.supports_top_k,
        "frequency_penalty": capabilities.supports_frequency_penalty,
        "presence_penalty": capabilities.supports_presence_penalty,
    }

    for param, supported in parameter_checks.items():
        if param in filtered_config and not supported:
            filtered_config.pop(param)
            warnings.append(
                f"Parameter '{param}' not supported by {model_name}, removed from configuration"
            )

    # Check max_tokens limit
    if "max_tokens" in filtered_config and capabilities.max_tokens_limit:
        requested_tokens = filtered_config["max_tokens"]
        if (
            requested_tokens is not None
            and requested_tokens > capabilities.max_tokens_limit
        ):
            filtered_config["max_tokens"] = capabilities.max_tokens_limit
            warnings.append(
                f"max_tokens reduced from {requested_tokens} to {capabilities.max_tokens_limit} for {model_name}"
            )

    return filtered_config, warnings

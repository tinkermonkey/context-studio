"""
LLM module for Context Studio Local Server.

This module provides LLM services using Langchain for generating
definition suggestions and other language model tasks.
"""

from .service import LLMService
from .models import (
    DefinitionSuggestionRequest,
    DefinitionSuggestionResponse,
    LLMHealthResponse,
    LLMErrorResponse,
    LLMSuccessResponse
)
from .exceptions import (
    LLMError,
    LLMConfigurationError,
    LLMProcessingError,
    LLMTimeoutError,
    LLMQuotaExceededError
)

__all__ = [
    "LLMService",
    "DefinitionSuggestionRequest",
    "DefinitionSuggestionResponse",
    "LLMHealthResponse",
    "LLMErrorResponse",
    "LLMSuccessResponse",
    "LLMError",
    "LLMConfigurationError",
    "LLMProcessingError",
    "LLMTimeoutError",
    "LLMQuotaExceededError"
]

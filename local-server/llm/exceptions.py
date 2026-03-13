"""
Custom exceptions for LLM-related errors.
"""


class LLMError(Exception):
    """Base exception for LLM-related errors"""

    pass


class LLMConfigurationError(LLMError):
    """Raised when LLM configuration is invalid or missing"""

    pass


class LLMProcessingError(LLMError):
    """Raised when LLM processing fails"""

    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out"""

    pass


class LLMQuotaExceededError(LLMError):
    """Raised when API quota is exceeded"""

    pass


class FlavorNotFoundError(LLMError):
    """Raised when a requested flavor is not found"""

    pass


class FlavorValidationError(LLMError):
    """Raised when flavor validation fails"""

    pass

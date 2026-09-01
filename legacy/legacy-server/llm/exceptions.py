"""
Custom exceptions for LLM-related errors.
"""


class LLMError(Exception):
    """Base exception for LLM-related errors"""



class LLMConfigurationError(LLMError):
    """Raised when LLM configuration is invalid or missing"""



class LLMProcessingError(LLMError):
    """Raised when LLM processing fails"""



class LLMTimeoutError(LLMError):
    """Raised when LLM request times out"""



class LLMQuotaExceededError(LLMError):
    """Raised when API quota is exceeded"""



class FlavorNotFoundError(LLMError):
    """Raised when a requested flavor is not found"""



class FlavorValidationError(LLMError):
    """Raised when flavor validation fails"""


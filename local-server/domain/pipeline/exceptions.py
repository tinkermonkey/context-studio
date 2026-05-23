"""
Exceptions for the LLM Pipeline Management domain context.
"""


class PipelineError(Exception):
    """Base exception for pipeline domain errors."""

    pass


class PipelineNotFoundError(PipelineError):
    """Raised when a pipeline configuration is not found."""

    pass


class LayerExecutionError(PipelineError):
    """Raised when a pipeline layer execution fails."""

    pass


class PipelineStorageError(PipelineError):
    """Raised when a database operation for pipeline runs fails."""

    pass


class PipelineInputError(PipelineError):
    """Raised for invalid or malformed input (maps to HTTP 400)."""

    pass


class PipelineExternalServiceError(PipelineError):
    """Raised for external service failures like timeouts (maps to HTTP 503)."""

    pass


class PipelineExecutionError(PipelineError):
    """Raised for internal orchestrator logic failures (maps to HTTP 500)."""

    pass

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
    """Raised when pipeline input is invalid or malformed."""

    pass


class PipelineExternalServiceError(PipelineError):
    """Raised when an external service fails (timeouts, connection errors)."""

    pass


class PipelineExecutionError(PipelineError):
    """Raised when internal orchestrator logic fails unexpectedly."""

    pass

"""
Exception classes for the Pipeline Management domain.

These exceptions represent domain-specific errors that may occur
during pipeline operations.
"""


class PipelineError(Exception):
    """Base exception for all pipeline domain errors."""

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

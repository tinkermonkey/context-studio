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


class ApplySelectionError(PipelineInputError):
    """Raised when an apply request's explicit selections do not match the run.

    For example: an accepted candidate id the run does not contain, a recognition
    decision for a mention the run never extracted, or a merge target individual
    that does not exist.
    """

    pass


class PipelineExternalServiceError(PipelineError):
    """Raised when an external service fails (timeouts, connection errors)."""

    pass


class PipelineExecutionError(PipelineError):
    """Raised when internal orchestrator logic fails unexpectedly."""

    pass

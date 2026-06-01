"""
Exceptions for the Pipeline Management bounded context.
"""


class PipelineStorageError(Exception):
    """Raised when a database operation for pipeline runs fails."""

    pass


class PipelineInputError(Exception):
    """Raised when pipeline input is invalid or malformed."""

    pass


class PipelineExternalServiceError(Exception):
    """Raised when an external service fails (timeouts, connection errors)."""

    pass


class PipelineExecutionError(Exception):
    """Raised when internal orchestrator logic fails unexpectedly."""

    pass

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
    """
    Raised when internal orchestrator logic fails unexpectedly.

    llm_metadata carries what the run's model calls cost before it failed,
    so the failed run still records it.
    """

    def __init__(self, message: str = "", llm_metadata: dict | None = None) -> None:
        super().__init__(message)
        self.llm_metadata = llm_metadata


class ExtractionFailedError(PipelineExecutionError):
    """
    Raised when a run's extraction failed for a reason its caller is told: for
    one, an LLM response that stayed incomplete. The message is that reason.
    """

    pass

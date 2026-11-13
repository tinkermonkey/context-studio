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


class LLMProviderError(PipelineExternalServiceError):
    """
    Raised by an LLMProvider that could not answer a request, where it knows
    what kind of failure it met. The message is written for the run's caller:
    it names the provider and the kind of failure, and quotes neither a
    response body nor the text of a client library's error (which may hold
    anything, the API key included).

    Raised as itself, it is a failure that is neither worth asking again (the
    provider's client already retried it, or a retry cannot change it) nor one
    every other request will meet.
    """

    pass


class LLMTransientError(LLMProviderError):
    """
    The same request may be answered if it is made again: a server error, a
    timeout, a connection that failed, an error returned in place of a
    completion.
    """

    pass


class LLMRateLimitError(LLMTransientError):
    """
    The provider's rate limit turned the request away. It may be answered
    after a wait; while the limit holds, every request for the model is turned
    away, whatever it asks.
    """

    pass


class LLMRequestRefusedError(LLMProviderError):
    """
    The provider will not answer this request however often it is made, nor
    any other request for the model: it rejected the API key, has no such
    model, or the account is out of credit.
    """

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
    Raised when a run's extraction failed because an LLM response stayed
    incomplete or the LLM provider did not answer. The message is that reason,
    written for the run's caller.
    """

    pass

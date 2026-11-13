"""
Exceptions for the Knowledge Extraction domain context.
"""


class ExtractionError(Exception):
    """Base exception for extraction domain errors."""

    pass


class LayerExecutionError(ExtractionError):
    """Raised when an extraction layer fails to execute."""

    pass


class InvalidInputError(ExtractionError):
    """Raised when extraction input is invalid or malformed."""

    pass


class NLPProcessorNotReadyError(ExtractionError):
    """Raised when NLP processor is not available or not initialized."""

    pass


class IncompleteLLMResponseError(ExtractionError):
    """
    Raised when an LLM response is not the model's whole answer: it stopped
    early (provider error or output limit) or its content is not the JSON
    that was asked for.
    """

    pass


class SourceFailedError(ExtractionError):
    """
    Raised by a SourceReader or PageFetcher when a source can't be read or
    fetched; the source is stored as failed with this failure and detail.

    Attributes:
        failure: A SourceFailure value (too_large, unsupported_type, no_text, fetch_failed)
        detail: A sentence saying more
    """

    def __init__(self, failure: str, detail: str) -> None:
        self.failure = failure
        self.detail = detail
        super().__init__(f"{failure}: {detail}")


class SourceNotReadyError(ExtractionError):
    """Raised when a source's text is asked for while it is fetching or failed."""

    def __init__(self, source_id: str, status: str) -> None:
        self.source_id = source_id
        self.status = status
        super().__init__(f"Source {source_id} is {status}, so it has no text")

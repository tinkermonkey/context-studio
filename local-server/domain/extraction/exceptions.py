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

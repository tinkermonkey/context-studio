"""
Exceptions for the Knowledge Extraction domain context.
"""


class ExtractionError(Exception):
    """Base exception for extraction domain errors."""
    pass


class NoLayerSucceededError(ExtractionError):
    """Raised when all extraction layers fail."""
    pass

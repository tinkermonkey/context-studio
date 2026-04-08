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


class InvalidInputError(PipelineError):
    """Raised when pipeline input validation fails in domain logic."""
    pass

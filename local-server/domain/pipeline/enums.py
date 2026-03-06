"""
Domain value enums for the pipeline bounded context.

Enums represent domain concepts in the pipeline bounded context.
They are immutable and framework-free, depending only on Python stdlib.
"""

from enum import Enum


class PipelineType(str, Enum):
    """
    Enumeration of pipeline types.

    Attributes:
        EXTRACTION: Pipeline for entity/relationship extraction
        CLASSIFICATION: Pipeline for text classification
        SUMMARIZATION: Pipeline for text summarization
        TRANSLATION: Pipeline for text translation
        CUSTOM: Custom pipeline type
    """

    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    CUSTOM = "custom"


class ExecutionStatus(str, Enum):
    """
    Enumeration of execution statuses.

    Attributes:
        PENDING: Execution has been created but not yet started
        RUNNING: Execution is currently in progress
        COMPLETED: Execution completed successfully
        FAILED: Execution failed with an error
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineFlavorExecutionStatus(str, Enum):
    """
    Enumeration of pipeline flavor execution statuses.

    Attributes:
        PENDING: Execution queued and waiting to run
        SUCCESS: Execution completed successfully
        ERROR: Execution failed with an error
        TIMEOUT: Execution exceeded maximum time limit
    """

    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"

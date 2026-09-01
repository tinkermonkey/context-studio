"""Pipeline management module."""

from pipeline.manager import (
    OperationsDatabaseManager,
    # Backward compatibility
    PipelineDatabaseManager,
    get_operations_database_manager,
    get_pipeline_database_manager,
    get_pipeline_engine,
    get_pipeline_session,
)

from .models import Base, LLMPipeline

__all__ = [
    "Base",
    "LLMPipeline",
    "OperationsDatabaseManager",
    # Backward compatibility
    "PipelineDatabaseManager",
    "get_operations_database_manager",
    "get_pipeline_database_manager",
    "get_pipeline_engine",
    "get_pipeline_session",
]

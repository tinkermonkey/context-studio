"""Pipeline management module."""

from pipeline.manager import (
    OperationsDatabaseManager,
    get_operations_database_manager,
    # Backward compatibility
    PipelineDatabaseManager,
    get_pipeline_database_manager,
    get_pipeline_session,
    get_pipeline_engine
)

__all__ = [
    'OperationsDatabaseManager',
    'get_operations_database_manager',
    # Backward compatibility
    'PipelineDatabaseManager',
    'get_pipeline_database_manager',
    'get_pipeline_session',
    'get_pipeline_engine'
]

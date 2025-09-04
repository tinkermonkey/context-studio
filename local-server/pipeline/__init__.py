"""
Pipeline module for managing pipeline configurations independently of datasets.
"""

from .manager import (
    PipelineDatabaseManager,
    get_pipeline_database_manager,
    get_pipeline_session,
    get_pipeline_engine
)

__all__ = [
    'PipelineDatabaseManager',
    'get_pipeline_database_manager', 
    'get_pipeline_session',
    'get_pipeline_engine'
]

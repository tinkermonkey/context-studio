"""
Dependency injection for RAG Pipeline services

This module provides dependency injection for RAG-related services
following the established pattern in the codebase.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from database.utils import get_db
from pipeline.manager import get_pipeline_database_manager
from rag.rag_pipeline_service import RAGPipelineService
from rag.observability_store import RAGObservabilityStore


def get_operations_db() -> Session:
    """
    Get database session for operations database (operations.db).

    This database handles pipeline flavors, executions, and observability data.

    Returns:
        Database session for operations.db
    """
    db_manager = get_pipeline_database_manager()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_rag_pipeline_service(
    kg_db: Session = Depends(get_db),
    ops_db: Session = Depends(get_operations_db)
) -> RAGPipelineService:
    """
    Dependency injection for RAGPipelineService.

    Args:
        kg_db: Database session for knowledge graph (local.db)
        ops_db: Database session for operations/observability (operations.db)

    Returns:
        RAGPipelineService instance configured with database sessions
    """
    return RAGPipelineService(
        kg_db_session=kg_db,
        ops_db_session=ops_db
    )


def get_rag_observability_store(
    ops_db: Session = Depends(get_operations_db)
) -> RAGObservabilityStore:
    """
    Dependency injection for RAGObservabilityStore.

    Args:
        ops_db: Database session for operations/observability (operations.db)

    Returns:
        RAGObservabilityStore instance configured with operations database session
    """
    return RAGObservabilityStore(db_session=ops_db)

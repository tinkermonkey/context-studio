# mypy: ignore-errors
"""
Dependency injection for RAG Pipeline services

This module provides dependency injection for RAG-related services
following the established pattern in the codebase.
"""

from database.utils import get_db
from fastapi import Depends
from pipeline.manager import get_pipeline_database_manager
from rag.observability_store import RAGObservabilityStore
from rag.rag_pipeline_service import RAGPipelineService
from sqlalchemy.orm import Session


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
    kg_db: Session = Depends(get_db), ops_db: Session = Depends(get_operations_db)
) -> RAGPipelineService:
    """
    Dependency injection for RAGPipelineService.

    Args:
        kg_db: Database session for knowledge graph (local.db)
        ops_db: Database session for operations/observability (operations.db)

    Returns:
        RAGPipelineService instance configured with database sessions and timeout settings  # noqa: E501
    """
    from config import get_settings

    settings = get_settings()

    # Get configuration from RAG pipeline settings
    llm_flavor_id = settings.rag_pipeline.llm_pipeline_flavor or "default"
    kg_top_k = settings.rag_pipeline.kg_context_top_k
    kg_vector_threshold = settings.rag_pipeline.kg_vector_threshold
    dedup_threshold = settings.rag_pipeline.deduplication_threshold

    # Get timeout settings from config
    timeout_layer_0 = settings.rag_pipeline.timeout_layer_0
    timeout_layer_1 = settings.rag_pipeline.timeout_layer_1
    timeout_layer_2 = settings.rag_pipeline.timeout_layer_2
    timeout_layer_3 = settings.rag_pipeline.timeout_layer_3

    return RAGPipelineService(
        kg_db_session=kg_db,
        ops_db_session=ops_db,
        llm_flavor_id=llm_flavor_id,
        kg_top_k=kg_top_k,
        kg_vector_threshold=kg_vector_threshold,
        dedup_similarity_threshold=dedup_threshold,
        timeout_layer_0=timeout_layer_0,
        timeout_layer_1=timeout_layer_1,
        timeout_layer_2=timeout_layer_2,
        timeout_layer_3=timeout_layer_3,
    )


def get_rag_observability_store(
    ops_db: Session = Depends(get_operations_db),
) -> RAGObservabilityStore:
    """
    Dependency injection for RAGObservabilityStore.

    Args:
        ops_db: Database session for operations/observability (operations.db)

    Returns:
        RAGObservabilityStore instance configured with operations database session  # noqa: E501
    """
    return RAGObservabilityStore(db_session=ops_db)

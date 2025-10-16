"""
Integration tests for RAG Pipeline with real processors.

These tests use real processor implementations with test databases.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
import tempfile
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from rag.rag_pipeline_service import RAGPipelineService
from database.models import Base, StructureNode
from database.custom_types import NodeType
import numpy as np


@pytest.fixture
def test_kg_db():
    """Create a temporary test database for knowledge graph."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    # Add some test structure nodes with embeddings
    session = SessionLocal()
    try:
        # Create embedding model to generate test embeddings
        from embeddings.generate_embeddings import get_model
        model = get_model()

        # Add test terms with embeddings
        terms_data = [
            ("Machine Learning", "A field of artificial intelligence focused on algorithms that learn from data"),
            ("Neural Networks", "Computing systems inspired by biological neural networks"),
            ("Deep Learning", "A subset of machine learning using multi-layered neural networks"),
            ("Artificial Intelligence", "The simulation of human intelligence by machines"),
        ]

        for title, definition in terms_data:
            # Generate embedding
            embedding = model.encode([title])[0]
            embedding_blob = np.array(embedding, dtype=np.float32).tobytes()

            node = StructureNode(
                node_type=NodeType.TERM,
                title=title,
                definition=definition,
                title_embedding=embedding_blob,
                parent_node_id=None
            )
            session.add(node)

        session.commit()
    finally:
        session.close()

    yield engine, SessionLocal

    # Cleanup
    engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def test_ops_db():
    """Create a temporary test database for operations/observability."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine)

    # Create observability tables
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_processing_metrics (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                sentence_text TEXT NOT NULL,
                layer_0_time_ms INTEGER,
                layer_0_count INTEGER,
                layer_1_time_ms INTEGER,
                layer_1_count INTEGER,
                layer_2_time_ms INTEGER,
                layer_2_count INTEGER,
                layer_3_time_ms INTEGER,
                layer_3_count INTEGER,
                total_time_ms INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                retention_days INTEGER DEFAULT 30 NOT NULL
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_observability_trace (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                sentence_index INTEGER NOT NULL,
                layer_name TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                trace_data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                retention_days INTEGER DEFAULT 7 NOT NULL
            )
        """))
        conn.commit()

    yield engine, SessionLocal

    # Cleanup
    engine.dispose()
    os.unlink(db_path)


class TestRAGPipelineIntegration:
    """Integration tests for RAG Pipeline Service with real processors."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_real_processors(self, test_kg_db, test_ops_db):
        """Test full RAG pipeline with real processor implementations."""
        kg_engine, kg_session_maker = test_kg_db
        ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            # Create service with real processors (use longer timeouts for test environment)
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=10,
                timeout_layer_0=2.0,  # 2s for test environment
                timeout_layer_2=2.0   # 2s for test environment
            )

            # Test text mentioning concepts in KG
            input_text = "Machine learning and neural networks are key technologies in artificial intelligence."

            # Execute extraction
            response = await service.extract_entities(input_text, enable_trace=False)

            # Assertions
            assert response.request_id is not None
            assert len(response.entities) > 0  # Should extract at least some entities

            # Check metrics
            assert response.metrics.total_execution_time_ms > 0
            assert response.metrics.kg_layer.execution_time_ms > 0
            assert response.metrics.total_sentences >= 1

            # Verify entities contain expected concepts
            entity_texts = [e.text.lower() for e in response.entities]
            assert any("machine learning" in t.lower() for t in entity_texts)

            # Verify metrics were saved to database
            result = ops_session.execute(text(
                "SELECT COUNT(*) FROM rag_processing_metrics WHERE request_id = :request_id"
            ), {"request_id": response.request_id}).scalar()
            assert result == 1

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_pipeline_with_trace_enabled(self, test_kg_db, test_ops_db):
        """Test that trace data is captured and saved when enabled."""
        kg_engine, kg_session_maker = test_kg_db
        ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            # Create service with longer timeouts for test environment
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=10,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0
            )

            input_text = "Neural networks enable deep learning applications."

            # Execute with trace enabled
            response = await service.extract_entities(input_text, enable_trace=True)

            # Check trace availability
            assert response.trace_available is True

            # Verify trace records were saved
            result = ops_session.execute(text(
                "SELECT COUNT(*) FROM rag_observability_trace WHERE request_id = :request_id"
            ), {"request_id": response.request_id}).scalar()
            assert result > 0  # Should have trace records

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_pipeline_with_unknown_concepts(self, test_kg_db, test_ops_db):
        """Test pipeline behavior with concepts not in knowledge graph."""
        kg_engine, kg_session_maker = test_kg_db
        ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            # Create service with longer timeouts for test environment
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=10,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0
            )

            # Text with concepts not in KG
            input_text = "Quantum computing and blockchain technology are emerging fields."

            # Execute extraction
            response = await service.extract_entities(input_text, enable_trace=False)

            # Should still complete successfully
            assert response.request_id is not None
            assert response.metrics.total_execution_time_ms > 0

            # May have fewer entities or entities from gap detection/web search
            # This tests graceful handling of unknown concepts

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_empty_text_handling(self, test_kg_db, test_ops_db):
        """Test pipeline handling of empty or minimal text."""
        kg_engine, kg_session_maker = test_kg_db
        ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            # Create service with longer timeouts for test environment
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=10,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0
            )

            # Very short text
            input_text = "AI."

            response = await service.extract_entities(input_text, enable_trace=False)

            # Should complete without errors
            assert response.request_id is not None
            assert response.metrics.total_execution_time_ms > 0
            # May have zero entities, which is acceptable

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_multiple_sentences(self, test_kg_db, test_ops_db):
        """Test pipeline with multiple sentences."""
        kg_engine, kg_session_maker = test_kg_db
        ops_engine, ops_session_maker = test_ops_db

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            # Create service with longer timeouts for test environment
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                kg_top_k=10,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0
            )

            # Multi-sentence text
            input_text = (
                "Machine learning is a subset of artificial intelligence. "
                "Neural networks are used for deep learning. "
                "These technologies are transforming many industries."
            )

            response = await service.extract_entities(input_text, enable_trace=False)

            # Should process multiple sentences
            assert response.metrics.total_sentences >= 3
            assert len(response.entities) > 0

        finally:
            kg_session.close()
            ops_session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

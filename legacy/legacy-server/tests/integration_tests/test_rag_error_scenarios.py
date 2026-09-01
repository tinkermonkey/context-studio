"""
Error scenario integration tests for RAG Pipeline.

These tests verify graceful degradation, error handling, and timeout enforcement.  # noqa: E501
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import tempfile
from unittest.mock import Mock, patch

import pytest
from database.models import Base
from rag.processors.models import (
    ConceptResolutionOutput,
    KGContextOutput,
    LLMExtractionOutput,
    SpaCyGapOutput,
)
from rag.rag_pipeline_service import RAGPipelineService
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_dbs():
    """Create temporary test databases."""
    # KG database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        kg_db_path = f.name

    kg_engine = create_engine(f"sqlite:///{kg_db_path}")
    Base.metadata.create_all(kg_engine)
    KGSessionLocal = sessionmaker(bind=kg_engine)

    # Operations database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        ops_db_path = f.name

    ops_engine = create_engine(f"sqlite:///{ops_db_path}")
    OpsSessionLocal = sessionmaker(bind=ops_engine)

    # Create observability tables
    with ops_engine.connect() as conn:
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

    yield (kg_engine, KGSessionLocal), (ops_engine, OpsSessionLocal)

    # Cleanup
    kg_engine.dispose()
    ops_engine.dispose()
    os.unlink(kg_db_path)
    os.unlink(ops_db_path)


class TestRAGErrorScenarios:
    """Error scenario tests for RAG Pipeline."""

    @pytest.mark.asyncio
    async def test_all_layers_timeout(self, test_dbs):
        """Test pipeline completes when all layers timeout."""
        (_kg_engine, kg_session_maker), (_ops_engine, ops_session_maker) = (
            test_dbs
        )

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            with patch("rag.rag_pipeline_service.KGContextProcessor") as MockKG, patch(
                "rag.rag_pipeline_service.LLMExtractionProcessor"
            ) as MockLLM, patch(
                "rag.rag_pipeline_service.SpaCyGapProcessor"
            ) as MockSpaCy, patch(
                "rag.rag_pipeline_service.ConceptResolutionProcessor"
            ) as MockConcept, patch(
                "rag.rag_pipeline_service.RAGObservabilityStore"
            ) as MockObs:

                # Make all processors timeout
                async def timeout():
                    await asyncio.sleep(100)
                    return Mock()

                MockKG.return_value.process.side_effect = timeout
                MockLLM.return_value.process.side_effect = timeout
                MockSpaCy.return_value.process.side_effect = timeout
                MockConcept.return_value.process.side_effect = timeout

                MockObs.return_value.save_metrics.return_value = "metrics123"

                service = RAGPipelineService(
                    kg_db_session=kg_session,
                    ops_db_session=ops_session,
                    timeout_layer_0=0.1,
                    timeout_layer_1=0.1,
                    timeout_layer_2=0.1,
                    timeout_layer_3=0.1,
                )

                response = await service.extract_entities(
                    "Test text", enable_trace=False
                )

                # Pipeline should complete with no entities
                assert response.request_id is not None
                assert len(response.entities) == 0
                assert response.metrics.total_execution_time_ms > 0

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_layer_0_exception_graceful_degradation(self, test_dbs):
        """Test that Layer 0 exception allows pipeline to continue."""
        (_kg_engine, kg_session_maker), (_ops_engine, ops_session_maker) = (
            test_dbs
        )

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            with patch("rag.rag_pipeline_service.KGContextProcessor") as MockKG, patch(
                "rag.rag_pipeline_service.LLMExtractionProcessor"
            ) as MockLLM, patch(
                "rag.rag_pipeline_service.SpaCyGapProcessor"
            ) as MockSpaCy, patch(
                "rag.rag_pipeline_service.ConceptResolutionProcessor"
            ) as MockConcept, patch(
                "rag.rag_pipeline_service.RAGObservabilityStore"
            ) as MockObs:

                # Layer 0 raises exception
                MockKG.return_value.process.side_effect = Exception(
                    "Layer 0 error"
                )

                # Other layers succeed with empty results
                MockLLM.return_value.process.return_value = (
                    LLMExtractionOutput(
                        entities=[],
                        kg_context_size=0,
                        token_usage=None,
                        trace_data={},
                    )
                )
                MockSpaCy.return_value.process.return_value = SpaCyGapOutput(
                    gaps=[],
                    total_noun_phrases=0,
                    filtered_count=0,
                    trace_data={},
                )
                MockConcept.return_value.process.return_value = (
                    ConceptResolutionOutput(
                        resolved_concepts=[],
                        unresolved_gaps=[],
                        web_searches_performed=0,
                        cached_kg_hits=0,
                        full_kg_hits=0,
                        trace_data={},
                    )
                )

                MockObs.return_value.save_metrics.return_value = "metrics123"

                service = RAGPipelineService(
                    kg_db_session=kg_session, ops_db_session=ops_session
                )

                response = await service.extract_entities(
                    "Test text", enable_trace=False
                )

                # Should complete successfully despite Layer 0 error
                assert response.request_id is not None
                assert response.metrics.kg_layer.entities_found == 0

                # Verify other layers were called
                MockLLM.return_value.process.assert_called_once()
                MockSpaCy.return_value.process.assert_called_once()

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_layer_1_llm_service_unavailable(self, test_dbs):
        """Test handling of LLM service unavailability."""
        (_kg_engine, kg_session_maker), (_ops_engine, ops_session_maker) = (
            test_dbs
        )

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            with patch("rag.rag_pipeline_service.KGContextProcessor") as MockKG, patch(
                "rag.rag_pipeline_service.LLMExtractionProcessor"
            ) as MockLLM, patch(
                "rag.rag_pipeline_service.SpaCyGapProcessor"
            ) as MockSpaCy, patch(
                "rag.rag_pipeline_service.ConceptResolutionProcessor"
            ) as MockConcept, patch(
                "rag.rag_pipeline_service.RAGObservabilityStore"
            ) as MockObs:

                MockKG.return_value.process.return_value = KGContextOutput(
                    extracted_phrases=[],
                    kg_nodes=[],
                    total_sentences=1,
                    trace_data={},
                )

                # LLM service raises exception (e.g., API unavailable)
                MockLLM.return_value.process.side_effect = ConnectionError(
                    "LLM API unavailable"
                )

                MockSpaCy.return_value.process.return_value = SpaCyGapOutput(
                    gaps=[],
                    total_noun_phrases=0,
                    filtered_count=0,
                    trace_data={},
                )
                MockConcept.return_value.process.return_value = (
                    ConceptResolutionOutput(
                        resolved_concepts=[],
                        unresolved_gaps=[],
                        web_searches_performed=0,
                        cached_kg_hits=0,
                        full_kg_hits=0,
                        trace_data={},
                    )
                )

                MockObs.return_value.save_metrics.return_value = "metrics123"

                service = RAGPipelineService(
                    kg_db_session=kg_session, ops_db_session=ops_session
                )

                response = await service.extract_entities(
                    "Test text", enable_trace=False
                )

                # Should continue to other layers
                assert response.request_id is not None
                assert response.metrics.llm_layer.entities_found == 0

                # Verify subsequent layers were still called
                MockSpaCy.return_value.process.assert_called_once()
                MockConcept.return_value.process.assert_called_once()

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_layer_3_web_search_unavailable(self, test_dbs):
        """Test handling when web search service is unavailable."""
        (_kg_engine, kg_session_maker), (_ops_engine, ops_session_maker) = (
            test_dbs
        )

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            with patch("rag.rag_pipeline_service.KGContextProcessor") as MockKG, patch(
                "rag.rag_pipeline_service.LLMExtractionProcessor"
            ) as MockLLM, patch(
                "rag.rag_pipeline_service.SpaCyGapProcessor"
            ) as MockSpaCy, patch(
                "rag.rag_pipeline_service.ConceptResolutionProcessor"
            ) as MockConcept, patch(
                "rag.rag_pipeline_service.RAGObservabilityStore"
            ) as MockObs:

                MockKG.return_value.process.return_value = KGContextOutput(
                    extracted_phrases=[],
                    kg_nodes=[],
                    total_sentences=1,
                    trace_data={},
                )
                MockLLM.return_value.process.return_value = (
                    LLMExtractionOutput(
                        entities=[],
                        kg_context_size=0,
                        token_usage=None,
                        trace_data={},
                    )
                )
                MockSpaCy.return_value.process.return_value = SpaCyGapOutput(
                    gaps=[],
                    total_noun_phrases=0,
                    filtered_count=0,
                    trace_data={},
                )

                # Layer 3 handles web search unavailability gracefully
                MockConcept.return_value.process.return_value = (
                    ConceptResolutionOutput(
                        resolved_concepts=[],
                        unresolved_gaps=[],
                        web_searches_performed=0,
                        cached_kg_hits=0,
                        full_kg_hits=0,
                        trace_data={},
                    )
                )

                MockObs.return_value.save_metrics.return_value = "metrics123"

                service = RAGPipelineService(
                    kg_db_session=kg_session, ops_db_session=ops_session
                )

                response = await service.extract_entities(
                    "Test text", enable_trace=False
                )

                # Should complete successfully
                assert response.request_id is not None
                assert response.metrics.web_layer.entities_found == 0

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_malformed_input_special_characters(self, test_dbs):
        """Test handling of malformed input with special characters."""
        (_kg_engine, kg_session_maker), (_ops_engine, ops_session_maker) = (
            test_dbs
        )

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0,
            )

            # Test with various special characters
            special_inputs = [
                "Test\x00with\x00null\x00bytes",
                "Test with emoji 🔥 💡 🚀",
                "Test with unicode \u2022 \u2026 \u00a9",
                "Test with RTL text עברית",
                "Test with Chinese characters 中文测试",
            ]

            for input_text in special_inputs:
                response = await service.extract_entities(
                    input_text, enable_trace=False
                )

                # Should handle without crashing
                assert response.request_id is not None
                assert response.metrics.total_execution_time_ms > 0

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_very_long_input(self, test_dbs):
        """Test handling of very long input text."""
        (_kg_engine, kg_session_maker), (_ops_engine, ops_session_maker) = (
            test_dbs
        )

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                timeout_layer_0=3.0,
                timeout_layer_2=3.0,
            )

            # Create very long input (10,000 characters)
            long_text = (
                "Machine learning is a subset of artificial intelligence. " * 200
            )

            response = await service.extract_entities(
                long_text, enable_trace=False
            )

            # Should handle without crashing
            assert response.request_id is not None
            assert response.metrics.total_sentences > 0

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_observability_store_failure(self, test_dbs):
        """Test that pipeline completes even if observability store fails."""
        (_kg_engine, kg_session_maker), (_ops_engine, ops_session_maker) = (
            test_dbs
        )

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            with patch("rag.rag_pipeline_service.KGContextProcessor") as MockKG, patch(
                "rag.rag_pipeline_service.LLMExtractionProcessor"
            ) as MockLLM, patch(
                "rag.rag_pipeline_service.SpaCyGapProcessor"
            ) as MockSpaCy, patch(
                "rag.rag_pipeline_service.ConceptResolutionProcessor"
            ) as MockConcept, patch(
                "rag.rag_pipeline_service.RAGObservabilityStore"
            ) as MockObs:

                MockKG.return_value.process.return_value = KGContextOutput(
                    extracted_phrases=[],
                    kg_nodes=[],
                    total_sentences=1,
                    trace_data={},
                )
                MockLLM.return_value.process.return_value = (
                    LLMExtractionOutput(
                        entities=[],
                        kg_context_size=0,
                        token_usage=None,
                        trace_data={},
                    )
                )
                MockSpaCy.return_value.process.return_value = SpaCyGapOutput(
                    gaps=[],
                    total_noun_phrases=0,
                    filtered_count=0,
                    trace_data={},
                )
                MockConcept.return_value.process.return_value = (
                    ConceptResolutionOutput(
                        resolved_concepts=[],
                        unresolved_gaps=[],
                        web_searches_performed=0,
                        cached_kg_hits=0,
                        full_kg_hits=0,
                        trace_data={},
                    )
                )

                # Observability store fails to save metrics
                MockObs.return_value.save_metrics.side_effect = Exception(
                    "Database write error"
                )

                service = RAGPipelineService(
                    kg_db_session=kg_session, ops_db_session=ops_session
                )

                # Pipeline should complete successfully despite observability failure
                response = await service.extract_entities(
                    "Test text", enable_trace=False
                )

                assert response.request_id is not None
                # Metrics should still be populated in response even if save failed
                assert response.metrics.total_execution_time_ms > 0

        finally:
            kg_session.close()
            ops_session.close()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, test_dbs):
        """Test handling of multiple concurrent RAG extraction requests."""
        (_kg_engine, kg_session_maker), (_ops_engine, ops_session_maker) = (
            test_dbs
        )

        kg_session = kg_session_maker()
        ops_session = ops_session_maker()

        try:
            service = RAGPipelineService(
                kg_db_session=kg_session,
                ops_db_session=ops_session,
                timeout_layer_0=2.0,
                timeout_layer_2=2.0,
            )

            # Create multiple concurrent requests
            texts = [
                "First test paragraph about machine learning.",
                "Second test paragraph about neural networks.",
                "Third test paragraph about artificial intelligence.",
                "Fourth test paragraph about deep learning.",
                "Fifth test paragraph about natural language processing.",
            ]

            # Execute all requests concurrently
            tasks = [
                service.extract_entities(text, enable_trace=False) for text in texts
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # All requests should complete successfully
            assert len(responses) == 5
            for response in responses:
                if isinstance(response, Exception):
                    pytest.fail(f"Request failed with exception: {response}")
                assert response.request_id is not None

            # All request IDs should be unique
            request_ids = [r.request_id for r in responses]
            assert len(set(request_ids)) == 5

        finally:
            kg_session.close()
            ops_session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

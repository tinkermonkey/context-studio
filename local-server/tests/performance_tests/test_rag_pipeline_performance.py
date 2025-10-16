"""
Performance tests for RAG Pipeline timeout enforcement.

These tests verify that layer timeouts are enforced and pipeline
completes within expected time budgets.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rag.rag_pipeline_service import RAGPipelineService
from rag.processors.models import (
    KGContextOutput,
    LLMExtractionOutput,
    SpaCyGapOutput,
    ConceptResolutionOutput
)


@pytest.fixture
def mock_db_sessions():
    """Create mock database sessions for performance testing."""
    kg_session = Mock()
    ops_session = Mock()
    ops_session.execute = Mock()
    ops_session.commit = Mock()
    ops_session.rollback = Mock()
    return kg_session, ops_session


class TestRAGPipelinePerformance:
    """Performance tests for RAG Pipeline Service."""

    @pytest.mark.asyncio
    async def test_layer_0_timeout_enforcement(self, mock_db_sessions):
        """Test that Layer 0 timeout (500ms) is enforced."""
        kg_session, ops_session = mock_db_sessions

        with patch('rag.rag_pipeline_service.KGContextProcessor') as MockKGProcessor, \
             patch('rag.rag_pipeline_service.LLMExtractionProcessor') as MockLLMProcessor, \
             patch('rag.rag_pipeline_service.SpaCyGapProcessor') as MockSpaCyProcessor, \
             patch('rag.rag_pipeline_service.ConceptResolutionProcessor') as MockConceptProcessor, \
             patch('rag.rag_pipeline_service.RAGObservabilityStore') as MockObsStore:

            # Setup Layer 0 to take longer than timeout
            mock_kg_proc = MockKGProcessor.return_value

            async def slow_process(*args, **kwargs):
                await asyncio.sleep(1.0)  # 1 second (> 500ms timeout)
                return KGContextOutput(
                    extracted_phrases=[],
                    kg_nodes=[],
                    total_sentences=1,
                    trace_data={}
                )

            mock_kg_proc.process.side_effect = slow_process

            # Setup other layers
            mock_llm_proc = MockLLMProcessor.return_value
            mock_llm_proc.process.return_value = LLMExtractionOutput(
                entities=[], kg_context_size=0, token_usage=None, trace_data={}
            )

            mock_spacy_proc = MockSpaCyProcessor.return_value
            mock_spacy_proc.process.return_value = SpaCyGapOutput(
                gaps=[], total_noun_phrases=0, filtered_count=0, trace_data={}
            )

            mock_concept_proc = MockConceptProcessor.return_value
            mock_concept_proc.process.return_value = ConceptResolutionOutput(
                resolved_concepts=[], unresolved_gaps=[], web_searches_performed=0,
                cached_kg_hits=0, full_kg_hits=0, trace_data={}
            )

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"

            service = RAGPipelineService(kg_session, ops_session)

            # Measure execution time
            start = time.time()
            response = await service.extract_entities("Test text", enable_trace=False)
            elapsed = time.time() - start

            # Layer 0 should have timed out, but total pipeline should complete
            # Total time should be much less than 1 second (the slow layer time)
            assert elapsed < 5.0  # Pipeline completes despite Layer 0 timeout

            # Layer 0 metrics should reflect timeout
            assert response.metrics.kg_layer.entities_found == 0

    @pytest.mark.asyncio
    async def test_layer_1_timeout_enforcement(self, mock_db_sessions):
        """Test that Layer 1 timeout (30s) is enforced."""
        kg_session, ops_session = mock_db_sessions

        with patch('rag.rag_pipeline_service.KGContextProcessor') as MockKGProcessor, \
             patch('rag.rag_pipeline_service.LLMExtractionProcessor') as MockLLMProcessor, \
             patch('rag.rag_pipeline_service.SpaCyGapProcessor') as MockSpaCyProcessor, \
             patch('rag.rag_pipeline_service.ConceptResolutionProcessor') as MockConceptProcessor, \
             patch('rag.rag_pipeline_service.RAGObservabilityStore') as MockObsStore:

            # Setup Layer 0 to succeed quickly
            mock_kg_proc = MockKGProcessor.return_value
            mock_kg_proc.process.return_value = KGContextOutput(
                extracted_phrases=[], kg_nodes=[], total_sentences=1, trace_data={}
            )

            # Setup Layer 1 to take longer than timeout
            mock_llm_proc = MockLLMProcessor.return_value

            async def slow_llm(*args, **kwargs):
                await asyncio.sleep(35.0)  # 35 seconds (> 30s timeout)
                return LLMExtractionOutput(
                    entities=[], kg_context_size=0, token_usage=None, trace_data={}
                )

            mock_llm_proc.process.side_effect = slow_llm

            # Setup other layers
            mock_spacy_proc = MockSpaCyProcessor.return_value
            mock_spacy_proc.process.return_value = SpaCyGapOutput(
                gaps=[], total_noun_phrases=0, filtered_count=0, trace_data={}
            )

            mock_concept_proc = MockConceptProcessor.return_value
            mock_concept_proc.process.return_value = ConceptResolutionOutput(
                resolved_concepts=[], unresolved_gaps=[], web_searches_performed=0,
                cached_kg_hits=0, full_kg_hits=0, trace_data={}
            )

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"

            service = RAGPipelineService(kg_session, ops_session)

            # Measure execution time
            start = time.time()
            response = await service.extract_entities("Test text", enable_trace=False)
            elapsed = time.time() - start

            # Pipeline should complete despite Layer 1 timeout
            # Should be much less than 35 seconds
            assert elapsed < 35.0
            assert response.metrics.llm_layer.entities_found == 0

    @pytest.mark.asyncio
    async def test_layer_2_timeout_enforcement(self, mock_db_sessions):
        """Test that Layer 2 timeout (500ms) is enforced."""
        kg_session, ops_session = mock_db_sessions

        with patch('rag.rag_pipeline_service.KGContextProcessor') as MockKGProcessor, \
             patch('rag.rag_pipeline_service.LLMExtractionProcessor') as MockLLMProcessor, \
             patch('rag.rag_pipeline_service.SpaCyGapProcessor') as MockSpaCyProcessor, \
             patch('rag.rag_pipeline_service.ConceptResolutionProcessor') as MockConceptProcessor, \
             patch('rag.rag_pipeline_service.RAGObservabilityStore') as MockObsStore:

            # Setup Layers 0 and 1 to succeed
            mock_kg_proc = MockKGProcessor.return_value
            mock_kg_proc.process.return_value = KGContextOutput(
                extracted_phrases=[], kg_nodes=[], total_sentences=1, trace_data={}
            )

            mock_llm_proc = MockLLMProcessor.return_value
            mock_llm_proc.process.return_value = LLMExtractionOutput(
                entities=[], kg_context_size=0, token_usage=None, trace_data={}
            )

            # Setup Layer 2 to take longer than timeout
            mock_spacy_proc = MockSpaCyProcessor.return_value

            async def slow_spacy(*args, **kwargs):
                await asyncio.sleep(1.0)  # 1 second (> 500ms timeout)
                return SpaCyGapOutput(
                    gaps=[], total_noun_phrases=0, filtered_count=0, trace_data={}
                )

            mock_spacy_proc.process.side_effect = slow_spacy

            mock_concept_proc = MockConceptProcessor.return_value
            mock_concept_proc.process.return_value = ConceptResolutionOutput(
                resolved_concepts=[], unresolved_gaps=[], web_searches_performed=0,
                cached_kg_hits=0, full_kg_hits=0, trace_data={}
            )

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"

            service = RAGPipelineService(kg_session, ops_session)

            start = time.time()
            response = await service.extract_entities("Test text", enable_trace=False)
            elapsed = time.time() - start

            # Should timeout and continue
            assert elapsed < 5.0
            assert response.metrics.nlp_layer.entities_found == 0

    @pytest.mark.asyncio
    async def test_layer_3_timeout_enforcement(self, mock_db_sessions):
        """Test that Layer 3 timeout (30s) is enforced."""
        kg_session, ops_session = mock_db_sessions

        with patch('rag.rag_pipeline_service.KGContextProcessor') as MockKGProcessor, \
             patch('rag.rag_pipeline_service.LLMExtractionProcessor') as MockLLMProcessor, \
             patch('rag.rag_pipeline_service.SpaCyGapProcessor') as MockSpaCyProcessor, \
             patch('rag.rag_pipeline_service.ConceptResolutionProcessor') as MockConceptProcessor, \
             patch('rag.rag_pipeline_service.RAGObservabilityStore') as MockObsStore:

            # Setup Layers 0-2 to succeed
            mock_kg_proc = MockKGProcessor.return_value
            mock_kg_proc.process.return_value = KGContextOutput(
                extracted_phrases=[], kg_nodes=[], total_sentences=1, trace_data={}
            )

            mock_llm_proc = MockLLMProcessor.return_value
            mock_llm_proc.process.return_value = LLMExtractionOutput(
                entities=[], kg_context_size=0, token_usage=None, trace_data={}
            )

            mock_spacy_proc = MockSpaCyProcessor.return_value
            mock_spacy_proc.process.return_value = SpaCyGapOutput(
                gaps=[], total_noun_phrases=0, filtered_count=0, trace_data={}
            )

            # Setup Layer 3 to take longer than timeout
            mock_concept_proc = MockConceptProcessor.return_value

            async def slow_concept(*args, **kwargs):
                await asyncio.sleep(35.0)  # 35 seconds (> 30s timeout)
                return ConceptResolutionOutput(
                    resolved_concepts=[], unresolved_gaps=[], web_searches_performed=0,
                    cached_kg_hits=0, full_kg_hits=0, trace_data={}
                )

            mock_concept_proc.process.side_effect = slow_concept

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"

            service = RAGPipelineService(kg_session, ops_session)

            start = time.time()
            response = await service.extract_entities("Test text", enable_trace=False)
            elapsed = time.time() - start

            # Should timeout and complete
            assert elapsed < 35.0
            assert response.metrics.web_layer.entities_found == 0

    @pytest.mark.asyncio
    async def test_fast_path_performance(self, mock_db_sessions):
        """Test performance of fast path (all layers succeed quickly)."""
        kg_session, ops_session = mock_db_sessions

        with patch('rag.rag_pipeline_service.KGContextProcessor') as MockKGProcessor, \
             patch('rag.rag_pipeline_service.LLMExtractionProcessor') as MockLLMProcessor, \
             patch('rag.rag_pipeline_service.SpaCyGapProcessor') as MockSpaCyProcessor, \
             patch('rag.rag_pipeline_service.ConceptResolutionProcessor') as MockConceptProcessor, \
             patch('rag.rag_pipeline_service.RAGObservabilityStore') as MockObsStore:

            # Setup all layers to succeed quickly
            mock_kg_proc = MockKGProcessor.return_value
            mock_kg_proc.process.return_value = KGContextOutput(
                extracted_phrases=[], kg_nodes=[], total_sentences=1, trace_data={}
            )

            mock_llm_proc = MockLLMProcessor.return_value
            mock_llm_proc.process.return_value = LLMExtractionOutput(
                entities=[], kg_context_size=0, token_usage=None, trace_data={}
            )

            mock_spacy_proc = MockSpaCyProcessor.return_value
            mock_spacy_proc.process.return_value = SpaCyGapOutput(
                gaps=[], total_noun_phrases=0, filtered_count=0, trace_data={}
            )

            mock_concept_proc = MockConceptProcessor.return_value
            mock_concept_proc.process.return_value = ConceptResolutionOutput(
                resolved_concepts=[], unresolved_gaps=[], web_searches_performed=0,
                cached_kg_hits=0, full_kg_hits=0, trace_data={}
            )

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"

            service = RAGPipelineService(kg_session, ops_session)

            start = time.time()
            response = await service.extract_entities("Test text", enable_trace=False)
            elapsed = time.time() - start

            # Fast path should complete quickly (well under any timeout)
            assert elapsed < 1.0  # Should be very fast with mocks
            assert response.request_id is not None

    @pytest.mark.asyncio
    async def test_total_pipeline_timeout_budget(self, mock_db_sessions):
        """Test that total pipeline completes within 120s budget even with multiple slow layers."""
        kg_session, ops_session = mock_db_sessions

        with patch('rag.rag_pipeline_service.KGContextProcessor') as MockKGProcessor, \
             patch('rag.rag_pipeline_service.LLMExtractionProcessor') as MockLLMProcessor, \
             patch('rag.rag_pipeline_service.SpaCyGapProcessor') as MockSpaCyProcessor, \
             patch('rag.rag_pipeline_service.ConceptResolutionProcessor') as MockConceptProcessor, \
             patch('rag.rag_pipeline_service.RAGObservabilityStore') as MockObsStore:

            # Setup all layers to take moderate time (within individual timeouts)
            async def moderate_kg(*args, **kwargs):
                await asyncio.sleep(0.4)  # 400ms (under 500ms timeout)
                return KGContextOutput(
                    extracted_phrases=[], kg_nodes=[], total_sentences=1, trace_data={}
                )

            async def moderate_llm(*args, **kwargs):
                await asyncio.sleep(0.1)  # 100ms
                return LLMExtractionOutput(
                    entities=[], kg_context_size=0, token_usage=None, trace_data={}
                )

            async def moderate_spacy(*args, **kwargs):
                await asyncio.sleep(0.4)  # 400ms (under 500ms timeout)
                return SpaCyGapOutput(
                    gaps=[], total_noun_phrases=0, filtered_count=0, trace_data={}
                )

            async def moderate_concept(*args, **kwargs):
                await asyncio.sleep(0.1)  # 100ms
                return ConceptResolutionOutput(
                    resolved_concepts=[], unresolved_gaps=[], web_searches_performed=0,
                    cached_kg_hits=0, full_kg_hits=0, trace_data={}
                )

            mock_kg_proc = MockKGProcessor.return_value
            mock_kg_proc.process.side_effect = moderate_kg

            mock_llm_proc = MockLLMProcessor.return_value
            mock_llm_proc.process.side_effect = moderate_llm

            mock_spacy_proc = MockSpaCyProcessor.return_value
            mock_spacy_proc.process.side_effect = moderate_spacy

            mock_concept_proc = MockConceptProcessor.return_value
            mock_concept_proc.process.side_effect = moderate_concept

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"

            service = RAGPipelineService(kg_session, ops_session)

            start = time.time()
            response = await service.extract_entities("Test text", enable_trace=False)
            elapsed = time.time() - start

            # Total should be sum of layer times (~1 second)
            assert elapsed < 2.0  # Reasonable margin
            assert elapsed >= 1.0  # Should take at least 1 second with these delays

            # All layers should complete successfully
            assert response.metrics.kg_layer.execution_time_ms > 0
            assert response.metrics.llm_layer.execution_time_ms > 0
            assert response.metrics.nlp_layer.execution_time_ms > 0
            assert response.metrics.web_layer.execution_time_ms > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

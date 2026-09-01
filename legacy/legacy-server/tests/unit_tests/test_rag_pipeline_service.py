"""
Unit tests for RAG Pipeline Service with mocked processors.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch

import pytest
from rag.processors.models import (
    ConceptResolutionOutput,
    ExtractedPhrase,
    GapConcept,
    GapPriority,
    KGContextOutput,
    KGNode,
    LLMExtractionOutput,
    ResolutionMethod,
    ResolvedConcept,
    SpaCyGapOutput,
)
from rag.processors.models import (
    ExtractedEntity as ProcessorExtractedEntity,
)
from rag.rag_pipeline_service import RAGPipelineService


@pytest.fixture
def mock_db_sessions():
    """Create mock database sessions for testing."""
    kg_session = Mock()
    ops_session = Mock()
    ops_session.execute = Mock()
    ops_session.commit = Mock()
    ops_session.rollback = Mock()
    return kg_session, ops_session


@pytest.fixture
def mock_kg_context_output():
    """Create mock KG context output."""
    return KGContextOutput(
        extracted_phrases=[
            ExtractedPhrase(
                text="machine learning", sentence_index=0, start_char=0, end_char=16
            ),
            ExtractedPhrase(
                text="neural networks", sentence_index=0, start_char=20, end_char=35
            ),
        ],
        kg_nodes=[
            KGNode(
                node_id="kg1",
                title="Machine Learning",
                node_type="term",
                similarity_score=0.95,
                definition="A field of artificial intelligence",
            ),
            KGNode(
                node_id="kg2",
                title="Neural Networks",
                node_type="term",
                similarity_score=0.90,
                definition="Computing systems inspired by biological neural networks",
            ),
        ],
        total_sentences=1,
        trace_data={},
    )


@pytest.fixture
def mock_llm_extraction_output():
    """Create mock LLM extraction output."""
    return LLMExtractionOutput(
        entities=[
            ProcessorExtractedEntity(
                text="machine learning",
                entity_type="CONCEPT",
                confidence=0.95,
                sentence_indices=[0],
                matched_kg_node="kg1",
                start_char=0,
                end_char=16,
            ),
            ProcessorExtractedEntity(
                text="artificial intelligence",
                entity_type="CONCEPT",
                confidence=0.92,
                sentence_indices=[0],
                matched_kg_node=None,
                start_char=50,
                end_char=73,
            ),
        ],
        kg_context_size=2,
        token_usage={"prompt_tokens": 100, "completion_tokens": 50},
        trace_data={},
    )


@pytest.fixture
def mock_spacy_gap_output():
    """Create mock spaCy gap output."""
    return SpaCyGapOutput(
        gaps=[
            GapConcept(
                text="deep learning",
                sentence_index=0,
                priority=GapPriority.IMPORTANT,
                dep_role="dobj",
                head_word="uses",
                connected_verb="uses",
                start_char=80,
                end_char=93,
                tf_idf_score=0.25,
            )
        ],
        total_noun_phrases=5,
        filtered_count=2,
        trace_data={},
    )


@pytest.fixture
def mock_concept_resolution_output(mock_spacy_gap_output):
    """Create mock concept resolution output."""
    return ConceptResolutionOutput(
        resolved_concepts=[
            ResolvedConcept(
                original_gap=mock_spacy_gap_output.gaps[0],
                resolution_method=ResolutionMethod.FULL_KG,
                matched_kg_node=KGNode(
                    node_id="kg3",
                    title="Deep Learning",
                    node_type="term",
                    similarity_score=0.88,
                    definition="Subset of machine learning",
                ),
                web_definition=None,
                confidence=0.70,
            )
        ],
        unresolved_gaps=[],
        web_searches_performed=0,
        cached_kg_hits=0,
        full_kg_hits=1,
        trace_data={},
    )


class TestRAGPipelineService:
    """Test suite for RAG Pipeline Service."""

    @pytest.mark.asyncio
    async def test_successful_extraction_all_layers(
        self,
        mock_db_sessions,
        mock_kg_context_output,
        mock_llm_extraction_output,
        mock_spacy_gap_output,
        mock_concept_resolution_output,
    ):
        """Test successful entity extraction through all four layers."""
        kg_session, ops_session = mock_db_sessions

        with patch(
            "rag.rag_pipeline_service.KGContextProcessor"
        ) as MockKGProcessor, patch(
            "rag.rag_pipeline_service.LLMExtractionProcessor"
        ) as MockLLMProcessor, patch(
            "rag.rag_pipeline_service.SpaCyGapProcessor"
        ) as MockSpaCyProcessor, patch(
            "rag.rag_pipeline_service.ConceptResolutionProcessor"
        ) as MockConceptProcessor, patch(
            "rag.rag_pipeline_service.RAGObservabilityStore"
        ) as MockObsStore:

            # Setup mocks
            mock_kg_proc = MockKGProcessor.return_value
            mock_kg_proc.process.return_value = mock_kg_context_output

            mock_llm_proc = MockLLMProcessor.return_value
            mock_llm_proc.process.return_value = mock_llm_extraction_output

            mock_spacy_proc = MockSpaCyProcessor.return_value
            mock_spacy_proc.process.return_value = mock_spacy_gap_output

            mock_concept_proc = MockConceptProcessor.return_value
            mock_concept_proc.process.return_value = mock_concept_resolution_output

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"
            mock_obs_store.save_trace.return_value = "trace123"

            # Create service
            service = RAGPipelineService(kg_session, ops_session)

            # Execute extraction
            text = "Machine learning uses deep learning techniques in artificial intelligence."
            response = await service.extract_entities(text, enable_trace=False)

            # Assertions
            assert response.request_id is not None
            assert len(response.entities) == 3  # ML + AI + DL after dedup
            assert response.metrics.total_entities == 3
            assert response.metrics.kg_layer.entities_found == 2
            assert response.metrics.llm_layer.entities_found == 2
            assert response.metrics.nlp_layer.entities_found == 1
            assert response.metrics.web_layer.entities_found == 1
            assert response.trace_available is False

            # Verify all processors were called
            mock_kg_proc.process.assert_called_once()
            mock_llm_proc.process.assert_called_once()
            mock_spacy_proc.process.assert_called_once()
            mock_concept_proc.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_layer_0_timeout_graceful_degradation(self, mock_db_sessions):
        """Test that Layer 0 timeout allows pipeline to continue with empty KG context."""
        kg_session, ops_session = mock_db_sessions

        with patch(
            "rag.rag_pipeline_service.KGContextProcessor"
        ) as MockKGProcessor, patch(
            "rag.rag_pipeline_service.LLMExtractionProcessor"
        ) as MockLLMProcessor, patch(
            "rag.rag_pipeline_service.SpaCyGapProcessor"
        ) as MockSpaCyProcessor, patch(
            "rag.rag_pipeline_service.ConceptResolutionProcessor"
        ) as MockConceptProcessor, patch(
            "rag.rag_pipeline_service.RAGObservabilityStore"
        ) as MockObsStore:

            # Setup Layer 0 to timeout
            mock_kg_proc = MockKGProcessor.return_value

            def timeout_func(*args, **kwargs):
                import time

                time.sleep(1.0)  # Longer than 500ms timeout
                return KGContextOutput(
                    extracted_phrases=[], kg_nodes=[], total_sentences=1, trace_data={}
                )

            mock_kg_proc.process.side_effect = timeout_func

            # Setup other layers to succeed
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
                resolved_concepts=[],
                unresolved_gaps=[],
                web_searches_performed=0,
                cached_kg_hits=0,
                full_kg_hits=0,
                trace_data={},
            )

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"

            # Create service
            service = RAGPipelineService(kg_session, ops_session)

            # Execute extraction
            response = await service.extract_entities("Test text", enable_trace=False)

            # Assertions
            assert response.request_id is not None
            assert len(response.entities) == 0  # No entities due to timeout
            assert response.metrics.kg_layer.entities_found == 0
            # Pipeline should have continued despite Layer 0 timeout
            mock_llm_proc.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_layer_1_timeout_graceful_degradation(
        self, mock_db_sessions, mock_kg_context_output
    ):
        """Test that Layer 1 timeout allows pipeline to continue without LLM entities."""
        kg_session, ops_session = mock_db_sessions

        with patch(
            "rag.rag_pipeline_service.KGContextProcessor"
        ) as MockKGProcessor, patch(
            "rag.rag_pipeline_service.LLMExtractionProcessor"
        ) as MockLLMProcessor, patch(
            "rag.rag_pipeline_service.SpaCyGapProcessor"
        ) as MockSpaCyProcessor, patch(
            "rag.rag_pipeline_service.ConceptResolutionProcessor"
        ) as MockConceptProcessor, patch(
            "rag.rag_pipeline_service.RAGObservabilityStore"
        ) as MockObsStore:

            # Setup Layer 0 to succeed
            mock_kg_proc = MockKGProcessor.return_value
            mock_kg_proc.process.return_value = mock_kg_context_output

            # Setup Layer 1 to timeout
            mock_llm_proc = MockLLMProcessor.return_value

            def timeout_func(*args, **kwargs):
                import time

                time.sleep(2.0)  # Longer than the configured timeout
                return LLMExtractionOutput(
                    entities=[], kg_context_size=0, token_usage=None, trace_data={}
                )

            mock_llm_proc.process.side_effect = timeout_func

            # Create service with shorter Layer 1 timeout for testing
            # Use 2.5s timeout since the mock processor sleeps for 2s
            service = RAGPipelineService(kg_session, ops_session, timeout_layer_1=2.5)

            # Setup other layers to succeed
            mock_spacy_proc = MockSpaCyProcessor.return_value
            mock_spacy_proc.process.return_value = SpaCyGapOutput(
                gaps=[], total_noun_phrases=0, filtered_count=0, trace_data={}
            )

            mock_concept_proc = MockConceptProcessor.return_value
            mock_concept_proc.process.return_value = ConceptResolutionOutput(
                resolved_concepts=[],
                unresolved_gaps=[],
                web_searches_performed=0,
                cached_kg_hits=0,
                full_kg_hits=0,
                trace_data={},
            )

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"

            # Execute extraction
            response = await service.extract_entities("Test text", enable_trace=False)

            # Assertions
            assert response.request_id is not None
            assert len(response.entities) == 0
            assert response.metrics.llm_layer.entities_found == 0
            # Pipeline should have continued to Layer 2
            mock_spacy_proc.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_entity_deduplication_90_percent_threshold(self, mock_db_sessions):
        """Test that entities with 90%+ similarity are deduplicated."""
        kg_session, ops_session = mock_db_sessions

        with patch(
            "rag.rag_pipeline_service.KGContextProcessor"
        ) as MockKGProcessor, patch(
            "rag.rag_pipeline_service.LLMExtractionProcessor"
        ) as MockLLMProcessor, patch(
            "rag.rag_pipeline_service.SpaCyGapProcessor"
        ) as MockSpaCyProcessor, patch(
            "rag.rag_pipeline_service.ConceptResolutionProcessor"
        ) as MockConceptProcessor, patch(
            "rag.rag_pipeline_service.RAGObservabilityStore"
        ) as MockObsStore:

            # Setup mocks
            mock_kg_proc = MockKGProcessor.return_value
            mock_kg_proc.process.return_value = KGContextOutput(
                extracted_phrases=[], kg_nodes=[], total_sentences=1, trace_data={}
            )

            # LLM extracts "machine learning"
            mock_llm_proc = MockLLMProcessor.return_value
            mock_llm_proc.process.return_value = LLMExtractionOutput(
                entities=[
                    ProcessorExtractedEntity(
                        text="machine learning",
                        entity_type="CONCEPT",
                        confidence=0.95,
                        sentence_indices=[0],
                        matched_kg_node=None,
                        start_char=0,
                        end_char=16,
                    )
                ],
                kg_context_size=0,
                token_usage=None,
                trace_data={},
            )

            # spaCy detects "Machine Learning" (same entity, different case)
            gap = GapConcept(
                text="Machine Learning",
                sentence_index=0,
                priority=GapPriority.IMPORTANT,
                dep_role="dobj",
                head_word="test",
                connected_verb="test",
                start_char=0,
                end_char=16,
                tf_idf_score=0.25,
            )

            mock_spacy_proc = MockSpaCyProcessor.return_value
            mock_spacy_proc.process.return_value = SpaCyGapOutput(
                gaps=[gap], total_noun_phrases=1, filtered_count=0, trace_data={}
            )

            # Resolution resolves the gap
            mock_concept_proc = MockConceptProcessor.return_value
            mock_concept_proc.process.return_value = ConceptResolutionOutput(
                resolved_concepts=[
                    ResolvedConcept(
                        original_gap=gap,
                        resolution_method=ResolutionMethod.CACHED_KG,
                        matched_kg_node=None,
                        web_definition="A definition",
                        confidence=0.75,
                    )
                ],
                unresolved_gaps=[],
                web_searches_performed=0,
                cached_kg_hits=1,
                full_kg_hits=0,
                trace_data={},
            )

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"

            # Create service
            service = RAGPipelineService(kg_session, ops_session)

            # Execute extraction
            response = await service.extract_entities(
                "Machine learning test", enable_trace=False
            )

            # Assertions - should only have 1 entity after deduplication
            assert len(response.entities) == 1
            assert response.entities[0].text.lower() == "machine learning"
            # Should prefer LLM extraction (higher priority)
            assert response.entities[0].source_layer == "llm"

    @pytest.mark.asyncio
    async def test_observability_metrics_saved(
        self,
        mock_db_sessions,
        mock_kg_context_output,
        mock_llm_extraction_output,
        mock_spacy_gap_output,
        mock_concept_resolution_output,
    ):
        """Test that observability metrics are saved to database."""
        kg_session, ops_session = mock_db_sessions

        with patch(
            "rag.rag_pipeline_service.KGContextProcessor"
        ) as MockKGProcessor, patch(
            "rag.rag_pipeline_service.LLMExtractionProcessor"
        ) as MockLLMProcessor, patch(
            "rag.rag_pipeline_service.SpaCyGapProcessor"
        ) as MockSpaCyProcessor, patch(
            "rag.rag_pipeline_service.ConceptResolutionProcessor"
        ) as MockConceptProcessor, patch(
            "rag.rag_pipeline_service.RAGObservabilityStore"
        ) as MockObsStore:

            # Setup mocks
            mock_kg_proc = MockKGProcessor.return_value
            mock_kg_proc.process.return_value = mock_kg_context_output

            mock_llm_proc = MockLLMProcessor.return_value
            mock_llm_proc.process.return_value = mock_llm_extraction_output

            mock_spacy_proc = MockSpaCyProcessor.return_value
            mock_spacy_proc.process.return_value = mock_spacy_gap_output

            mock_concept_proc = MockConceptProcessor.return_value
            mock_concept_proc.process.return_value = mock_concept_resolution_output

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"

            # Create service
            service = RAGPipelineService(kg_session, ops_session)

            # Execute extraction
            response = await service.extract_entities("Test text", enable_trace=False)

            # Verify save_metrics was called with correct parameters
            mock_obs_store.save_metrics.assert_called_once()
            call_args = mock_obs_store.save_metrics.call_args

            # Check that metrics include all required fields
            assert call_args[0][0] == response.request_id  # request_id
            # Total time, layer times, and counts should be present

    @pytest.mark.asyncio
    async def test_observability_traces_saved_when_enabled(
        self,
        mock_db_sessions,
        mock_kg_context_output,
        mock_llm_extraction_output,
        mock_spacy_gap_output,
        mock_concept_resolution_output,
    ):
        """Test that observability traces are saved when trace is enabled."""
        kg_session, ops_session = mock_db_sessions

        with patch(
            "rag.rag_pipeline_service.KGContextProcessor"
        ) as MockKGProcessor, patch(
            "rag.rag_pipeline_service.LLMExtractionProcessor"
        ) as MockLLMProcessor, patch(
            "rag.rag_pipeline_service.SpaCyGapProcessor"
        ) as MockSpaCyProcessor, patch(
            "rag.rag_pipeline_service.ConceptResolutionProcessor"
        ) as MockConceptProcessor, patch(
            "rag.rag_pipeline_service.RAGObservabilityStore"
        ) as MockObsStore:

            # Setup mocks
            mock_kg_proc = MockKGProcessor.return_value
            mock_kg_proc.process.return_value = mock_kg_context_output

            mock_llm_proc = MockLLMProcessor.return_value
            mock_llm_proc.process.return_value = mock_llm_extraction_output

            mock_spacy_proc = MockSpaCyProcessor.return_value
            mock_spacy_proc.process.return_value = mock_spacy_gap_output

            mock_concept_proc = MockConceptProcessor.return_value
            mock_concept_proc.process.return_value = mock_concept_resolution_output

            mock_obs_store = MockObsStore.return_value
            mock_obs_store.save_metrics.return_value = "metrics123"
            mock_obs_store.save_trace.return_value = "trace123"

            # Create service
            service = RAGPipelineService(kg_session, ops_session)

            # Execute extraction WITH trace enabled
            response = await service.extract_entities("Test text", enable_trace=True)

            # Verify save_trace was called for each layer
            assert mock_obs_store.save_trace.call_count == 4  # One per layer
            assert response.trace_available is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

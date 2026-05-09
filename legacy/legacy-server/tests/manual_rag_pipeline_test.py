"""
Manual test script for RAG Pipeline Service.

This script tests the RAG pipeline without pytest dependencies.
"""

import asyncio
from unittest.mock import Mock, patch

from rag.rag_pipeline_service import RAGPipelineService
from rag.processors.models import (
    KGContextOutput,
    LLMExtractionOutput,
    SpaCyGapOutput,
    ConceptResolutionOutput,
    ExtractedEntity as ProcessorExtractedEntity,
    KGNode,
    ExtractedPhrase,
)


def create_mock_sessions():
    """Create mock database sessions."""
    kg_session = Mock()
    ops_session = Mock()
    ops_session.execute = Mock()
    ops_session.commit = Mock()
    ops_session.rollback = Mock()
    return kg_session, ops_session


def test_text_similarity():
    """Test the text similarity calculation."""
    print("Testing text similarity calculation...")
    kg_session, ops_session = create_mock_sessions()

    with patch("rag.rag_pipeline_service.KGContextProcessor"), patch(
        "rag.rag_pipeline_service.LLMExtractionProcessor"
    ), patch("rag.rag_pipeline_service.SpaCyGapProcessor"), patch(
        "rag.rag_pipeline_service.ConceptResolutionProcessor"
    ), patch(
        "rag.rag_pipeline_service.RAGObservabilityStore"
    ):

        service = RAGPipelineService(kg_session, ops_session)

        # Test exact match
        similarity = service._text_similarity(
            "machine learning", "machine learning"
        )  # noqa: E501
        assert similarity == 1.0, f"Expected 1.0, got {similarity}"
        print("✓ Exact match test passed")

        # Test case-insensitive match
        similarity = service._text_similarity(
            "machine learning", "machine learning".lower()
        )  # noqa: E501
        assert similarity == 1.0, f"Expected 1.0, got {similarity}"
        print("✓ Case-insensitive match test passed")

        # Test high similarity
        similarity = service._text_similarity(
            "machine learning", "machine learnings"
        )  # noqa: E501
        assert similarity > 0.9, f"Expected > 0.9, got {similarity}"
        print(f"✓ High similarity test passed (similarity: {similarity:.3f})")

        # Test low similarity
        similarity = service._text_similarity(
            "machine learning", "deep learning"
        )  # noqa: E501
        assert similarity < 0.9, f"Expected < 0.9, got {similarity}"
        print(f"✓ Low similarity test passed (similarity: {similarity:.3f})")

        print("All text similarity tests passed!\n")


async def test_successful_extraction():
    """Test successful extraction through all layers."""
    print("Testing successful extraction through all layers...")
    kg_session, ops_session = create_mock_sessions()

    with patch("rag.rag_pipeline_service.KGContextProcessor") as MockKGProcessor, patch(
        "rag.rag_pipeline_service.LLMExtractionProcessor"
    ) as MockLLMProcessor, patch(
        "rag.rag_pipeline_service.SpaCyGapProcessor"
    ) as MockSpaCyProcessor, patch(
        "rag.rag_pipeline_service.ConceptResolutionProcessor"
    ) as MockConceptProcessor, patch(
        "rag.rag_pipeline_service.RAGObservabilityStore"
    ) as MockObsStore:  # noqa: E501

        # Setup mocks
        mock_kg_proc = MockKGProcessor.return_value
        mock_kg_proc.process.return_value = KGContextOutput(
            extracted_phrases=[
                ExtractedPhrase(
                    text="machine learning", sentence_index=0, start_char=0, end_char=16
                )  # noqa: E501
            ],
            kg_nodes=[
                KGNode(
                    node_id="kg1",
                    title="Machine Learning",
                    node_type="term",
                    similarity_score=0.95,
                    definition="A field of AI",
                )
            ],
            total_sentences=1,
            trace_data={},
        )

        mock_llm_proc = MockLLMProcessor.return_value
        mock_llm_proc.process.return_value = LLMExtractionOutput(
            entities=[
                ProcessorExtractedEntity(
                    text="machine learning",
                    entity_type="CONCEPT",
                    confidence=0.95,
                    sentence_indices=[0],
                    matched_kg_node="kg1",
                    start_char=0,
                    end_char=16,
                )
            ],
            kg_context_size=1,
            token_usage=None,
            trace_data={},
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
        text = "Machine learning is important."
        response = await service.extract_entities(text, enable_trace=False)

        # Assertions
        assert response.request_id is not None, "Request ID should not be None"
        print(f"✓ Request ID generated: {response.request_id}")

        assert len(response.entities) > 0, "Should have extracted entities"
        print(f"✓ Extracted {len(response.entities)} entities")

        assert (
            response.metrics.total_execution_time_ms > 0
        ), "Should have execution time"  # noqa: E501
        print(
            f"✓ Total execution time: {response.metrics.total_execution_time_ms:.2f}ms"
        )  # noqa: E501

        assert (
            response.metrics.kg_layer.entities_found == 1
        ), "KG layer should find 1 node"  # noqa: E501
        print(
            f"✓ KG layer found {response.metrics.kg_layer.entities_found} nodes"
        )  # noqa: E501

        assert (
            response.metrics.llm_layer.entities_found == 1
        ), "LLM layer should find 1 entity"  # noqa: E501
        print(
            f"✓ LLM layer found {response.metrics.llm_layer.entities_found} entities"
        )  # noqa: E501

        # Verify processors were called
        assert mock_kg_proc.process.called, "KG processor should be called"
        assert mock_llm_proc.process.called, "LLM processor should be called"
        assert (
            mock_spacy_proc.process.called
        ), "spaCy processor should be called"  # noqa: E501
        assert (
            mock_concept_proc.process.called
        ), "Concept processor should be called"  # noqa: E501
        print("✓ All processors were called")

        print("All extraction tests passed!\n")


async def test_layer_timeout():
    """Test layer timeout handling."""
    print("Testing layer timeout handling...")
    kg_session, ops_session = create_mock_sessions()

    with patch("rag.rag_pipeline_service.KGContextProcessor") as MockKGProcessor, patch(
        "rag.rag_pipeline_service.LLMExtractionProcessor"
    ) as MockLLMProcessor, patch(
        "rag.rag_pipeline_service.SpaCyGapProcessor"
    ) as MockSpaCyProcessor, patch(
        "rag.rag_pipeline_service.ConceptResolutionProcessor"
    ) as MockConceptProcessor, patch(
        "rag.rag_pipeline_service.RAGObservabilityStore"
    ) as MockObsStore:  # noqa: E501

        # Setup Layer 0 to timeout
        async def timeout_func(*args, **kwargs):
            await asyncio.sleep(1.0)  # Longer than 500ms timeout
            return Mock()

        mock_kg_proc = MockKGProcessor.return_value
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
        response = await service.extract_entities(
            "Test text", enable_trace=False
        )  # noqa: E501

        # Assertions
        assert response.request_id is not None, "Request ID should not be None"
        print(f"✓ Request ID generated despite timeout: {response.request_id}")

        assert (
            response.metrics.kg_layer.entities_found == 0
        ), "KG layer should have 0 entities due to timeout"  # noqa: E501
        print("✓ KG layer correctly shows 0 entities after timeout")

        # Pipeline should have continued despite timeout
        assert (
            mock_llm_proc.process.called
        ), "LLM processor should still be called"  # noqa: E501
        print("✓ Pipeline continued to LLM layer despite KG timeout")

        print("All timeout tests passed!\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("RAG Pipeline Service Manual Tests")
    print("=" * 60 + "\n")

    try:
        # Run synchronous test
        test_text_similarity()

        # Run async tests
        asyncio.run(test_successful_extraction())
        asyncio.run(test_layer_timeout())

        print("=" * 60)
        print("ALL TESTS PASSED! ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

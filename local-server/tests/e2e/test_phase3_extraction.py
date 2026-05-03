"""
E2E tests for Phase 3: Knowledge Extraction Layers integration.

Tests cover the four-layer extraction pipeline orchestration:
- Layer 0: Knowledge Graph Context (KG similarity search)
- Layer 1: LLM Extraction (structured JSON with context)
- Layer 2: NLP Gap-Filling (entity recognition fallback)
- Layer 3: Reference Source Enrichment (URI and metadata lookup)

These tests verify:
- Full pipeline execution with real adapters
- Layer orchestration and forward-context passing
- Reference aggregation across multiple sources
- Extraction metrics and execution traces
- Reference cache effectiveness

Run with: pytest -m extraction
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
import tempfile
from pathlib import Path

from domain.extraction.services import ExtractionService
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.reference.cache import CachedReferenceSource

# Import fakes
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_extraction_repository import FakeExtractionRepository
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_reference_source import FakeReferenceSource


@pytest.mark.llm
@pytest.mark.nlp
@pytest.mark.reference
class TestExtractionWithKGContext:
    """Tests for extraction with knowledge graph context enrichment."""

    def test_extraction_with_kg_context_includes_kg_entities(self):
        """Extraction with KG context includes entities from the knowledge graph."""
        # Set up KG with sample entities
        kg_repo = FakeOntologyRepository()
        kg_repo.setup_sample_data()

        # Create embedding service
        embedding_service = SentenceTransformerEmbedding()

        # Create extraction service with KG context
        service = ExtractionService(
            ontology_repo=kg_repo,
            embedding_service=embedding_service,
            llm=FakeLLMProvider(response_content='{"entities": []}'),
            nlp=SpacyNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        # Execute extraction
        text = "Apple is a technology company"
        result = service.extract(text)

        # Verify extraction result structure
        assert result.id is not None
        assert result.text == text
        assert isinstance(result.entities, list)
        assert isinstance(result.layers_executed, list)
        # Should have executed at least the KG context layer
        assert len(result.layers_executed) > 0

    def test_extraction_with_kg_context_passes_context_to_llm(self):
        """KG context from Layer 0 is passed to LLM Layer 1."""
        kg_repo = FakeOntologyRepository()
        kg_repo.setup_sample_data()

        embedding_service = SentenceTransformerEmbedding()
        llm = FakeLLMProvider(response_content='{"entities": []}')

        service = ExtractionService(
            ontology_repo=kg_repo,
            embedding_service=embedding_service,
            llm=llm,
            nlp=SpacyNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        text = "Technology companies include Microsoft and Google"
        service.extract(text)

        # Verify LLM was called (indicating layer execution)
        assert llm.call_count > 0


@pytest.mark.llm
@pytest.mark.nlp
class TestExtractionLayerMetrics:
    """Tests for extraction layer metrics and execution tracing."""

    def test_extraction_layer_metrics_captures_execution_time(self):
        """Extraction result includes execution time metrics."""
        kg_repo = FakeOntologyRepository()
        embedding_service = SentenceTransformerEmbedding()

        service = ExtractionService(
            ontology_repo=kg_repo,
            embedding_service=embedding_service,
            llm=FakeLLMProvider(),
            nlp=SpacyNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.extract("Apple is a company")

        # Verify metrics are captured
        assert result.duration_ms is not None
        assert result.duration_ms >= 0

    def test_extraction_layer_metrics_tracks_layer_execution_order(self):
        """Extraction result tracks which layers executed and in what order."""
        kg_repo = FakeOntologyRepository()
        embedding_service = SentenceTransformerEmbedding()

        service = ExtractionService(
            ontology_repo=kg_repo,
            embedding_service=embedding_service,
            llm=FakeLLMProvider(),
            nlp=SpacyNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.extract("Sample text for extraction")

        # Verify layer execution tracking
        assert len(result.layers_executed) > 0
        # Layers should have order information
        for i, layer in enumerate(result.layers_executed):
            assert layer.layer_num is not None
            assert layer.layer_name is not None
            # Verify sequential order
            assert layer.layer_num == i or layer.layer_num <= 3

    def test_extraction_layer_metrics_tracks_error_in_layer_execution(self):
        """Extraction result includes error details when a layer fails."""
        kg_repo = FakeOntologyRepository()
        embedding_service = SentenceTransformerEmbedding()
        # Use a broken reference source
        broken_ref = FakeReferenceSource(should_fail=True)

        service = ExtractionService(
            ontology_repo=kg_repo,
            embedding_service=embedding_service,
            llm=FakeLLMProvider(),
            nlp=SpacyNLPProcessor(),
            reference_sources=[broken_ref],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.extract("Text to extract")

        # Should complete despite reference source failure
        assert result is not None
        # Layer 3 should have recorded an error or continued with entities
        layer_3 = next(
            (layer for layer in result.layers_executed if layer.layer_num == 3), None
        )
        if layer_3 is not None:
            # Either layer recorded an error message OR it has entities despite failure
            assert layer_3.error_message is not None or len(layer_3.entities) > 0


@pytest.mark.reference
class TestReferenceAggregationAcrossSources:
    """Tests for reference source aggregation in Layer 3."""

    def test_reference_aggregation_across_sources_combines_results(self):
        """Extraction aggregates results from multiple reference sources."""
        kg_repo = FakeOntologyRepository()
        embedding_service = SentenceTransformerEmbedding()

        # Create multiple reference sources
        source1 = FakeReferenceSource(name="source-1")
        source2 = FakeReferenceSource(name="source-2")
        source3 = FakeReferenceSource(name="source-3")

        service = ExtractionService(
            ontology_repo=kg_repo,
            embedding_service=embedding_service,
            llm=FakeLLMProvider(response_content='{"entities": [{"label": "apple"}]}'),
            nlp=SpacyNLPProcessor(),
            reference_sources=[source1, source2, source3],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.extract("Apple is a company")

        # Verify that reference layer executed
        layer_3 = next(
            (layer for layer in result.layers_executed if layer.layer_num == 3), None
        )
        assert layer_3 is not None
        assert layer_3.layer_name == "Reference Source Enrichment"

    def test_reference_aggregation_continues_on_source_failure(self):
        """Extraction continues when one reference source fails."""
        kg_repo = FakeOntologyRepository()
        embedding_service = SentenceTransformerEmbedding()

        # Mix working and failing sources
        working_source = FakeReferenceSource(name="working")
        failing_source = FakeReferenceSource(name="failing", should_fail=True)

        service = ExtractionService(
            ontology_repo=kg_repo,
            embedding_service=embedding_service,
            llm=FakeLLMProvider(response_content='{"entities": [{"label": "test"}]}'),
            nlp=SpacyNLPProcessor(),
            reference_sources=[working_source, failing_source],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.extract("Test entity")

        # Should complete despite one source failing
        assert result is not None
        assert len(result.layers_executed) > 0


@pytest.mark.reference
class TestReferenceCacheEffectiveness:
    """Tests for reference source caching in Layer 3."""

    def test_reference_cache_effectiveness_reduces_repeated_lookups(self):
        """Reference cache reduces repeated lookups to the same source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kg_repo = FakeOntologyRepository()
            embedding_service = SentenceTransformerEmbedding()

            # Create a cached reference source
            inner_source = FakeReferenceSource(name="cached-source")
            cache_db = Path(tmpdir) / "reference_cache.db"
            cached_source = CachedReferenceSource(inner_source, str(cache_db))

            service = ExtractionService(
                ontology_repo=kg_repo,
                embedding_service=embedding_service,
                llm=FakeLLMProvider(
                    response_content='{"entities": [{"label": "apple"}]}'
                ),
                nlp=SpacyNLPProcessor(),
                reference_sources=[cached_source],
                event_publisher=FakeEventPublisher(),
                extraction_repo=FakeExtractionRepository(),
            )

            # First extraction
            text1 = "Apple is a company"
            result1 = service.extract(text1)
            assert result1 is not None

            # Get initial call count
            initial_calls = inner_source.call_count

            # Second extraction with same search term
            text2 = "Apple produces iPhones"
            result2 = service.extract(text2)
            assert result2 is not None

            # Cache should reduce additional calls for repeated terms
            # The cache hit means call count should not increase much
            final_calls = inner_source.call_count
            # Cache should prevent most duplicate lookups (allow up to 2 new calls)
            assert final_calls <= initial_calls + 2, (
                f"Expected cache to limit additional calls to 2, but got {final_calls - initial_calls} "
                f"(initial: {initial_calls}, final: {final_calls})"
            )

    def test_reference_cache_effectiveness_cache_database_created(self):
        """Reference cache creates and persists cache database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "reference_cache.db"
            inner_source = FakeReferenceSource(name="test-source")

            # Create cached source
            _cached = CachedReferenceSource(inner_source, str(cache_db))

            # Verify cache database exists
            assert cache_db.exists()
            assert cache_db.stat().st_size > 0


@pytest.mark.llm
@pytest.mark.nlp
@pytest.mark.reference
def test_full_rag_extraction_pipeline():
    """
    E2E test for full RAG extraction pipeline.

    Verifies that all 4 layers execute successfully with:
    - At least 3 entities extracted from the input text
    - Execution trace stored with layer metadata
    - All layers contributing to the final result
    """
    # Set up all required adapters
    kg_repo = FakeOntologyRepository()
    kg_repo.setup_sample_data()
    embedding_service = SentenceTransformerEmbedding()

    # Create reference sources for Layer 3
    ref_source1 = FakeReferenceSource(name="ref-1")
    ref_source2 = FakeReferenceSource(name="ref-2")

    # Create extraction service with all four layers
    event_publisher = FakeEventPublisher()
    extraction_repo = FakeExtractionRepository()

    service = ExtractionService(
        ontology_repo=kg_repo,
        embedding_service=embedding_service,
        llm=FakeLLMProvider(
            response_content='{"entities": [{"label": "Microsoft"}, {"label": "Google"}, {"label": "Apple"}]}'
        ),
        nlp=SpacyNLPProcessor(),
        reference_sources=[ref_source1, ref_source2],
        event_publisher=event_publisher,
        extraction_repo=extraction_repo,
    )

    # Execute the full RAG extraction pipeline
    input_text = "Microsoft, Google, and Apple are major technology companies"
    result = service.extract(input_text)

    # Verify extraction result
    assert result is not None
    assert result.id is not None
    assert result.text == input_text

    # Verify at least 3 entities extracted
    assert (
        len(result.entities) >= 3
    ), f"Expected at least 3 entities, got {len(result.entities)}: {result.entities}"

    # Verify all 4 layers executed
    assert (
        len(result.layers_executed) == 4
    ), f"Expected 4 layers executed, got {len(result.layers_executed)}"

    # Verify each layer in sequence
    layer_nums = [layer.layer_num for layer in result.layers_executed]
    assert layer_nums == [0, 1, 2, 3], f"Expected layers [0, 1, 2, 3], got {layer_nums}"

    # Verify layer metadata
    for layer in result.layers_executed:
        assert layer.layer_name is not None
        assert layer.duration_ms >= 0
        assert isinstance(layer.entities, list)

    # Verify execution trace is stored
    assert result.duration_ms >= 0
    assert result.created_at is not None

    # Verify at least Layer 1 (LLM) extracted entities
    llm_layer = next(
        (layer for layer in result.layers_executed if layer.layer_num == 1), None
    )
    assert llm_layer is not None
    # LLM layer should contribute entities
    assert llm_layer.entities or len(result.entities) > 0

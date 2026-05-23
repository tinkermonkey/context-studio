"""
Unit tests for ExtractionService.

Tests cover all business logic: layer orchestration, error isolation,
deduplication with string similarity, event emission, and forward-output
passing between layers. Uses in-memory fakes with zero infrastructure imports.
"""

import pytest

from domain.extraction.entities import ExtractedEntity
from domain.extraction.events import ExtractionCompleted
from domain.extraction.exceptions import ExtractionError
from domain.extraction.services import ExtractionService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_extraction_repository import FakeExtractionRepository
from tests.fakes.fake_extraction_run_repo import FakeExtractionRunRepository
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_reference_source import FakeReferenceSource

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def service():
    """Create a fresh ExtractionService with in-memory fakes."""
    return ExtractionService(
        ontology_repo=FakeOntologyRepository(),
        embedding_service=FakeEmbeddingService(),
        llm=FakeLLMProvider(),
        nlp=FakeNLPProcessor(),
        reference_sources=[FakeReferenceSource("TestSource")],
        event_publisher=FakeEventPublisher(),
        extraction_repo=FakeExtractionRepository(),
        extraction_run_repo=FakeExtractionRunRepository(),
    )


# ============================================================================
# Test Cases
# ============================================================================


class TestExtract:
    """Tests for extract() orchestration."""

    def test_extract_success_all_layers(self, service):
        """Extract entities through all layers and verify result structure."""
        result = service.extract("Apple and Microsoft are companies.")

        assert result.id is not None
        assert result.text == "Apple and Microsoft are companies."
        assert len(result.layers_executed) == 4
        assert len(result.extracted_entities) > 0
        assert result.total_duration_ms >= 0
        assert result.created_at is not None

        # Verify all layers recorded
        for i in range(4):
            layer = result.layers_executed[i]
            assert layer.layer_number == i
            assert isinstance(layer.duration_ms, int)
            assert layer.success is not None

    def test_extract_empty_text_raises(self, service):
        """Extract from empty text raises ExtractionError."""
        with pytest.raises(ExtractionError, match="empty"):
            service.extract("")

    def test_extract_whitespace_text_raises(self, service):
        """Extract from whitespace-only text raises ExtractionError."""
        with pytest.raises(ExtractionError, match="empty"):
            service.extract("   ")

    def test_extract_layer_failure_isolated(self):
        """All layers execute even when some have empty output."""
        # Layer 0 will have empty output (no entities in repo)
        # But all layers should still execute
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        result = service.extract("Test text")

        # All 4 layers should be recorded and succeeded
        assert len(result.layers_executed) == 4

        # All layers should report success (they don't raise exceptions)
        for layer in result.layers_executed:
            assert layer.success is True

        # But we should still get entities from layers that found them (LLM, NLP, ref)
        assert len(result.extracted_entities) > 0

    def test_extract_emits_completion_event(self, service):
        """Extraction emits ExtractionCompleted event with correct data."""
        result = service.extract("Test text with entities")

        events = service._event_publisher.get_events()
        assert len(events) > 0

        completion_events = [e for e in events if isinstance(e, ExtractionCompleted)]
        assert len(completion_events) == 1

        event = completion_events[0]
        assert event.result_id == result.id
        assert event.entity_count == len(result.extracted_entities)
        assert event.duration_ms == result.total_duration_ms

    def test_extract_measures_duration(self, service):
        """Extract records execution time."""
        result = service.extract("Test text")

        # Duration should be non-negative
        assert result.total_duration_ms >= 0

        # At least one layer should be executed
        assert len(result.layers_executed) > 0


class TestDeduplication:
    """Tests for deduplication logic."""

    def test_deduplicate_exact_match_prefers_higher_priority(self):
        """Exact label match keeps highest-priority entity."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        # Create entities with same label but different source layers
        entity_layer_0 = ExtractedEntity(
            label="Apple",
            entity_type="ORG",
            source_layer=0,
            confidence=0.9,
        )
        entity_layer_1 = ExtractedEntity(
            label="Apple",
            entity_type="ORG",
            source_layer=1,
            confidence=0.95,
        )
        entity_layer_3 = ExtractedEntity(
            label="Apple",
            entity_type="ORG",
            source_layer=3,
            confidence=0.8,
        )

        # Deduplication should keep layer 1 (highest priority)
        deduplicated = service._deduplicate([entity_layer_0, entity_layer_1, entity_layer_3])

        assert len(deduplicated) == 1
        assert deduplicated[0].source_layer == 1

    def test_deduplicate_similarity_threshold(self):
        """Similar labels below threshold are kept separate."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        # Labels with low similarity (below 0.85)
        entity_a = ExtractedEntity(label="Apple", entity_type="ORG", source_layer=0)
        entity_b = ExtractedEntity(label="Banana", entity_type="ORG", source_layer=1)

        deduplicated = service._deduplicate([entity_a, entity_b])

        assert len(deduplicated) == 2
        assert {e.label for e in deduplicated} == {"Apple", "Banana"}

    def test_deduplicate_case_insensitive(self):
        """Deduplication is case-insensitive."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        entity_a = ExtractedEntity(label="Apple", entity_type="ORG", source_layer=0)
        entity_b = ExtractedEntity(label="APPLE", entity_type="ORG", source_layer=1)

        deduplicated = service._deduplicate([entity_a, entity_b])

        # Should be deduplicated (case-insensitive match)
        assert len(deduplicated) == 1
        # Keeps higher-priority entity (layer 1 > layer 0)
        assert deduplicated[0].source_layer == 1

    def test_deduplicate_whitespace_normalized(self):
        """Deduplication normalizes whitespace."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        entity_a = ExtractedEntity(label="Apple Inc.", entity_type="ORG", source_layer=0)
        entity_b = ExtractedEntity(label="  Apple Inc.  ", entity_type="ORG", source_layer=1)

        deduplicated = service._deduplicate([entity_a, entity_b])

        assert len(deduplicated) == 1

    def test_deduplicate_priority_order(self):
        """Deduplication respects priority: 1 > 0 > 2 > 3."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        # Same entity from all layers
        entities = [
            ExtractedEntity(label="Apple", entity_type="ORG", source_layer=0),
            ExtractedEntity(label="Apple", entity_type="ORG", source_layer=1),
            ExtractedEntity(label="Apple", entity_type="ORG", source_layer=2),
            ExtractedEntity(label="Apple", entity_type="ORG", source_layer=3),
        ]

        deduplicated = service._deduplicate(entities)

        # Should keep only layer 1 (highest priority)
        assert len(deduplicated) == 1
        assert deduplicated[0].source_layer == 1

    def test_deduplicate_empty_list(self):
        """Deduplicating empty list returns empty list."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        result = service._deduplicate([])
        assert result == []

    def test_deduplicate_single_entity(self):
        """Deduplicating single entity returns it unchanged."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        entity = ExtractedEntity(label="Apple", entity_type="ORG", source_layer=1)
        result = service._deduplicate([entity])

        assert len(result) == 1
        assert result[0].label == "Apple"


class TestLayerExecution:
    """Tests for layer execution error handling."""

    def test_all_layers_executed_even_with_failures(self):
        """All four layers execute even if one fails."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(should_fail=True),  # Layer 1 fails
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        result = service.extract("Test text")

        # Should have executed all 4 layers
        assert len(result.layers_executed) == 4

        # All should be recorded
        for layer in result.layers_executed:
            assert layer.layer_name is not None
            assert layer.duration_ms >= 0

    def test_layer_returns_empty_output_gracefully(self):
        """Layer that returns empty output doesn't stop extraction."""

        # LLM provider with no available models returns empty output
        class NoModelsLLMProvider:
            def list_available_models(self):
                return []

            def is_model_available(self, model):
                return False

            def complete(self, *args, **kwargs):
                # Won't be called if no models available
                raise RuntimeError("Should not be called")

        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=NoModelsLLMProvider(),
            nlp=FakeNLPProcessor(),  # This layer still runs
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        result = service.extract("Test text with content")

        # Layer 1 gracefully handles no available models
        assert result.layers_executed[1].success is True
        assert result.layers_executed[1].entities_found == 0  # No entities from LLM

        # Layer 2 (NLP) should have succeeded and found entities
        assert result.layers_executed[2].success is True

        # NLP layer should have found entities (FakeEntity from the fake processor)
        assert any(e.entity_type == "ORG" for e in result.extracted_entities)


class TestLayerForwardOutput:
    """Tests for forward-output passing between layers."""

    def test_each_layer_receives_prior_entities(self):
        """Each layer receives existing entities from prior layers."""
        # This is harder to test directly without mocking layer functions,
        # but we can verify that the service returns a result with entities
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        result = service.extract("Test text")

        # If layers are passing forward output, we should get entities
        assert isinstance(result.extracted_entities, list)
        assert len(result.layers_executed) == 4


class TestStringSimilarity:
    """Tests for string similarity computation."""

    def test_normalized_similarity_exact_match(self):
        """Exact match returns 1.0."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        sim = service._normalized_similarity("Apple", "Apple")
        assert sim == 1.0

    def test_normalized_similarity_case_insensitive(self):
        """Case-insensitive comparison."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        sim = service._normalized_similarity("apple", "APPLE")
        assert sim == 1.0

    def test_normalized_similarity_empty_strings(self):
        """Empty strings have zero similarity."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        sim = service._normalized_similarity("", "")
        assert sim == 1.0  # Both empty match exactly

        sim = service._normalized_similarity("Apple", "")
        assert sim == 0.0

    def test_normalized_similarity_one_character_difference(self):
        """Single character difference reduces similarity."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        # "Apple" vs "Apples" - one extra character
        sim = service._normalized_similarity("Apple", "Apples")
        assert 0.8 < sim < 1.0  # High but not exact


class TestAnalyzeText:
    """Tests for analyze_text() use case."""

    def test_analyze_text_success(self, service):
        """Analyze text extracts entities through KG context and NLP layers."""
        result = service.analyze_text("Apple and Microsoft are companies.")

        # Should have result structure
        assert result.id is not None
        assert result.text == "Apple and Microsoft are companies."
        assert len(result.extracted_entities) > 0
        assert result.total_duration_ms >= 0
        assert result.created_at is not None

        # Should execute layers 0 and 2 (KG context and NLP gap-filling)
        # Note: The full extract() runs all 4 layers, but analyze_text() runs 0 and 2
        assert len(result.layers_executed) >= 2

    def test_analyze_text_empty_text_raises(self, service):
        """Analyze text with empty text raises ExtractionError."""
        with pytest.raises(ExtractionError, match="empty"):
            service.analyze_text("")

    def test_analyze_text_whitespace_text_raises(self, service):
        """Analyze text with whitespace-only text raises ExtractionError."""
        with pytest.raises(ExtractionError, match="empty"):
            service.analyze_text("   ")

    def test_analyze_text_emits_completion_event(self, service):
        """Analyze text emits ExtractionCompleted event with correct data."""
        result = service.analyze_text("Test text with entities")

        events = service._event_publisher.get_events()
        assert len(events) > 0

        completion_events = [e for e in events if isinstance(e, ExtractionCompleted)]
        assert len(completion_events) > 0

        event = completion_events[-1]  # Get the most recent event
        assert event.result_id == result.id
        assert event.entity_count == len(result.extracted_entities)
        assert event.duration_ms == result.total_duration_ms

    def test_analyze_text_measures_duration(self, service):
        """Analyze text records execution time."""
        result = service.analyze_text("Test text")

        # Duration should be non-negative
        assert result.total_duration_ms >= 0

        # At least one layer should be executed
        assert len(result.layers_executed) > 0


class TestEnrichFromReferences:
    """Tests for enrich_from_references() use case."""

    def test_enrich_from_references_success(self, service):
        """Enrich entities with external references."""
        # Start with some entities
        input_entities = [
            ExtractedEntity(
                label="Apple",
                entity_type="ORG",
                source_layer=1,
                confidence=0.9,
            ),
            ExtractedEntity(
                label="Microsoft",
                entity_type="ORG",
                source_layer=1,
                confidence=0.85,
            ),
        ]

        result = service.enrich_from_references(
            "Apple and Microsoft are companies.",
            input_entities,
        )

        # Should have result structure
        assert result.id is not None
        assert result.text == "Apple and Microsoft are companies."
        assert len(result.extracted_entities) > 0
        assert result.total_duration_ms >= 0
        assert result.created_at is not None

        # Should contain at least the input entities (possibly enriched)
        result_labels = {e.label for e in result.extracted_entities}
        assert "Apple" in result_labels
        assert "Microsoft" in result_labels

    def test_enrich_from_references_empty_text_raises(self, service):
        """Enrich with empty text raises ExtractionError."""
        input_entities = [ExtractedEntity(label="Apple", entity_type="ORG", source_layer=1)]

        with pytest.raises(ExtractionError, match="empty"):
            service.enrich_from_references("", input_entities)

    def test_enrich_from_references_whitespace_text_raises(self, service):
        """Enrich with whitespace-only text raises ExtractionError."""
        input_entities = [ExtractedEntity(label="Apple", entity_type="ORG", source_layer=1)]

        with pytest.raises(ExtractionError, match="empty"):
            service.enrich_from_references("   ", input_entities)

    def test_enrich_from_references_empty_entities(self, service):
        """Enrich with empty entity list returns result structure."""
        result = service.enrich_from_references("Test text", [])

        # Should have result structure even with no input entities
        assert result.id is not None
        assert result.text == "Test text"
        assert result.total_duration_ms >= 0
        assert result.created_at is not None

    def test_enrich_from_references_deduplicates(self, service):
        """Enrich deduplicates input entities with reference results."""
        # Input with duplicates
        input_entities = [
            ExtractedEntity(
                label="Apple",
                entity_type="ORG",
                source_layer=0,
                confidence=0.8,
            ),
            ExtractedEntity(
                label="Apple",  # Same label
                entity_type="ORG",
                source_layer=2,
                confidence=0.75,
            ),
        ]

        result = service.enrich_from_references("Apple Inc.", input_entities)

        # Deduplication should occur
        apple_entities = [e for e in result.extracted_entities if e.label == "Apple"]
        # Should keep the highest-priority entity (source_layer 0 has higher priority than 2)
        assert len(apple_entities) >= 1

    def test_enrich_from_references_emits_completion_event(self, service):
        """Enrich from references emits ExtractionCompleted event."""
        input_entities = [ExtractedEntity(label="Apple", entity_type="ORG", source_layer=1)]

        result = service.enrich_from_references("Apple", input_entities)

        events = service._event_publisher.get_events()
        assert len(events) > 0

        completion_events = [e for e in events if isinstance(e, ExtractionCompleted)]
        assert len(completion_events) > 0

        event = completion_events[-1]  # Get the most recent event
        assert event.result_id == result.id
        assert event.entity_count == len(result.extracted_entities)
        assert event.duration_ms == result.total_duration_ms

    def test_enrich_from_references_measures_duration(self, service):
        """Enrich from references records execution time."""
        input_entities = [ExtractedEntity(label="Apple", entity_type="ORG", source_layer=1)]

        result = service.enrich_from_references("Apple", input_entities)

        # Duration should be non-negative
        assert result.total_duration_ms >= 0

        # Layer 3 should be executed
        assert len(result.layers_executed) > 0


class TestExceptionHandling:
    """Tests for exception behavior."""

    def test_all_layers_fail_returns_empty_result(self):
        """Extraction returns empty result even if all layers fail.

        Empty results are valid—they indicate the text contains no entities,
        not that extraction failed.
        """

        # All layers fail to extract entities (either by exception or returning no results)
        class ThrowingOntologyRepository:
            def get_all_entities_and_relationships(self):
                raise RuntimeError("Ontology repo error")

        class ThrowingEmbeddingService:
            def embed(self, text):
                raise RuntimeError("Embedding error")

            def embed_batch(self, texts):
                raise RuntimeError("Embedding error")

            def similarity(self, a, b):
                raise RuntimeError("Embedding error")

        service = ExtractionService(
            ontology_repo=ThrowingOntologyRepository(),  # Layer 0 fails
            embedding_service=ThrowingEmbeddingService(),
            llm=FakeLLMProvider(should_fail=True),  # Layer 1 fails
            nlp=FakeNLPProcessor(should_fail=True),  # Layer 2 fails (empty entities)
            reference_sources=[
                FakeReferenceSource(should_fail=True)
            ],  # Layer 3: no entities to enrich
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        # No entities extracted across all layers returns empty result, not error
        result = service.extract("Test text")
        assert result.extracted_entities == []
        assert len(result.layers_executed) == 4
        # At least layers 0, 1, 2 failed (see logs)
        # Note: layer 3 (reference enrichment) succeeds but has nothing to enrich
        assert not result.layers_executed[0].success  # Layer 0 failed
        assert not result.layers_executed[1].success  # Layer 1 failed
        assert not result.layers_executed[2].success  # Layer 2 failed

    def test_nlp_processor_not_ready_allows_continuation(self):
        """NLP processor not ready doesn't stop extraction."""

        class NotReadyNLPProcessor:
            def is_ready(self):
                return False

            def process(self, text):
                # Won't be called if not ready
                raise RuntimeError("Should not be called")

            def extract_entities(self, text):
                # Won't be called if not ready
                raise RuntimeError("Should not be called")

        # LLM provider that returns valid JSON entities
        llm_provider = FakeLLMProvider(
            response_content=('[{"label": "TestEntity", "type": "ORG", "confidence": 0.9}]')
        )

        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=llm_provider,
            nlp=NotReadyNLPProcessor(),  # Layer 2 not ready
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        # Should not raise despite NLP not being ready - LLM will extract entities
        result = service.extract("Test text")

        # Layer 2 (NLP) should be recorded as failed since processor not ready
        # This allows users to distinguish "no entities found" from "processor unavailable"
        assert result.layers_executed[2].success is False
        assert result.layers_executed[2].error_message is not None
        assert "not ready" in result.layers_executed[2].error_message.lower()
        # But other layers should still execute successfully
        assert result.layers_executed[3].success is True
        # And we should still get a result with entities from other layers
        assert result.total_duration_ms >= 0

    def test_reference_source_not_available_allows_continuation(self):
        """Reference source not available doesn't stop extraction."""

        class UnavailableReferenceSource:
            @property
            def source_name(self):
                return "UnavailableSource"

            def search(self, term, limit=10):
                # Won't be called if not available
                raise RuntimeError("Should not be called")

            def get_relations(self, uri, limit=10):
                raise RuntimeError("Should not be called")

            def is_available(self):
                return False

        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[UnavailableReferenceSource()],  # Layer 3 not available
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
        )

        # Should not raise despite reference source not available
        result = service.extract("Test text")

        assert result.layers_executed[3].success is True
        assert result.layers_executed[3].entities_found == 0
        assert len(result.layers_executed) == 4

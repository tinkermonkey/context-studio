"""
Unit tests for extraction pipeline orchestration using fakes.

Tests cover:
- Full extraction pipeline execution with all 4 layers
- Entity deduplication and prioritization
- Layer failure isolation and graceful degradation
- Event emission and audit trails
- Extraction use cases (extract, analyze_text, enrich_from_references)

These tests use in-memory fakes to test business logic without external dependencies.
All tests complete quickly and provide rapid feedback on core extraction logic.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from domain.extraction.services import ExtractionService
from domain.extraction.entities import ExtractedEntity
from domain.extraction.exceptions import ExtractionError
from domain.extraction.events import ExtractionCompleted
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_reference_source import FakeReferenceSource
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_extraction_repository import FakeExtractionRepository


class TestFullExtractionPipeline:
    """Tests for the complete extraction pipeline."""

    def test_extract_with_all_layers_active(self):
        """Extract entities using all 4 layers."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(response_content='[{"label": "Apple", "type": "ORG", "confidence": 0.95}]'),
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource("TestSource")],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.extract("Apple and Microsoft are technology companies.")

        # Verify result structure
        assert result.id is not None
        assert result.text == "Apple and Microsoft are technology companies."
        assert len(result.layers_executed) == 4
        assert len(result.extracted_entities) > 0
        assert result.total_duration_ms >= 0
        assert result.created_at is not None

        # Verify all layers executed
        layer_numbers = [layer.layer_number for layer in result.layers_executed]
        assert layer_numbers == [0, 1, 2, 3]

    def test_extract_emits_completion_event(self):
        """Extraction emits completion event with correct data."""
        event_publisher = FakeEventPublisher()
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(response_content='[{"label": "TestEntity", "type": "ORG", "confidence": 0.9}]'),
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource()],
            event_publisher=event_publisher,
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.extract("Test content")

        events = event_publisher.get_events()
        completion_events = [e for e in events if isinstance(e, ExtractionCompleted)]

        assert len(completion_events) > 0
        event = completion_events[0]
        assert event.result_id == result.id
        assert event.entity_count == len(result.extracted_entities)
        assert event.duration_ms == result.total_duration_ms

    def test_extract_with_layer_failures_continues(self):
        """Extraction continues and returns results even when a layer fails."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(should_fail=True),  # Layer 1 fails
            nlp=FakeNLPProcessor(),  # Layer 2 still succeeds
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.extract("Test text for extraction")

        # Should have executed all 4 layers despite layer 1 failure
        assert len(result.layers_executed) == 4

        # Layer 1 should report failure but not stop extraction
        assert result.layers_executed[1].success is False

        # Should still get entities from other layers
        assert len(result.extracted_entities) > 0

    def test_extract_invalid_inputs(self):
        """Extraction rejects invalid inputs."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        # Empty text
        with pytest.raises(ExtractionError):
            service.extract("")

        # Whitespace only
        with pytest.raises(ExtractionError):
            service.extract("   \n\t  ")


class TestEntityDeduplication:
    """Tests for entity deduplication logic."""

    def test_deduplicate_exact_matches(self):
        """Identical entities are deduplicated."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(response_content='[{"label": "Apple", "type": "ORG", "confidence": 0.95}]'),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        # Create entities with same label from different layers
        entity_layer_0 = ExtractedEntity(
            label="Apple",
            entity_type="ORG",
            source_layer=0,
            confidence=0.8,
        )
        entity_layer_1 = ExtractedEntity(
            label="Apple",
            entity_type="ORG",
            source_layer=1,
            confidence=0.95,
        )

        # Deduplicate keeps highest priority (layer 1)
        deduplicated = service._deduplicate([entity_layer_0, entity_layer_1])

        assert len(deduplicated) == 1
        assert deduplicated[0].source_layer == 1
        assert deduplicated[0].confidence == 0.95

    def test_deduplicate_case_insensitive(self):
        """Deduplication handles case variations."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        entities = [
            ExtractedEntity(label="apple", entity_type="ORG", source_layer=0),
            ExtractedEntity(label="APPLE", entity_type="ORG", source_layer=1),
        ]

        deduplicated = service._deduplicate(entities)

        # Should deduplicate to single entity (case-insensitive)
        assert len(deduplicated) == 1

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
        )

        entities = [
            ExtractedEntity(label="Apple Inc.", entity_type="ORG", source_layer=0),
            ExtractedEntity(label="  Apple Inc.  ", entity_type="ORG", source_layer=1),
        ]

        deduplicated = service._deduplicate(entities)

        assert len(deduplicated) == 1


class TestLayerPriority:
    """Tests for layer priority in deduplication."""

    def test_layer_priority_order(self):
        """Layer 1 (LLM) has highest priority in deduplication."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        # Same entity from all layers
        entities = [
            ExtractedEntity(label="Entity", entity_type="ORG", source_layer=0, confidence=0.5),
            ExtractedEntity(label="Entity", entity_type="ORG", source_layer=1, confidence=0.9),
            ExtractedEntity(label="Entity", entity_type="ORG", source_layer=2, confidence=0.7),
            ExtractedEntity(label="Entity", entity_type="ORG", source_layer=3, confidence=0.6),
        ]

        deduplicated = service._deduplicate(entities)

        # Should keep layer 1 (highest priority)
        assert len(deduplicated) == 1
        assert deduplicated[0].source_layer == 1


class TestUseCase_AnalyzeText:
    """Tests for analyze_text use case."""

    def test_analyze_text_basic(self):
        """Analyze text for entities using KG context and NLP."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.analyze_text("Apple and Microsoft are companies.")

        assert result.id is not None
        assert result.text == "Apple and Microsoft are companies."
        assert len(result.layers_executed) >= 2  # Layers 0 and 2
        assert len(result.extracted_entities) > 0

    def test_analyze_text_invalid_inputs(self):
        """Analyze text rejects invalid inputs."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        with pytest.raises(ExtractionError):
            service.analyze_text("")

        with pytest.raises(ExtractionError):
            service.analyze_text("   ")


class TestUseCase_EnrichFromReferences:
    """Tests for enrich_from_references use case."""

    def test_enrich_from_references_basic(self):
        """Enrich entities with reference source data."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource("TestSource")],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        input_entities = [
            ExtractedEntity(
                label="Apple",
                entity_type="ORG",
                source_layer=1,
                confidence=0.95,
            ),
            ExtractedEntity(
                label="Microsoft",
                entity_type="ORG",
                source_layer=1,
                confidence=0.9,
            ),
        ]

        result = service.enrich_from_references(
            "Apple and Microsoft are companies.",
            input_entities,
        )

        assert result.id is not None
        assert result.text == "Apple and Microsoft are companies."
        assert len(result.extracted_entities) >= len(input_entities)

        # Input entities should still be in result
        result_labels = {e.label for e in result.extracted_entities}
        assert "Apple" in result_labels
        assert "Microsoft" in result_labels

    def test_enrich_empty_entities(self):
        """Enrich with empty entity list returns results."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.enrich_from_references("Test text", [])

        assert result.id is not None
        assert result.text == "Test text"
        assert isinstance(result.extracted_entities, list)

    def test_enrich_invalid_text(self):
        """Enrich rejects invalid text input."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        entities = [ExtractedEntity(label="Test", entity_type="ORG", source_layer=1)]

        with pytest.raises(ExtractionError):
            service.enrich_from_references("", entities)


class TestErrorHandling:
    """Tests for error handling and resilience."""

    def test_all_layers_fail_returns_empty_result(self):
        """Extraction returns empty result if all layers fail.

        Empty results are valid—they indicate the text contains no entities,
        not that extraction failed.
        """
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(should_fail=True),
            nlp=FakeNLPProcessor(should_fail=True),
            reference_sources=[FakeReferenceSource(should_fail=True)],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        # Should not raise, but return empty result
        result = service.extract("Test text")
        assert result.extracted_entities == []
        assert len(result.layers_executed) == 4

    def test_layer_exception_isolation(self):
        """Single layer exception doesn't stop other layers."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(should_fail=True),  # Layer 1 throws
            nlp=FakeNLPProcessor(),  # Layer 2 still runs
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.extract("Test content for extraction")

        # All layers should execute
        assert len(result.layers_executed) == 4

        # Layer 1 should be marked as failed
        assert result.layers_executed[1].success is False

        # But result should still have entities from other layers
        assert len(result.extracted_entities) > 0

    def test_graceful_degradation(self):
        """Extraction degrades gracefully with missing services."""
        # NLP processor not ready
        class NotReadyNLPProcessor:
            def is_ready(self):
                return False
            def process(self, text):
                raise RuntimeError("Not ready")
            def extract_entities(self, text):
                raise RuntimeError("Not ready")

        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(response_content='[{"label": "Entity", "type": "ORG", "confidence": 0.9}]'),
            nlp=NotReadyNLPProcessor(),
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        # Should not raise despite NLP not being ready
        result = service.extract("Test text")

        # Should still extract from LLM
        assert len(result.extracted_entities) > 0


class TestPerformance:
    """Tests for performance characteristics."""

    def test_extraction_completes_in_reasonable_time(self):
        """Extraction completes with reasonable performance."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        result = service.extract("Test text for performance measurement")

        # Should complete with reasonable duration (fakes are fast)
        assert result.total_duration_ms >= 0
        assert result.total_duration_ms < 5000  # Less than 5 seconds for fakes

    def test_batch_extraction_performance(self):
        """Multiple extractions perform efficiently."""
        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
        )

        texts = [
            "First text content",
            "Second text content",
            "Third text content",
        ]

        results = []
        for text in texts:
            result = service.extract(text)
            results.append(result)

        # All extractions should complete
        assert len(results) == 3
        assert all(r.id is not None for r in results)
        assert all(len(r.extracted_entities) > 0 for r in results)

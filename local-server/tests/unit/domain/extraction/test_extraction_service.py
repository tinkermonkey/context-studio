"""
Unit tests for ExtractionService.

Tests the four-layer extraction pipeline, deduplication logic, error handling,
and configuration options.
"""

import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)

import pytest
from unittest.mock import Mock

from domain.extraction.services import ExtractionService
from domain.extraction.entities import ExtractedEntity, ExtractionResult
from domain.extraction.exceptions import ExtractionError


class FakeOntologyRepository:
    """Fake ontology repository for testing."""

    def get_by_semantic_similarity(self, embedding, limit=5):
        return []


class FakeEmbeddingService:
    """Fake embedding service for testing."""

    def embed(self, text):
        return [0.0] * 384  # Dummy embedding


class FakeLLMProvider:
    """Fake LLM provider for testing."""

    def complete(self, system_prompt, user_prompt, model, **kwargs):
        from domain.pipeline.ports import LLMResponse

        # Simple response for testing
        return LLMResponse(
            content='[{"label": "Apple", "type": "ORG", "confidence": 0.9}]',
            tokens_in=10,
            tokens_out=20,
            duration_ms=100.0,
            finish_reason="stop",
            model=model,
        )

    def is_model_available(self, model):
        return True

    def list_available_models(self):
        return ["gpt-4"]


class FakeNLPProcessor:
    """Fake NLP processor for testing."""

    def extract_entities(self, text):
        from domain.extraction.ports import NLPEntity

        return [
            NLPEntity(
                text="Steve",
                label="PERSON",
                start=0,
                end=5,
                confidence=0.95,
                linked_uri=None,
            ),
        ]

    def is_ready(self):
        return True

    def process(self, text):
        return Mock()


class FakeReferenceSource:
    """Fake reference source for testing."""

    @property
    def source_name(self):
        return "TestSource"

    def search(self, term, limit=10):
        from domain.extraction.ports import ReferenceResult

        if term.lower() == "apple":
            return [
                ReferenceResult(
                    uri="https://example.com/Apple",
                    label="Apple Inc.",
                    description="Technology company",
                    confidence=0.95,
                    source="TestSource",
                )
            ]
        return []

    def get_relations(self, uri, limit=10):
        return []

    def is_available(self):
        return True


class FakeExtractionRepository:
    """Fake extraction repository for testing."""

    def __init__(self):
        self.saved_results = []

    def save_extraction_result(self, result):
        self.saved_results.append(result)
        return result

    def get_extraction_result(self, result_id):
        for result in self.saved_results:
            if result.id == result_id:
                return result
        return None

    def list_extraction_results(self, limit=100, offset=0):
        return self.saved_results[offset : offset + limit]


class FakeEventPublisher:
    """Fake event publisher for testing."""

    def __init__(self):
        self.published_events = []

    def publish(self, event) -> list[tuple[str, Exception]]:
        self.published_events.append(event)
        return []


@pytest.fixture
def service_with_fakes():
    """Create an ExtractionService with fake dependencies."""
    ontology_repo = FakeOntologyRepository()
    embedding_service = FakeEmbeddingService()
    llm = FakeLLMProvider()
    nlp = FakeNLPProcessor()
    reference_sources = [FakeReferenceSource()]
    event_publisher = FakeEventPublisher()
    extraction_repo = FakeExtractionRepository()

    service = ExtractionService(
        ontology_repo=ontology_repo,
        embedding_service=embedding_service,
        llm=llm,
        nlp=nlp,
        reference_sources=reference_sources,
        event_publisher=event_publisher,
        extraction_repo=extraction_repo,
        similarity_threshold=0.85,
    )

    return {
        "service": service,
        "ontology_repo": ontology_repo,
        "embedding_service": embedding_service,
        "llm": llm,
        "nlp": nlp,
        "reference_sources": reference_sources,
        "event_publisher": event_publisher,
        "extraction_repo": extraction_repo,
    }


class TestExtractionServiceConfiguration:
    """Test configuration and initialization."""

    def test_similarity_threshold_configurable(self, service_with_fakes):
        """Test that similarity threshold is configurable at runtime."""
        service = service_with_fakes["service"]
        assert service._similarity_threshold == 0.85

    def test_similarity_threshold_validation(self, service_with_fakes):
        """Test that invalid similarity thresholds are rejected."""
        ontology_repo = FakeOntologyRepository()
        embedding_service = FakeEmbeddingService()
        llm = FakeLLMProvider()
        nlp = FakeNLPProcessor()
        reference_sources = []
        event_publisher = FakeEventPublisher()
        extraction_repo = FakeExtractionRepository()

        with pytest.raises(ValueError):
            ExtractionService(
                ontology_repo=ontology_repo,
                embedding_service=embedding_service,
                llm=llm,
                nlp=nlp,
                reference_sources=reference_sources,
                event_publisher=event_publisher,
                extraction_repo=extraction_repo,
                similarity_threshold=1.5,  # Invalid: > 1.0
            )


class TestExtractionServiceDeduplication:
    """Test deduplication logic, especially reference enrichment."""

    def test_dedup_empty_list(self, service_with_fakes):
        """Test deduplication of empty list."""
        service = service_with_fakes["service"]
        result = service._deduplicate([])
        assert result == []

    def test_dedup_single_entity(self, service_with_fakes):
        """Test deduplication of single entity."""
        service = service_with_fakes["service"]
        entity = ExtractedEntity(
            label="Test",
            entity_type="ORG",
            source_layer=1,
            confidence=0.9,
        )
        result = service._deduplicate([entity])
        assert len(result) == 1
        assert result[0].label == "Test"

    def test_dedup_reference_enrichment_preferred(self, service_with_fakes):
        """Test that enriched entities from layer 3 are preferred over original."""
        service = service_with_fakes["service"]

        # Original entity from layer 1
        original = ExtractedEntity(
            id="entity-1",
            label="Apple",
            entity_type="ORG",
            source_layer=1,
            confidence=0.9,
            uri=None,
            description=None,
        )

        # Enriched copy from layer 3 with same ID
        enriched = ExtractedEntity(
            id="entity-1",  # SAME ID
            label="Apple",
            entity_type="ORG",
            source_layer=3,  # Reference layer
            confidence=0.9,
            uri="https://example.com/Apple",
            description="Technology company",
            properties={"reference_source": "TestSource"},
        )

        # Deduplicate
        result = service._deduplicate([original, enriched])

        # Should keep enriched version (has URI and description)
        assert len(result) == 1
        kept = result[0]
        assert kept.uri == "https://example.com/Apple"
        assert kept.description == "Technology company"
        assert "reference_source" in kept.properties

    def test_dedup_preserves_enrichment_data_merge(self, service_with_fakes):
        """Test that enrichment data is merged, not lost."""
        service = service_with_fakes["service"]

        # Original with some data
        original = ExtractedEntity(
            id="entity-2",
            label="Microsoft",
            entity_type="ORG",
            source_layer=1,
            confidence=0.85,
            uri=None,
            description="Software company",
            properties={"extracted_by": "llm"},
        )

        # Enriched with additional data
        enriched = ExtractedEntity(
            id="entity-2",
            label="Microsoft",
            entity_type="ORG",
            source_layer=3,
            confidence=0.85,
            uri="https://example.com/Microsoft",
            description="Multinational tech corporation",  # Better description
            properties={"reference_source": "DBpedia", "extracted_by": "llm"},
        )

        result = service._deduplicate([original, enriched])

        assert len(result) == 1
        kept = result[0]
        # Should have enriched URI
        assert kept.uri == "https://example.com/Microsoft"
        # Should have enriched description
        assert kept.description == "Multinational tech corporation"
        # Should have both property sources
        assert kept.properties["reference_source"] == "DBpedia"
        assert kept.properties["extracted_by"] == "llm"

    def test_dedup_priority_respects_layer_order(self, service_with_fakes):
        """Test that dedup respects layer priority order."""
        service = service_with_fakes["service"]

        # Layer 1 (LLM) - highest priority
        llm_entity = ExtractedEntity(
            id="entity-3",
            label="Google",
            entity_type="ORG",
            source_layer=1,
            confidence=0.95,
        )

        # Layer 0 (KG) - second priority
        kg_entity = ExtractedEntity(
            id="entity-3",
            label="Google",
            entity_type="ORG",
            source_layer=0,
            confidence=0.85,
        )

        # Deduplicate
        result = service._deduplicate([kg_entity, llm_entity])

        # Should keep layer 1 (higher priority) since there's no enrichment
        assert len(result) == 1
        assert result[0].source_layer == 1
        assert result[0].confidence == 0.95

    def test_dedup_label_similarity_threshold(self, service_with_fakes):
        """Test that label similarity respects the threshold."""
        service = service_with_fakes["service"]

        # Entities with very similar labels (Levenshtein distance = 1, similarity ~0.94)
        entity1 = ExtractedEntity(
            label="Microsoft",
            entity_type="ORG",
            source_layer=1,
            confidence=0.9,
        )

        entity2 = ExtractedEntity(
            label="Microsft",  # One character missing (Levenshtein distance = 1)
            entity_type="ORG",
            source_layer=2,
            confidence=0.85,
        )

        result = service._deduplicate([entity1, entity2])

        # With default threshold (0.85), should recognize as similar
        # (similarity = 1.0 - 1/9 = 0.889 >= 0.85)
        # and keep only the higher-priority one
        assert len(result) == 1
        assert result[0].label == "Microsoft"

    def test_dedup_multiple_entities_with_enrichment(self, service_with_fakes):
        """Test deduplication with multiple entities and selective enrichment."""
        service = service_with_fakes["service"]

        # Entity A from layer 1
        entity_a = ExtractedEntity(
            id="id-a",
            label="Apple",
            entity_type="ORG",
            source_layer=1,
            confidence=0.9,
        )

        # Entity B from layer 1
        entity_b = ExtractedEntity(
            id="id-b",
            label="Google",
            entity_type="ORG",
            source_layer=1,
            confidence=0.9,
        )

        # Enriched A from layer 3
        entity_a_enriched = ExtractedEntity(
            id="id-a",
            label="Apple",
            entity_type="ORG",
            source_layer=3,
            uri="https://example.com/Apple",
            description="Tech company",
            properties={"reference_source": "ConceptNet"},
        )

        # Deduplicate
        result = service._deduplicate([entity_a, entity_b, entity_a_enriched])

        assert len(result) == 2
        # Find enriched A
        enriched_a = next((e for e in result if e.id == "id-a"), None)
        assert enriched_a is not None
        assert enriched_a.uri == "https://example.com/Apple"

        # Find B (not enriched)
        b = next((e for e in result if e.id == "id-b"), None)
        assert b is not None
        assert b.uri is None


class TestExtractionServicePersistence:
    """Test persistence and error handling."""

    def test_extraction_returns_result_even_if_persistence_fails(
        self, service_with_fakes
    ):
        """Test that extraction returns result even if persistence fails."""
        service = service_with_fakes["service"]
        extraction_repo = service_with_fakes["extraction_repo"]

        # Make persistence fail

        def failing_save(result):
            raise RuntimeError("Database connection failed")

        extraction_repo.save_extraction_result = failing_save

        # Extraction should still return a result
        result = service.extract("Test text with Apple in it")

        assert isinstance(result, ExtractionResult)
        assert (
            len(result.extracted_entities) > 0
        )  # Has entities despite persistence failure
        # Event should still be published
        assert len(service_with_fakes["event_publisher"].published_events) > 0

    def test_extraction_event_published_even_if_persistence_fails(
        self, service_with_fakes
    ):
        """Test that completion event is published even if persistence fails."""
        service = service_with_fakes["service"]
        extraction_repo = service_with_fakes["extraction_repo"]
        event_publisher = service_with_fakes["event_publisher"]

        # Make persistence fail
        extraction_repo.save_extraction_result = Mock(
            side_effect=RuntimeError("DB error")
        )

        # Run extraction
        service.extract("Test text")

        # Event should still be published
        assert len(event_publisher.published_events) > 0
        from domain.extraction.events import ExtractionCompleted

        assert any(
            isinstance(e, ExtractionCompleted) for e in event_publisher.published_events
        )

    def test_analyze_text_returns_result_even_if_persistence_fails(
        self, service_with_fakes
    ):
        """Test that analyze_text returns result even if persistence fails."""
        service = service_with_fakes["service"]
        extraction_repo = service_with_fakes["extraction_repo"]

        extraction_repo.save_extraction_result = Mock(
            side_effect=RuntimeError("Database connection failed")
        )

        result = service.analyze_text("Test text about Steve Jobs")

        assert isinstance(result, ExtractionResult)
        assert len(service_with_fakes["event_publisher"].published_events) > 0

    def test_enrich_from_references_returns_result_even_if_persistence_fails(
        self, service_with_fakes
    ):
        """Test that enrich_from_references returns result even if persistence fails."""
        service = service_with_fakes["service"]
        extraction_repo = service_with_fakes["extraction_repo"]
        from domain.extraction.entities import ExtractedEntity as DomainEntity

        extraction_repo.save_extraction_result = Mock(
            side_effect=RuntimeError("Database connection failed")
        )

        entities = [
            DomainEntity(
                label="Apple", entity_type="ORG", source_layer=1, confidence=0.9
            )
        ]
        result = service.enrich_from_references("Apple is a tech company", entities)

        assert isinstance(result, ExtractionResult)
        assert len(service_with_fakes["event_publisher"].published_events) > 0

    def test_event_handler_failure_warning_logged(self, service_with_fakes):
        """Test that a warning is logged when an event handler fails."""
        from unittest.mock import patch

        fakes = service_with_fakes
        ontology_repo = fakes["ontology_repo"]
        embedding_service = fakes["embedding_service"]
        llm = fakes["llm"]
        nlp = fakes["nlp"]
        reference_sources = fakes["reference_sources"]
        extraction_repo = fakes["extraction_repo"]

        class FailingEventPublisher:
            """Event publisher that simulates a handler failure."""

            def publish(self, event) -> list[tuple[str, Exception]]:
                return [("audit_handler", RuntimeError("handler failed"))]

        service = ExtractionService(
            ontology_repo=ontology_repo,
            embedding_service=embedding_service,
            llm=llm,
            nlp=nlp,
            reference_sources=reference_sources,
            event_publisher=FailingEventPublisher(),
            extraction_repo=extraction_repo,
            similarity_threshold=0.85,
        )

        with patch("domain.extraction.services._logger") as mock_logger:
            result = service.extract("Test text")

        assert isinstance(result, ExtractionResult)
        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "Event handlers failed" in warning_msg


class TestExtractionServiceErrorHandling:
    """Test error handling and edge cases."""

    def test_empty_text_raises_error(self, service_with_fakes):
        """Test that empty text raises ExtractionError."""
        service = service_with_fakes["service"]

        with pytest.raises(ExtractionError):
            service.extract("")

        with pytest.raises(ExtractionError):
            service.extract("   ")

    def test_layer_failure_doesnt_stop_pipeline(self, service_with_fakes):
        """Test that a single layer failure doesn't stop the pipeline."""
        service = service_with_fakes["service"]
        nlp = service_with_fakes["nlp"]

        # Make NLP layer fail
        nlp.extract_entities = Mock(side_effect=RuntimeError("NLP model error"))

        # But LLM layer has ready() that returns False to trigger exception
        nlp.is_ready = Mock(return_value=False)

        # Extraction should still succeed with partial results
        result = service.extract("Test text")

        assert isinstance(result, ExtractionResult)
        # Some layers may have failed, but the result is still valid
        assert result.total_duration_ms >= 0

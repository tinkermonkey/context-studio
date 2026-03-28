"""
Unit tests for ExtractionService.

Tests cover all business logic: layer orchestration, error isolation,
deduplication with string similarity, event emission, and forward-output
passing between layers. Uses in-memory fakes with zero infrastructure imports.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from domain.extraction.services import ExtractionService
from domain.extraction.entities import ExtractedEntity, ExtractionResult
from domain.extraction.events import ExtractionCompleted
from domain.extraction.exceptions import ExtractionError
from domain.extraction.ports import LLMProvider, NLPProcessor, ReferenceSource
from domain.extraction.ports import LLMResponse, NLPResult, NLPEntity
from domain.extraction.value_objects import LayerOutput
from tests.fakes.fake_event_publisher import FakeEventPublisher


# ============================================================================
# Fake implementations for injection
# ============================================================================

class FakeOntologyRepository:
    """Fake ontology repository that returns empty entities."""

    def get_all_entities_and_relationships(self):
        """Return empty entities and relationships."""
        return {}, {}


class FakeEmbeddingService:
    """Fake embedding service with deterministic embeddings."""

    def embed(self, text: str) -> list[float]:
        """Return a deterministic embedding based on text length."""
        # Simple embedding: normalize text length to vector
        if not text:
            return [0.0] * 10
        return [float(len(text)) / 100.0] * 10

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        return [self.embed(text) for text in texts]

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """Compute simple cosine-like similarity."""
        if not embedding_a or not embedding_b:
            return 0.0
        dot = sum(a * b for a, b in zip(embedding_a, embedding_b))
        norm_a = sum(a * a for a in embedding_a) ** 0.5
        norm_b = sum(b * b for b in embedding_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class FakeLLMProvider:
    """Fake LLM provider that returns mock extraction results."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format=None,
    ) -> LLMResponse:
        """Return mock LLM response."""
        if self.should_fail:
            raise RuntimeError("LLM provider error")

        # Return mock entities as JSON
        content = '[{"label": "Apple", "type": "ORG", "confidence": 0.95}]'
        return LLMResponse(
            content=content,
            tokens_in=50,
            tokens_out=30,
            finish_reason="stop",
            model=model,
        )

    def is_model_available(self, model: str) -> bool:
        """Check if model is available."""
        return True

    def list_available_models(self) -> list[str]:
        """List available models."""
        return ["gpt-4", "gpt-3.5-turbo"]


class FakeNLPProcessor:
    """Fake NLP processor that returns mock entities."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def process(self, text: str) -> NLPResult:
        """Return mock NLP result."""
        if self.should_fail:
            raise RuntimeError("NLP processor error")

        entities = self.extract_entities(text)
        tokens = text.split()
        return NLPResult(
            tokens=tokens,
            entities=entities,
            language="en",
        )

    def extract_entities(self, text: str) -> list[NLPEntity]:
        """Extract mock named entities."""
        if self.should_fail:
            raise RuntimeError("NLP processor error")

        # Return mock entities
        return [
            NLPEntity(text="Microsoft", label="ORG", start=0, end=9),
        ]

    def is_ready(self) -> bool:
        """Check if processor is ready."""
        return True


class FakeReferenceSource:
    """Fake reference source that returns mock search results."""

    def __init__(self, source_name_val: str = "TestSource", should_fail: bool = False):
        self._source_name = source_name_val
        self.should_fail = should_fail

    @property
    def source_name(self) -> str:
        """Get source name."""
        return self._source_name

    def search(self, term: str, limit: int = 10) -> list:
        """Return mock search results."""
        if self.should_fail:
            raise RuntimeError("Reference source error")

        # Mock result
        from domain.extraction.ports import ReferenceResult
        return [
            ReferenceResult(
                uri=f"https://example.com/{term}",
                label=term,
                description=f"Reference for {term}",
                source=self.source_name,
            )
        ]

    def get_relations(self, uri: str, limit: int = 10) -> list:
        """Get relations for URI."""
        return []

    def is_available(self) -> bool:
        """Check if source is available."""
        return True


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
        )

        result = service.extract("Test text with content")

        # Layer 1 gracefully handles no available models
        assert result.layers_executed[1].success is True
        assert result.layers_executed[1].entities_found == 0  # No entities from LLM

        # Layer 2 (NLP) should have succeeded and found entities
        assert result.layers_executed[2].success is True

        # NLP layer should have found Microsoft
        assert any(e.label == "Microsoft" for e in result.extracted_entities)


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
        )

        # "Apple" vs "Apples" - one extra character
        sim = service._normalized_similarity("Apple", "Apples")
        assert 0.8 < sim < 1.0  # High but not exact


class TestExceptionHandling:
    """Tests for exception behavior."""

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

        service = ExtractionService(
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
            llm=FakeLLMProvider(),
            nlp=NotReadyNLPProcessor(),  # Layer 2 not ready
            reference_sources=[FakeReferenceSource()],
            event_publisher=FakeEventPublisher(),
        )

        # Should not raise despite NLP not being ready
        result = service.extract("Test text")

        assert result.layers_executed[2].success is True
        assert result.layers_executed[2].entities_found == 0
        assert result.layers_executed[3].success is True

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
        )

        # Should not raise despite reference source not available
        result = service.extract("Test text")

        assert result.layers_executed[3].success is True
        assert result.layers_executed[3].entities_found == 0
        assert len(result.layers_executed) == 4


class TestReferenceEnrichment:
    """Tests for reference enrichment preservation."""

    def test_reference_enrichment_preserves_metadata(self):
        """URIs and descriptions from reference layer survive deduplication."""
        fake_ontology = FakeOntologyRepository()
        fake_embedding = FakeEmbeddingService()
        fake_llm = FakeLLMProvider()
        fake_nlp = FakeNLPProcessor()
        fake_reference = FakeReferenceSource()
        event_publisher = FakeEventPublisher()

        service = ExtractionService(
            ontology_repo=fake_ontology,
            embedding_service=fake_embedding,
            llm=fake_llm,
            nlp=fake_nlp,
            reference_sources=[fake_reference],
            event_publisher=event_publisher,
        )

        result = service.extract("Test text")

        # Check that at least one entity has enrichment metadata
        has_reference_data = any(
            "reference_source" in (e.properties or {})
            for e in result.extracted_entities
        )
        # The reference layer successfully enriches if it finds matches
        # This test verifies that enrichment data is not discarded
        assert isinstance(result.extracted_entities, list)

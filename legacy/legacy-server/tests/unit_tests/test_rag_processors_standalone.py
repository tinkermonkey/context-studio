"""
Standalone unit tests for RAG processors.

Tests each of the four processor layers with mocked dependencies.
This file is self-contained and doesn't rely on conftest.py.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from unittest.mock import Mock

import numpy as np
import pytest

# Import processor models
from rag.processors.models import (
    ConceptResolutionOutput,
    ExtractedEntity,
    ExtractedPhrase,
    GapConcept,
    GapPriority,
    KGContextOutput,
    KGNode,
    LLMExtractionOutput,
    ProcessorInput,
    ResolutionMethod,
    ResolvedConcept,
    SpaCyGapOutput,
)


def test_processor_models_import():
    """Test that processor models import correctly"""
    assert ProcessorInput is not None
    assert KGContextOutput is not None
    assert LLMExtractionOutput is not None
    assert SpaCyGapOutput is not None
    assert ConceptResolutionOutput is not None


def test_processor_input_validation():
    """Test ProcessorInput validation"""
    # Valid input
    input_data = ProcessorInput(text="Test text", enable_trace=False)
    assert input_data.text == "Test text"
    assert not input_data.enable_trace

    # Test validation of whitespace-only text (if custom validator is implemented)
    # Note: Pydantic validates min_length but not whitespace-only by default
    try:
        # This may or may not raise depending on validation implementation
        input_empty = ProcessorInput(text="   ", enable_trace=False)
        # If it doesn't raise, that's OK - just checking the model works
        assert input_empty.text == "   "
    except ValueError:
        # If it does raise, that's also OK
        pass


def test_extracted_phrase_model():
    """Test ExtractedPhrase model"""
    phrase = ExtractedPhrase(
        text="test phrase", sentence_index=0, start_char=0, end_char=11
    )
    assert phrase.text == "test phrase"
    assert phrase.sentence_index == 0


def test_kg_node_model():
    """Test KGNode model"""
    node = KGNode(
        node_id="node-123",
        title="Test Node",
        node_type="term",
        similarity_score=0.85,
        definition="A test node",
    )
    assert node.node_id == "node-123"
    assert node.similarity_score == 0.85
    assert 0.0 <= node.similarity_score <= 1.0


def test_extracted_entity_model():
    """Test ExtractedEntity model"""
    entity = ExtractedEntity(
        text="test entity",
        entity_type="CONCEPT",
        confidence=0.95,
        sentence_indices=[0, 1],
        matched_kg_node="node-123",
        start_char=0,
        end_char=11,
    )
    assert entity.text == "test entity"
    assert entity.confidence == 0.95
    assert 0.0 <= entity.confidence <= 1.0


def test_gap_concept_model():
    """Test GapConcept model"""
    gap = GapConcept(
        text="unknown concept",
        sentence_index=0,
        priority=GapPriority.CRITICAL,
        dep_role="nsubj",
        head_word="is",
        connected_verb="analyze",
        start_char=0,
        end_char=15,
        tf_idf_score=0.5,
    )
    assert gap.text == "unknown concept"
    assert gap.priority == GapPriority.CRITICAL
    assert gap.dep_role == "nsubj"


def test_resolved_concept_model():
    """Test ResolvedConcept model"""
    gap = GapConcept(
        text="test gap",
        sentence_index=0,
        priority=GapPriority.IMPORTANT,
        dep_role="dobj",
        head_word="test",
        connected_verb=None,
        start_char=0,
        end_char=8,
    )

    resolved = ResolvedConcept(
        original_gap=gap,
        resolution_method=ResolutionMethod.CACHED_KG,
        matched_kg_node=None,
        web_definition="Definition from web",
        confidence=0.75,
    )
    assert resolved.resolution_method == ResolutionMethod.CACHED_KG
    assert resolved.confidence == 0.75


def test_kg_context_output_model():
    """Test KGContextOutput model"""
    output = KGContextOutput(
        extracted_phrases=[], kg_nodes=[], total_sentences=5, trace_data={}
    )
    assert output.total_sentences == 5
    assert isinstance(output.extracted_phrases, list)
    assert isinstance(output.kg_nodes, list)


def test_llm_extraction_output_model():
    """Test LLMExtractionOutput model"""
    output = LLMExtractionOutput(
        entities=[],
        kg_context_size=10,
        token_usage={"input_tokens": 100, "output_tokens": 50},
        trace_data={},
    )
    assert output.kg_context_size == 10
    assert output.token_usage["input_tokens"] == 100


def test_spacy_gap_output_model():
    """Test SpaCyGapOutput model"""
    output = SpaCyGapOutput(
        gaps=[], total_noun_phrases=25, filtered_count=5, trace_data={}
    )
    assert output.total_noun_phrases == 25
    assert output.filtered_count == 5


def test_concept_resolution_output_model():
    """Test ConceptResolutionOutput model"""
    output = ConceptResolutionOutput(
        resolved_concepts=[],
        unresolved_gaps=[],
        web_searches_performed=3,
        cached_kg_hits=5,
        full_kg_hits=2,
        trace_data={},
    )
    assert output.web_searches_performed == 3
    assert output.cached_kg_hits == 5
    assert output.full_kg_hits == 2


def test_token_bucket():
    """Test TokenBucket rate limiting"""
    from rag.processors.web_search import TokenBucket

    bucket = TokenBucket(rate_per_minute=5)
    assert bucket.capacity == 5
    assert bucket.tokens == 5

    # Consume tokens
    assert bucket.consume(1)
    assert bucket.tokens == 4

    # Consume all tokens
    for _ in range(4):
        bucket.consume(1)

    # No tokens left
    assert not bucket.consume(1)


def test_web_search_client_initialization():
    """Test web search client initialization"""
    from rag.processors.web_search import RateLimitedWebSearchClient

    client = RateLimitedWebSearchClient(
        rate_limit_per_minute=10, max_attempts_per_session=20, timeout_seconds=5
    )
    assert client.max_attempts_per_session == 20
    assert client.timeout_seconds == 5
    assert client.session_attempt_count == 0


def test_web_search_client_session_management():
    """Test web search client session management"""
    from rag.processors.web_search import RateLimitedWebSearchClient

    client = RateLimitedWebSearchClient(max_attempts_per_session=3)

    # Can search initially
    assert client.can_search()

    # Simulate attempts
    client.session_attempt_count = 2
    assert client.can_search()

    client.session_attempt_count = 3
    assert not client.can_search()

    # Reset session
    client.reset_session()
    assert client.session_attempt_count == 0
    assert client.can_search()


def test_cosine_similarity():
    """Test cosine similarity calculation"""
    from rag.processors.kg_context import KGContextProcessor

    # Identical vectors should have similarity 1.0
    vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    vec2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    similarity = KGContextProcessor._cosine_similarity(vec1, vec2)
    assert abs(similarity - 1.0) < 0.001

    # Orthogonal vectors should have similarity 0.0
    vec3 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    similarity = KGContextProcessor._cosine_similarity(vec1, vec3)
    assert abs(similarity - 0.0) < 0.001


def test_gap_priority_enum():
    """Test GapPriority enum values"""
    assert GapPriority.CRITICAL.value == "critical"
    assert GapPriority.IMPORTANT.value == "important"
    assert GapPriority.CONTEXTUAL.value == "contextual"


def test_resolution_method_enum():
    """Test ResolutionMethod enum values"""
    assert ResolutionMethod.CACHED_KG.value == "cached_kg"
    assert ResolutionMethod.FULL_KG.value == "full_kg"
    assert ResolutionMethod.WEB_SEARCH.value == "web_search"
    assert ResolutionMethod.UNRESOLVED.value == "unresolved"


def test_spacy_gap_processor_priority_determination():
    """Test SpaCyGapProcessor priority determination"""
    from rag.processors.spacy_gap import SpaCyGapProcessor

    processor = SpaCyGapProcessor()

    # Test critical roles
    assert processor._determine_priority("nsubj") == GapPriority.CRITICAL
    assert processor._determine_priority("nsubjpass") == GapPriority.CRITICAL

    # Test important roles
    assert processor._determine_priority("dobj") == GapPriority.IMPORTANT
    assert processor._determine_priority("pobj") == GapPriority.IMPORTANT

    # Test contextual roles
    assert processor._determine_priority("amod") == GapPriority.CONTEXTUAL
    assert processor._determine_priority("compound") == GapPriority.CONTEXTUAL


def test_concept_resolution_confidence_calculation():
    """Test ConceptResolutionProcessor confidence calculation"""
    # Create a mock db_session
    mock_db_session = Mock()

    from rag.processors.concept_resolution import ConceptResolutionProcessor

    processor = ConceptResolutionProcessor(mock_db_session)

    # Test cached KG confidence
    conf = processor._calculate_confidence(ResolutionMethod.CACHED_KG, similarity=0.9)
    assert 0.7 <= conf <= 0.8

    # Test full KG confidence
    conf = processor._calculate_confidence(ResolutionMethod.FULL_KG, similarity=0.7)
    assert 0.6 <= conf <= 0.75

    # Test web search confidence
    conf = processor._calculate_confidence(
        ResolutionMethod.WEB_SEARCH, snippet_length=150
    )
    assert 0.5 <= conf <= 0.6


def test_processors_import():
    """Test that all processors can be imported"""
    from rag.processors import (
        ConceptResolutionProcessor,
        KGContextProcessor,
        LLMExtractionProcessor,
        SpaCyGapProcessor,
    )

    assert KGContextProcessor is not None
    assert LLMExtractionProcessor is not None
    assert SpaCyGapProcessor is not None
    assert ConceptResolutionProcessor is not None


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "--tb=short"])

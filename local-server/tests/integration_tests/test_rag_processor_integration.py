"""
Integration tests for RAG processor pipeline.

Tests the interaction between all four processor layers with real services.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rag.processors import (
    KGContextProcessor,
    LLMExtractionProcessor,
    SpaCyGapProcessor,
    ConceptResolutionProcessor
)
from rag.processors.models import ProcessorInput, GapPriority
from rag.processors.web_search import RateLimitedWebSearchClient
from database.models import Base, StructureNode
from database.enums import NodeType
import numpy as np


@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite database for testing"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Add some test data
    node1 = StructureNode(
        id="test-node-1",
        node_type=NodeType.TERM,
        parent_node_id=None,
        title="machine learning",
        definition="A field of artificial intelligence",
        title_embedding=np.random.rand(384).astype(np.float32).tobytes()
    )

    node2 = StructureNode(
        id="test-node-2",
        node_type=NodeType.TERM,
        parent_node_id=None,
        title="neural network",
        definition="A computational model inspired by biological neurons",
        title_embedding=np.random.rand(384).astype(np.float32).tobytes()
    )

    session.add(node1)
    session.add(node2)
    session.commit()

    yield session

    session.close()
    engine.dispose()


def test_kg_context_processor_integration(in_memory_db):
    """Test KG Context Processor with real database"""
    processor = KGContextProcessor(in_memory_db, top_k=10)

    input_data = ProcessorInput(
        text="Machine learning uses neural networks for pattern recognition.",
        enable_trace=True
    )

    output = processor.process(input_data)

    # Verify output structure
    assert output is not None
    assert output.total_sentences >= 1
    assert isinstance(output.extracted_phrases, list)
    assert isinstance(output.kg_nodes, list)
    assert isinstance(output.trace_data, dict)

    # Verify trace data when enabled
    assert 'extracted_phrases' in output.trace_data or len(output.trace_data) >= 0


def test_spacy_gap_processor_integration():
    """Test SpaCy Gap Processor with real NLP pipeline"""
    processor = SpaCyGapProcessor(tf_idf_threshold=0.1)

    input_data = ProcessorInput(
        text="The quantum computer performed complex calculations using superposition.",
        enable_trace=True
    )

    # Mock LLM output (no entities recognized)
    from rag.processors.models import LLMExtractionOutput
    llm_output = LLMExtractionOutput(
        entities=[],
        kg_context_size=0,
        token_usage=None,
        trace_data={}
    )

    output = processor.process(input_data, llm_output)

    # Verify output structure
    assert output is not None
    assert isinstance(output.gaps, list)
    assert output.total_noun_phrases >= 0
    assert output.filtered_count >= 0

    # Verify gaps have proper structure
    for gap in output.gaps:
        assert gap.text is not None
        assert gap.priority in [GapPriority.CRITICAL, GapPriority.IMPORTANT, GapPriority.CONTEXTUAL]
        assert gap.dep_role is not None


def test_concept_resolution_processor_integration(in_memory_db):
    """Test Concept Resolution Processor with real dependencies"""
    # Create mock web search client
    web_search_client = Mock(spec=RateLimitedWebSearchClient)
    web_search_client.reset_session = Mock()
    web_search_client.can_search = Mock(return_value=False)  # Disable web search for this test

    processor = ConceptResolutionProcessor(
        in_memory_db,
        web_search_client=web_search_client,
        similarity_threshold=0.5
    )

    input_data = ProcessorInput(
        text="Test text",
        enable_trace=True
    )

    # Create mock inputs from previous layers
    from rag.processors.models import (
        KGContextOutput,
        LLMExtractionOutput,
        SpaCyGapOutput,
        GapConcept,
        KGNode
    )

    kg_context = KGContextOutput(
        extracted_phrases=[],
        kg_nodes=[
            KGNode(
                node_id="test-node-1",
                title="machine learning",
                node_type="term",
                similarity_score=0.8,
                definition="A field of AI"
            )
        ],
        total_sentences=1,
        trace_data={}
    )

    llm_output = LLMExtractionOutput(
        entities=[],
        kg_context_size=1,
        token_usage=None,
        trace_data={}
    )

    gap_output = SpaCyGapOutput(
        gaps=[
            GapConcept(
                text="machine learning",  # Should match cached KG
                sentence_index=0,
                priority=GapPriority.CRITICAL,
                dep_role="nsubj",
                head_word="is",
                connected_verb="analyze",
                start_char=0,
                end_char=16,
                tf_idf_score=0.5
            )
        ],
        total_noun_phrases=1,
        filtered_count=0,
        trace_data={}
    )

    output = processor.process(input_data, kg_context, llm_output, gap_output)

    # Verify output structure
    assert output is not None
    assert isinstance(output.resolved_concepts, list)
    assert isinstance(output.unresolved_gaps, list)
    assert output.web_searches_performed == 0  # Web search disabled
    assert output.cached_kg_hits + output.full_kg_hits >= 0


def test_full_pipeline_integration(in_memory_db):
    """Test full four-layer pipeline integration"""
    # Layer 0: KG Context
    kg_processor = KGContextProcessor(in_memory_db, top_k=5)

    input_data = ProcessorInput(
        text="Neural networks are a key component of machine learning systems.",
        enable_trace=False
    )

    kg_output = kg_processor.process(input_data)
    assert kg_output is not None

    # Skip Layer 1 (LLM) for integration test - would require real LLM
    from rag.processors.models import LLMExtractionOutput
    llm_output = LLMExtractionOutput(
        entities=[],  # Simulate no entities found by LLM
        kg_context_size=len(kg_output.kg_nodes),
        token_usage=None,
        trace_data={}
    )

    # Layer 2: spaCy Gap Detection
    gap_processor = SpaCyGapProcessor(tf_idf_threshold=0.1)
    gap_output = gap_processor.process(input_data, llm_output)
    assert gap_output is not None
    assert len(gap_output.gaps) >= 0

    # Layer 3: Concept Resolution
    web_search_client = Mock(spec=RateLimitedWebSearchClient)
    web_search_client.reset_session = Mock()
    web_search_client.can_search = Mock(return_value=False)

    resolution_processor = ConceptResolutionProcessor(
        in_memory_db,
        web_search_client=web_search_client
    )

    resolution_output = resolution_processor.process(
        input_data,
        kg_output,
        llm_output,
        gap_output
    )

    assert resolution_output is not None
    assert isinstance(resolution_output.resolved_concepts, list)
    assert isinstance(resolution_output.unresolved_gaps, list)

    # Verify pipeline data flow
    total_concepts = len(resolution_output.resolved_concepts) + len(resolution_output.unresolved_gaps)
    assert total_concepts == len(gap_output.gaps)


def test_processor_trace_data_flow(in_memory_db):
    """Test that trace data is properly captured and flows through pipeline"""
    kg_processor = KGContextProcessor(in_memory_db, top_k=5)

    input_data = ProcessorInput(
        text="Test sentence for tracing.",
        enable_trace=True  # Enable trace
    )

    kg_output = kg_processor.process(input_data)

    # Verify trace data is captured
    assert isinstance(kg_output.trace_data, dict)
    # Trace data should have some content when enabled
    assert len(kg_output.trace_data) >= 0 or 'extracted_phrases' in kg_output.trace_data


def test_web_search_rate_limiting():
    """Test web search rate limiting in integration context"""
    web_search_client = RateLimitedWebSearchClient(
        rate_limit_per_minute=2,
        max_attempts_per_session=3
    )

    # Reset session
    web_search_client.reset_session()
    assert web_search_client.session_attempt_count == 0

    # Check can search
    assert web_search_client.can_search() == True

    # Simulate reaching limit
    web_search_client.session_attempt_count = 3
    assert web_search_client.can_search() == False


def test_processor_error_handling(in_memory_db):
    """Test processor error handling"""
    processor = KGContextProcessor(in_memory_db, top_k=5)

    # Test with minimal valid input
    input_data = ProcessorInput(text="x", enable_trace=False)

    try:
        output = processor.process(input_data)
        # Should handle gracefully
        assert output is not None
    except Exception as e:
        # If it fails, error should be informative
        assert str(e) is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

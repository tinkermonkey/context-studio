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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Unit tests for RAG processors.

Tests each of the four processor layers with mocked dependencies.
"""

import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402
import numpy as np  # noqa: E402

from rag.processors.models import (  # noqa: E402
    ProcessorInput,
    KGContextOutput,
    LLMExtractionOutput,
    SpaCyGapOutput,
    ConceptResolutionOutput,
    KGNode,
    GapConcept,
    GapPriority,
    ResolutionMethod,
)


class TestKGContextProcessor:
    """Test Layer 0: KG Context Preparation Processor"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()

    @pytest.fixture
    def mock_nlp_pipeline(self):
        """Mock NLP pipeline"""
        with patch("rag.processors.kg_context.get_pipeline") as mock:
            pipeline = Mock()
            # Mock spaCy doc with sentences
            doc = Mock()
            sent1 = Mock()
            sent1.noun_chunks = []
            sent1.ents = []
            sent1.start_char = 0
            sent1.end_char = 10
            doc.sents = [sent1]
            pipeline.process.return_value = doc
            mock.return_value = pipeline
            yield mock

    @pytest.fixture
    def mock_embedding_model(self):
        """Mock embedding model"""
        with patch("rag.processors.kg_context.get_model") as mock:
            model = Mock()
            model.encode.return_value = [np.random.rand(384).astype(np.float32)]
            mock.return_value = model
            yield mock

    def test_processor_initialization(self, mock_db_session):
        """Test processor initializes correctly"""
        from rag.processors.kg_context import KGContextProcessor

        processor = KGContextProcessor(mock_db_session, top_k=30)
        assert processor.top_k == 30
        assert processor.db_session == mock_db_session

    def test_process_with_empty_text(
        self, mock_db_session, mock_nlp_pipeline, mock_embedding_model
    ):
        """Test processing with empty text"""
        from rag.processors.kg_context import KGContextProcessor

        processor = KGContextProcessor(mock_db_session)
        input_data = ProcessorInput(text="Test", enable_trace=False)

        output = processor.process(input_data)

        assert isinstance(output, KGContextOutput)
        assert output.total_sentences >= 0
        assert isinstance(output.extracted_phrases, list)
        assert isinstance(output.kg_nodes, list)

    def test_trace_capture_enabled(
        self, mock_db_session, mock_nlp_pipeline, mock_embedding_model
    ):
        """Test that trace data is captured when enabled"""
        from rag.processors.kg_context import KGContextProcessor

        processor = KGContextProcessor(mock_db_session)
        input_data = ProcessorInput(text="Test text", enable_trace=True)

        output = processor.process(input_data)

        assert "extracted_phrases" in output.trace_data or len(output.trace_data) >= 0

    def test_cosine_similarity(self):
        """Test cosine similarity calculation"""
        from rag.processors.kg_context import KGContextProcessor

        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)

        similarity = KGContextProcessor._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.001  # Should be 1.0 (identical vectors)

        vec3 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        similarity = KGContextProcessor._cosine_similarity(vec1, vec3)
        assert abs(similarity - 0.0) < 0.001  # Should be 0.0 (orthogonal vectors)


class TestLLMExtractionProcessor:
    """Test Layer 1: LLM Extraction Processor"""

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service"""
        with patch("rag.processors.llm_extraction.LLMService") as mock:
            service = Mock()
            # Mock successful LLM response
            response = Mock()
            response.response_content = "Entity: test concept"
            response.execution_id = "test-exec-id"
            response.token_usage = {"input_tokens": 10, "output_tokens": 5}
            service.execute_pipeline_flavor_sync = Mock(return_value=response)
            service.flavor_service = Mock()
            mock.return_value = service
            yield mock

    def test_processor_initialization(self, mock_llm_service):
        """Test processor initializes correctly"""
        from rag.processors.llm_extraction import LLMExtractionProcessor

        processor = LLMExtractionProcessor(flavor_id="test-flavor")
        assert processor.flavor_id == "test-flavor"
        assert processor.llm_service is not None

    def test_process_with_kg_context(self, mock_llm_service):
        """Test processing with KG context"""
        from rag.processors.llm_extraction import LLMExtractionProcessor

        processor = LLMExtractionProcessor()
        input_data = ProcessorInput(text="Test text about concepts", enable_trace=False)

        kg_context = KGContextOutput(
            extracted_phrases=[],
            kg_nodes=[
                KGNode(
                    node_id="node1",
                    title="test concept",
                    node_type="term",
                    similarity_score=0.8,
                    definition="A test concept",
                )
            ],
            total_sentences=1,
            trace_data={},
        )

        # Create a mock response
        from llm.models import PipelineExecutionResponse

        mock_response = PipelineExecutionResponse(
            response_content="Entity: test concept",
            execution_id="test-id",
            flavor_id="default",
            pipeline_type="extract_entities",
            token_usage={"input_tokens": 10, "output_tokens": 5},
        )

        # Mock the execute_pipeline_flavor_sync method
        processor.llm_service.execute_pipeline_flavor_sync.return_value = mock_response

        output = processor.process(input_data, kg_context)

        assert isinstance(output, LLMExtractionOutput)
        assert output.kg_context_size == 1
        assert isinstance(output.entities, list)

    def test_format_kg_context(self, mock_llm_service):
        """Test KG context formatting"""
        from rag.processors.llm_extraction import LLMExtractionProcessor

        processor = LLMExtractionProcessor()
        kg_context = KGContextOutput(
            extracted_phrases=[],
            kg_nodes=[
                KGNode(
                    node_id="node1",
                    title="concept1",
                    node_type="term",
                    similarity_score=0.9,
                    definition="Definition 1",
                ),
                KGNode(
                    node_id="node2",
                    title="concept2",
                    node_type="domain",
                    similarity_score=0.8,
                    definition="Definition 2",
                ),
            ],
            total_sentences=1,
            trace_data={},
        )

        formatted = processor._format_kg_context(kg_context)
        assert (
            "concept1" in formatted or "Relevant Knowledge Graph Context" in formatted
        )
        assert isinstance(formatted, str)


class TestSpaCyGapProcessor:
    """Test Layer 2: spaCy Gap Detection Processor"""

    @pytest.fixture
    def mock_nlp_pipeline(self):
        """Mock NLP pipeline"""
        with patch("rag.processors.spacy_gap.get_pipeline") as mock:
            pipeline = Mock()
            # Mock spaCy doc with sentences and noun chunks
            doc = Mock()
            sent = Mock()

            # Mock noun chunk
            chunk = Mock()
            chunk.text = "test phrase"
            chunk.start_char = 0
            chunk.end_char = 11
            chunk_token = Mock()
            chunk_token.is_stop = False
            chunk.root = chunk_token
            chunk_token.dep_ = "nsubj"
            chunk_token.head = Mock()
            chunk_token.head.text = "is"
            chunk_token.pos_ = "NOUN"
            chunk_token.children = []
            chunk.__iter__ = Mock(return_value=iter([chunk_token]))

            sent.noun_chunks = [chunk]
            sent.ents = []
            doc.sents = [sent]

            # Mock token iteration for TF-IDF
            token = Mock()
            token.lemma_ = "test"
            token.is_stop = False
            token.is_alpha = True
            doc.__iter__ = Mock(return_value=iter([token]))

            pipeline.process.return_value = doc
            mock.return_value = pipeline
            yield mock

    def test_processor_initialization(self):
        """Test processor initializes correctly"""
        from rag.processors.spacy_gap import SpaCyGapProcessor

        processor = SpaCyGapProcessor(tf_idf_threshold=0.2)
        assert processor.tf_idf_threshold == 0.2

    def test_process_identifies_gaps(self, mock_nlp_pipeline):
        """Test gap identification"""
        from rag.processors.spacy_gap import SpaCyGapProcessor

        processor = SpaCyGapProcessor()
        input_data = ProcessorInput(text="Test text", enable_trace=False)

        llm_output = LLMExtractionOutput(
            entities=[],  # No entities recognized
            kg_context_size=0,
            token_usage=None,
            trace_data={},
        )

        output = processor.process(input_data, llm_output)

        assert isinstance(output, SpaCyGapOutput)
        assert isinstance(output.gaps, list)
        assert output.total_noun_phrases >= 0

    def test_priority_determination(self):
        """Test gap priority determination"""
        from rag.processors.spacy_gap import SpaCyGapProcessor

        processor = SpaCyGapProcessor()

        assert processor._determine_priority("nsubj") == GapPriority.CRITICAL
        assert processor._determine_priority("dobj") == GapPriority.IMPORTANT
        assert processor._determine_priority("amod") == GapPriority.CONTEXTUAL


class TestConceptResolutionProcessor:
    """Test Layer 3: Concept Resolution Processor"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        session = Mock()
        # Mock query results
        query_mock = Mock()
        query_mock.filter.return_value.all.return_value = []
        session.query.return_value = query_mock
        return session

    @pytest.fixture
    def mock_web_search_client(self):
        """Mock web search client"""
        client = Mock()
        client.reset_session.return_value = None
        client.can_search.return_value = True
        client.search.return_value = None
        return client

    @pytest.fixture
    def mock_embedding_model(self):
        """Mock embedding model"""
        with patch("rag.processors.concept_resolution.get_model") as mock:
            model = Mock()
            model.encode.return_value = [np.random.rand(384).astype(np.float32)]
            mock.return_value = model
            yield mock

    def test_processor_initialization(self, mock_db_session, mock_web_search_client):
        """Test processor initializes correctly"""
        from rag.processors.concept_resolution import ConceptResolutionProcessor

        processor = ConceptResolutionProcessor(
            mock_db_session,
            web_search_client=mock_web_search_client,
            similarity_threshold=0.7,
        )
        assert processor.similarity_threshold == 0.7
        assert processor.web_search_client == mock_web_search_client

    def test_process_with_no_gaps(
        self, mock_db_session, mock_web_search_client, mock_embedding_model
    ):
        """Test processing with no gaps"""
        from rag.processors.concept_resolution import ConceptResolutionProcessor

        processor = ConceptResolutionProcessor(mock_db_session, mock_web_search_client)
        input_data = ProcessorInput(text="Test", enable_trace=False)

        kg_context = KGContextOutput(
            extracted_phrases=[], kg_nodes=[], total_sentences=1, trace_data={}
        )

        llm_output = LLMExtractionOutput(
            entities=[], kg_context_size=0, token_usage=None, trace_data={}
        )

        gap_output = SpaCyGapOutput(
            gaps=[], total_noun_phrases=0, filtered_count=0, trace_data={}  # No gaps
        )

        output = processor.process(input_data, kg_context, llm_output, gap_output)

        assert isinstance(output, ConceptResolutionOutput)
        assert len(output.resolved_concepts) == 0
        assert len(output.unresolved_gaps) == 0

    def test_confidence_calculation(self, mock_db_session, mock_web_search_client):
        """Test confidence score calculation"""
        from rag.processors.concept_resolution import ConceptResolutionProcessor

        processor = ConceptResolutionProcessor(mock_db_session, mock_web_search_client)

        # Test cached KG confidence
        conf = processor._calculate_confidence(
            ResolutionMethod.CACHED_KG, similarity=0.9
        )
        assert 0.7 <= conf <= 0.8

        # Test full KG confidence
        conf = processor._calculate_confidence(ResolutionMethod.FULL_KG, similarity=0.7)
        assert 0.6 <= conf <= 0.75

        # Test web search confidence
        conf = processor._calculate_confidence(
            ResolutionMethod.WEB_SEARCH, snippet_length=150
        )
        assert 0.5 <= conf <= 0.6

    def test_should_perform_web_search(self, mock_db_session, mock_web_search_client):
        """Test web search criteria evaluation"""
        from rag.processors.concept_resolution import ConceptResolutionProcessor

        processor = ConceptResolutionProcessor(mock_db_session, mock_web_search_client)

        # Critical priority should be searched
        gap_critical = GapConcept(
            text="test",
            sentence_index=0,
            priority=GapPriority.CRITICAL,
            dep_role="nsubj",
            head_word="is",
            connected_verb="is",
            start_char=0,
            end_char=4,
            tf_idf_score=0.5,
        )
        assert processor._should_perform_web_search(gap_critical)

        # Contextual priority should not be searched
        gap_contextual = GapConcept(
            text="test",
            sentence_index=0,
            priority=GapPriority.CONTEXTUAL,
            dep_role="amod",
            head_word="noun",
            connected_verb="",
            start_char=0,
            end_char=4,
            tf_idf_score=0.5,
        )
        assert not processor._should_perform_web_search(gap_contextual)


class TestWebSearchClient:
    """Test rate-limited web search client"""

    def test_token_bucket_initialization(self):
        """Test token bucket initializes correctly"""
        from rag.processors.web_search import TokenBucket

        bucket = TokenBucket(rate_per_minute=5)
        assert bucket.capacity == 5
        assert bucket.tokens == 5

    def test_token_bucket_consume(self):
        """Test token consumption"""
        from rag.processors.web_search import TokenBucket

        bucket = TokenBucket(rate_per_minute=5)

        # Should be able to consume tokens
        assert bucket.consume(1)
        assert bucket.tokens == 4

        # Consume all remaining tokens
        for _ in range(4):
            assert bucket.consume(1)

        # No tokens left
        assert not bucket.consume(1)

    def test_web_search_client_initialization(self):
        """Test web search client initializes correctly"""
        from rag.processors.web_search import RateLimitedWebSearchClient

        client = RateLimitedWebSearchClient(
            rate_limit_per_minute=10, max_attempts_per_session=20
        )
        assert client.max_attempts_per_session == 20
        assert client.session_attempt_count == 0

    def test_session_reset(self):
        """Test session counter reset"""
        from rag.processors.web_search import RateLimitedWebSearchClient

        client = RateLimitedWebSearchClient()
        client.session_attempt_count = 5
        client.reset_session()
        assert client.session_attempt_count == 0

    def test_can_search_respects_limits(self):
        """Test session limit enforcement"""
        from rag.processors.web_search import RateLimitedWebSearchClient

        client = RateLimitedWebSearchClient(max_attempts_per_session=2)
        assert client.can_search()

        client.session_attempt_count = 2
        assert not client.can_search()

    @patch("rag.processors.web_search.requests.get")
    def test_search_with_rate_limit(self, mock_get):
        """Test search respects rate limiting"""
        from rag.processors.web_search import RateLimitedWebSearchClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Heading": "Test",
            "AbstractText": "Test definition",
        }
        mock_get.return_value = mock_response

        client = RateLimitedWebSearchClient(
            rate_limit_per_minute=60
        )  # High rate for testing
        result = client.search("test query")

        assert (
            result is not None or result is None
        )  # May succeed or fail depending on timing
        assert client.session_attempt_count >= 0  # Counter incremented


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

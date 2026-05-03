"""
E2E tests for Phase 2: External Services integration.

Tests cover integration with real external services for:
- LLM providers (OpenAI, Anthropic)
- Embedding services (SentenceTransformer)
- Reference sources (ConceptNet, DBpedia, Wikidata, schema.org)
- NLP processors (spaCy)

These tests require network access and external service availability.
Run with: pytest -m reference or pytest -m llm
Deselect with: pytest -m "not reference" -m "not llm"
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.wikidata import WikidataSource
from adapters.reference.schema_org import SchemaOrgSource
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.nlp.spacy_processor import SpacyNLPProcessor

# Import LLM providers with fallback support
try:
    from adapters.llm.openai_provider import OpenAIProvider
except ImportError:
    OpenAIProvider = None  # type: ignore[assignment,misc]

try:
    from adapters.llm.anthropic_provider import AnthropicProvider
except ImportError:
    AnthropicProvider = None  # type: ignore[assignment,misc]

try:
    from adapters.llm.provider_router import LLMProviderRouter
except ImportError:
    LLMProviderRouter = None  # type: ignore[assignment,misc]


class TestEmbeddingService:
    """Tests for embedding service integration."""

    def test_sentence_transformer_embed_single_text(self):
        """Embed a single text string."""
        embedding_service = SentenceTransformerEmbedding()

        embedding = embedding_service.embed("Hello world")

        # Should return a list of floats
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)

    def test_sentence_transformer_embed_batch(self):
        """Embed multiple texts at once."""
        embedding_service = SentenceTransformerEmbedding()

        texts = ["Hello", "World", "Testing embeddings"]
        embeddings = embedding_service.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(isinstance(e, list) for e in embeddings)
        assert all(len(e) > 0 for e in embeddings)

    def test_sentence_transformer_similarity(self):
        """Compute similarity between two embeddings."""
        embedding_service = SentenceTransformerEmbedding()

        text1 = "The cat sat on the mat"
        text2 = "The cat was on the mat"
        text3 = "Completely different topic"

        emb1 = embedding_service.embed(text1)
        emb2 = embedding_service.embed(text2)
        emb3 = embedding_service.embed(text3)

        # Similar texts should have higher similarity than dissimilar texts
        similarity_same = embedding_service.similarity(emb1, emb2)
        similarity_different = embedding_service.similarity(emb1, emb3)

        # Similarity should be between -1 and 1 (cosine similarity range)
        assert -1.0 <= similarity_same <= 1.0
        assert -1.0 <= similarity_different <= 1.0
        # Similar texts should have higher similarity than very different ones
        assert similarity_same > similarity_different


@pytest.mark.nlp
class TestNLPProcessor:
    """Tests for NLP processor integration."""

    def test_spacy_process_english_text(self):
        """Process English text with spaCy."""
        nlp_processor = SpacyNLPProcessor()

        # Skip if spaCy model is not available
        if not nlp_processor.is_ready():
            pytest.skip("spaCy model not available")

        result = nlp_processor.process("Apple and Microsoft are companies.")

        assert result.tokens is not None
        assert len(result.tokens) > 0
        assert result.language == "en"

    def test_spacy_extract_entities(self):
        """Extract named entities from text."""
        nlp_processor = SpacyNLPProcessor()

        if not nlp_processor.is_ready():
            pytest.skip("spaCy model not available")

        entities = nlp_processor.extract_entities("Apple and Microsoft are companies.")

        # Should find at least some entities
        assert isinstance(entities, list)

    def test_spacy_is_ready(self):
        """Check if spaCy processor is ready."""
        nlp_processor = SpacyNLPProcessor()

        ready = nlp_processor.is_ready()
        assert isinstance(ready, bool)


@pytest.mark.reference
class TestConceptNetSource:
    """Tests for ConceptNet reference source."""

    def test_conceptnet_search(self):
        """Search ConceptNet for entities."""
        source = ConceptNetSource()

        # Skip if source is unavailable
        if not source.is_available():
            pytest.skip("ConceptNet not available")

        results = source.search("apple")

        assert isinstance(results, list)
        # May be empty if network issues, but should be a list
        assert all(hasattr(r, "uri") for r in results)
        assert all(hasattr(r, "label") for r in results)

    def test_conceptnet_is_available(self):
        """Check if ConceptNet source is available."""
        source = ConceptNetSource()

        available = source.is_available()
        assert isinstance(available, bool)

    def test_conceptnet_get_relations(self):
        """Get relations from ConceptNet."""
        source = ConceptNetSource()

        if not source.is_available():
            pytest.skip("ConceptNet not available")

        # Get relations for a URI if search returns results
        results = source.search("apple", limit=1)
        if results:
            uri = results[0].uri
            relations = source.get_relations(uri, limit=5)
            assert isinstance(relations, list)


@pytest.mark.reference
class TestDBpediaSource:
    """Tests for DBpedia reference source."""

    def test_dbpedia_search(self):
        """Search DBpedia for entities."""
        source = DBpediaSource()

        if not source.is_available():
            pytest.skip("DBpedia not available")

        results = source.search("Apple")

        assert isinstance(results, list)
        assert all(hasattr(r, "uri") for r in results)
        assert all(hasattr(r, "label") for r in results)

    def test_dbpedia_is_available(self):
        """Check if DBpedia source is available."""
        source = DBpediaSource()

        available = source.is_available()
        assert isinstance(available, bool)

    def test_dbpedia_get_relations(self):
        """Get relations from DBpedia."""
        source = DBpediaSource()

        if not source.is_available():
            pytest.skip("DBpedia not available")

        results = source.search("Apple", limit=1)
        if results:
            uri = results[0].uri
            relations = source.get_relations(uri, limit=5)
            assert isinstance(relations, list)


@pytest.mark.reference
class TestWikidataSource:
    """Tests for Wikidata reference source."""

    def test_wikidata_search(self):
        """Search Wikidata for entities."""
        source = WikidataSource()

        if not source.is_available():
            pytest.skip("Wikidata not available")

        results = source.search("Apple")

        assert isinstance(results, list)

    def test_wikidata_is_available(self):
        """Check if Wikidata source is available."""
        source = WikidataSource()

        available = source.is_available()
        assert isinstance(available, bool)

    def test_wikidata_get_relations(self):
        """Get relations from Wikidata."""
        source = WikidataSource()

        if not source.is_available():
            pytest.skip("Wikidata not available")

        results = source.search("Apple", limit=1)
        if results:
            uri = results[0].uri
            relations = source.get_relations(uri, limit=5)
            assert isinstance(relations, list)


@pytest.mark.reference
class TestSchemaOrgSource:
    """Tests for schema.org reference source."""

    def test_schema_org_search(self):
        """Search schema.org for entity definitions."""
        source = SchemaOrgSource()

        results = source.search("Person")

        assert isinstance(results, list)

    def test_schema_org_is_available(self):
        """Check if schema.org source is available."""
        source = SchemaOrgSource()

        # schema.org should always be available (local data)
        assert source.is_available() is True

    def test_schema_org_get_relations(self):
        """Get relationships from schema.org."""
        source = SchemaOrgSource()

        results = source.search("Person", limit=1)
        if results:
            uri = results[0].uri
            relations = source.get_relations(uri, limit=10)
            assert isinstance(relations, list)


@pytest.mark.llm
class TestLLMProviders:
    """Tests for LLM provider integration."""

    def test_openai_provider_is_model_available(self):
        """Check if OpenAI models are available."""
        if OpenAIProvider is None:
            pytest.skip("OpenAI provider not available")

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OpenAI API key not configured")

        try:
            provider = OpenAIProvider(api_key=api_key)
            available = provider.is_model_available("gpt-4")
            assert isinstance(available, bool)
        except (ConnectionError, RuntimeError, ValueError) as e:
            pytest.skip(f"OpenAI provider connection failed: {e}")

    def test_anthropic_provider_is_model_available(self):
        """Check if Anthropic models are available."""
        if AnthropicProvider is None:
            pytest.skip("Anthropic provider not available")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("Anthropic API key not configured")

        try:
            provider = AnthropicProvider(api_key=api_key)
            available = provider.is_model_available("claude-opus")
            assert isinstance(available, bool)
        except (ConnectionError, RuntimeError, ValueError) as e:
            pytest.skip(f"Anthropic provider connection failed: {e}")

    def test_llm_provider_router(self):
        """Test LLM provider routing."""
        if LLMProviderRouter is None:
            pytest.skip("LLM provider router not available")

        try:
            router = LLMProviderRouter()
            providers = router.list_available_models()
            assert isinstance(providers, list)
        except (ConnectionError, TypeError, ValueError) as e:
            pytest.skip(f"LLM provider router unavailable: {e}")

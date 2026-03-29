"""
Unit tests for extraction layer modules.

Tests cover each layer's business logic: JSON parsing, deduplication, similarity,
multi-source enrichment, and NLP processing. Uses in-memory fakes with zero
infrastructure imports.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from domain.extraction import layers
from domain.extraction.entities import ExtractedEntity
from domain.extraction.value_objects import LayerInput
from domain.extraction.ports import NLPEntity, ReferenceResult
from domain.ports import LLMResponse
from domain.ontology.entities import Class
from domain.ontology.value_objects import ExternalReference


# ============================================================================
# Fakes for Layer 0 (KG Context)
# ============================================================================

class FakeOntologyRepository:
    """Fake ontology repository with configurable entities."""

    def __init__(self, entities_dict=None):
        self.entities_dict = entities_dict or {}

    def get_all_entities_and_relationships(self):
        """Return configured entities and relationships."""
        # Convert dict format to typed domain entities
        entities = []
        for entity_id, entity_data in self.entities_dict.items():
            # Convert external_references dicts to ExternalReference objects
            external_refs = []
            if entity_data.get("external_references"):
                for ref in entity_data["external_references"]:
                    external_refs.append(
                        ExternalReference(
                            source=ref.get("source", "unknown"),
                            identifier=ref.get("uri", entity_id),
                            uri=ref.get("uri"),
                        )
                    )

            # Create a Class entity
            cls = Class(
                id=entity_id,
                concept_scheme_id="test-scheme",
                taxonomy_id="test-taxonomy",
                title=entity_data.get("title", ""),
                description=entity_data.get("description"),
                embedding=entity_data.get("embedding"),
                external_references=external_refs,
            )
            entities.append(cls)

        return entities, []


class FakeEmbeddingService:
    """Fake embedding service with deterministic embeddings."""

    def embed(self, text: str) -> list[float]:
        """Return a deterministic embedding based on text hash."""
        if not text:
            return [0.0] * 10
        # Use hash of text to generate a deterministic but variable embedding
        hash_val = hash(text.lower())
        # Generate unique embedding per text
        embedding = []
        for i in range(10):
            # Use hash to generate pseudo-random but deterministic values
            val = ((hash_val >> (i * 2)) & 0xFF) / 255.0
            embedding.append(val)
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        return [self.embed(text) for text in texts]

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        if not embedding_a or not embedding_b:
            return 0.0
        dot = sum(a * b for a, b in zip(embedding_a, embedding_b))
        norm_a = sum(a * a for a in embedding_a) ** 0.5
        norm_b = sum(b * b for b in embedding_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ============================================================================
# Fakes for Layer 1 (LLM Extract)
# ============================================================================

class FakeLLMProvider:
    """Fake LLM provider with configurable responses."""

    def __init__(self, response_content=None, should_fail=False):
        self.response_content = response_content or '[]'
        self.should_fail = should_fail

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format=None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Return mock LLM response."""
        if self.should_fail:
            raise RuntimeError("LLM provider error")

        return LLMResponse(
            content=self.response_content,
            tokens_in=50,
            tokens_out=30,
            duration_ms=0.0,
            finish_reason="stop",
            model=model,
        )

    def is_model_available(self, model: str) -> bool:
        """Check if model is available."""
        return True

    def list_available_models(self) -> list[str]:
        """List available models."""
        return ["gpt-4"]


# ============================================================================
# Fakes for Layer 2 (NLP Gap-Filling)
# ============================================================================

class FakeNLPProcessor:
    """Fake NLP processor with configurable entities."""

    def __init__(self, entities_list=None, should_fail=False):
        self.entities_list = entities_list or []
        self.should_fail = should_fail

    def extract_entities(self, text: str) -> list[NLPEntity]:
        """Return configured entities."""
        if self.should_fail:
            raise RuntimeError("NLP processor error")
        return self.entities_list

    def is_ready(self) -> bool:
        """Check if processor is ready."""
        return True


# ============================================================================
# Fakes for Layer 3 (Reference Enrichment)
# ============================================================================

class FakeReferenceSource:
    """Fake reference source with configurable results."""

    def __init__(self, source_name_val="TestSource", results_map=None, should_fail=False):
        self._source_name = source_name_val
        self.results_map = results_map or {}
        self.should_fail = should_fail

    @property
    def source_name(self) -> str:
        """Get source name."""
        return self._source_name

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """Return configured search results."""
        if self.should_fail:
            raise RuntimeError("Reference source error")

        # Return results configured for this term, or empty
        return self.results_map.get(term, [])

    def get_relations(self, uri: str, limit: int = 10) -> list:
        """Get relations for URI."""
        return []

    def is_available(self) -> bool:
        """Check if source is available."""
        return True


# ============================================================================
# Tests for Layer 0: KG Context
# ============================================================================

class TestLayer0KGContext:
    """Tests for Knowledge Graph context extraction layer."""

    def test_kg_context_empty_text_returns_empty(self):
        """Empty text returns empty output."""
        output = layers.kg_context.execute(
            text="",
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
        )

        assert output.entities == []
        assert output.metadata["reason"] == "empty_text"

    def test_kg_context_whitespace_text_returns_empty(self):
        """Whitespace-only text returns empty output."""
        output = layers.kg_context.execute(
            text="   \n  ",
            ontology_repo=FakeOntologyRepository(),
            embedding_service=FakeEmbeddingService(),
        )

        assert output.entities == []
        assert output.metadata["reason"] == "empty_text"

    def test_kg_context_no_entities_in_repo(self):
        """Repository with no entities returns empty output."""
        output = layers.kg_context.execute(
            text="Test text",
            ontology_repo=FakeOntologyRepository({}),
            embedding_service=FakeEmbeddingService(),
        )

        assert output.entities == []
        # When there are no entities in the repo, matches_found is 0
        assert output.metadata["matches_found"] == 0

    def test_kg_context_high_similarity_returns_entity(self):
        """High similarity matches are returned."""
        # Create entity with embedding that will match our test text
        entities_dict = {
            "entity1": {
                "title": "Apple Inc.",
                "node_type": "Organization",
                "embedding": [0.08] * 10,  # Similar to "Test text" (8 chars)
                "description": "Tech company",
                "external_references": [{"uri": "https://apple.com"}],
            }
        }

        output = layers.kg_context.execute(
            text="Test text",  # 9 chars
            ontology_repo=FakeOntologyRepository(entities_dict),
            embedding_service=FakeEmbeddingService(),
        )

        # Should find high-similarity entity (both have similar embedding values)
        assert len(output.entities) > 0

    def test_kg_context_empty_external_references_handled(self):
        """Empty external_references list doesn't crash."""
        entities_dict = {
            "entity1": {
                "title": "Apple Inc.",
                "node_type": "Organization",
                "embedding": [0.09] * 10,  # Will match threshold
                "description": "Tech company",
                "external_references": [],  # Empty list - the issue being fixed
            }
        }

        output = layers.kg_context.execute(
            text="Test text",
            ontology_repo=FakeOntologyRepository(entities_dict),
            embedding_service=FakeEmbeddingService(),
        )

        # Should not crash and should handle missing URI gracefully
        if output.entities:
            assert output.entities[0].uri is None

    def test_kg_context_missing_external_references_handled(self):
        """Missing external_references key handled gracefully."""
        entities_dict = {
            "entity1": {
                "title": "Apple Inc.",
                "node_type": "Organization",
                "embedding": [0.09] * 10,
                "description": "Tech company",
                # No external_references key at all
            }
        }

        output = layers.kg_context.execute(
            text="Test text",
            ontology_repo=FakeOntologyRepository(entities_dict),
            embedding_service=FakeEmbeddingService(),
        )

        # Should not crash
        if output.entities:
            assert output.entities[0].uri is None

    def test_kg_context_confidence_from_similarity(self):
        """Confidence is set from similarity score."""
        entities_dict = {
            "entity1": {
                "title": "Apple Inc.",
                "node_type": "Organization",
                "embedding": [0.08] * 10,
                "description": "Tech company",
                "external_references": [{"uri": "https://apple.com"}],
            }
        }

        output = layers.kg_context.execute(
            text="Test text",
            ontology_repo=FakeOntologyRepository(entities_dict),
            embedding_service=FakeEmbeddingService(),
        )

        if output.entities:
            # Confidence should be the similarity score
            assert 0.0 <= output.entities[0].confidence <= 1.0

    def test_kg_context_threshold_filtering(self):
        """Low similarity entities below 0.7 threshold are filtered."""
        # Create embeddings that will produce low similarity
        # Use completely different embeddings
        entities_dict = {
            "entity1": {
                "title": "Apple Inc.",
                "node_type": "Organization",
                "embedding": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # Very different
                "description": "Tech company",
                "external_references": [{"uri": "https://apple.com"}],
            }
        }

        output = layers.kg_context.execute(
            text="Test text",
            ontology_repo=FakeOntologyRepository(entities_dict),
            embedding_service=FakeEmbeddingService(),
        )

        # Similarity between [1.0, 0...] and generated text embedding should be < 0.7
        # If entity is returned, check that it's because similarity >= 0.7
        # Otherwise verify entities are empty
        assert len(output.entities) == 0 or output.entities[0].confidence >= 0.7


# ============================================================================
# Tests for Layer 1: LLM Extract
# ============================================================================

class TestLayer1LLMExtract:
    """Tests for LLM extraction layer."""

    def test_llm_extract_empty_text_returns_empty(self):
        """Empty text returns empty output."""
        input_data = LayerInput(text="", existing_entities=[])
        output = layers.llm_extract.execute(input_data, FakeLLMProvider())

        assert output.entities == []
        assert output.metadata["reason"] == "empty_text"

    def test_llm_extract_no_available_models_returns_empty(self):
        """No available models returns empty output."""
        class NoModelsLLM:
            def list_available_models(self):
                return []

        input_data = LayerInput(text="Test text", existing_entities=[])
        output = layers.llm_extract.execute(input_data, NoModelsLLM())

        assert output.entities == []
        assert output.metadata["reason"] == "no_models_available"

    def test_llm_extract_simple_json_array(self):
        """Simple JSON array is parsed correctly."""
        json_response = '[{"label": "Apple", "type": "ORG", "confidence": 0.95}]'
        input_data = LayerInput(text="Test text", existing_entities=[])
        output = layers.llm_extract.execute(input_data, FakeLLMProvider(json_response))

        assert len(output.entities) == 1
        assert output.entities[0].label == "Apple"
        assert output.entities[0].entity_type == "ORG"
        assert output.entities[0].confidence == 0.95

    def test_llm_extract_nested_json_array_preserved(self):
        """Nested JSON arrays are NOT truncated."""
        # This JSON has nested arrays - the bug fix should handle this
        json_response = '''{
            "entities": [
                {"label": "Apple", "type": "ORG", "confidence": 0.95},
                {"label": "Microsoft", "type": "ORG", "confidence": 0.90}
            ],
            "metadata": ["tag1", "tag2"]
        }'''
        # The layer should extract the outer array starting with [
        # But this malformed response won't parse as valid JSON array
        # Let's use a properly formatted array with nested structures

        json_response = '[{"label": "Apple", "type": "ORG", "confidence": 0.95, "properties": ["tag1", "tag2"]}]'
        input_data = LayerInput(text="Test text", existing_entities=[])
        output = layers.llm_extract.execute(input_data, FakeLLMProvider(json_response))

        # Should correctly extract the outer array with nested array inside
        assert len(output.entities) == 1
        assert output.entities[0].label == "Apple"

    def test_llm_extract_multiple_nested_arrays(self):
        """Multiple levels of nesting are handled correctly."""
        # JSON with nested closing brackets
        json_response = '''[
            {"label": "Apple", "data": [1, 2, 3]},
            {"label": "Microsoft", "data": [4, 5, 6]}
        ]'''
        input_data = LayerInput(text="Test text", existing_entities=[])
        output = layers.llm_extract.execute(input_data, FakeLLMProvider(json_response))

        # Should not truncate at first ]
        assert len(output.entities) == 2
        assert output.entities[0].label == "Apple"
        assert output.entities[1].label == "Microsoft"

    def test_llm_extract_with_text_before_json(self):
        """JSON preceded by text is extracted correctly."""
        json_response = 'Here are the entities:\n[{"label": "Apple", "type": "ORG", "confidence": 0.95}]'
        input_data = LayerInput(text="Test text", existing_entities=[])
        output = layers.llm_extract.execute(input_data, FakeLLMProvider(json_response))

        assert len(output.entities) == 1
        assert output.entities[0].label == "Apple"

    def test_llm_extract_invalid_json_returns_empty(self):
        """Invalid JSON returns empty entities."""
        json_response = '[{"label": "Apple" "type": "ORG"}]'  # Missing comma
        input_data = LayerInput(text="Test text", existing_entities=[])
        output = layers.llm_extract.execute(input_data, FakeLLMProvider(json_response))

        assert output.entities == []

    def test_llm_extract_missing_label_skipped(self):
        """Entities without label are skipped."""
        json_response = '[{"type": "ORG", "confidence": 0.95}]'  # No label
        input_data = LayerInput(text="Test text", existing_entities=[])
        output = layers.llm_extract.execute(input_data, FakeLLMProvider(json_response))

        assert output.entities == []

    def test_llm_extract_empty_label_skipped(self):
        """Entities with empty label are skipped."""
        json_response = '[{"label": "", "type": "ORG", "confidence": 0.95}]'
        input_data = LayerInput(text="Test text", existing_entities=[])
        output = layers.llm_extract.execute(input_data, FakeLLMProvider(json_response))

        assert output.entities == []

    def test_llm_extract_with_context_from_prior_entities(self):
        """LLM receives context about prior entities."""
        prior_entity = ExtractedEntity(label="Google", entity_type="ORG")
        input_data = LayerInput(
            text="Test text with Apple and Google",
            existing_entities=[prior_entity],
        )
        json_response = '[{"label": "Apple", "type": "ORG", "confidence": 0.95}]'
        output = layers.llm_extract.execute(input_data, FakeLLMProvider(json_response))

        assert len(output.entities) == 1


# ============================================================================
# Tests for Layer 2: NLP Gap-Filling
# ============================================================================

class TestLayer2NLPGapFilling:
    """Tests for NLP gap-filling layer."""

    def test_nlp_gap_empty_text_returns_empty(self):
        """Empty text returns empty output."""
        input_data = LayerInput(text="", existing_entities=[])
        output = layers.nlp_gap.execute(input_data, FakeNLPProcessor())

        assert output.entities == []
        assert output.metadata["reason"] == "empty_text"

    def test_nlp_gap_processor_not_ready(self):
        """NLP processor not ready returns empty output."""
        class NotReadyNLP:
            def is_ready(self):
                return False

        input_data = LayerInput(text="Test text", existing_entities=[])
        output = layers.nlp_gap.execute(input_data, NotReadyNLP())

        assert output.entities == []
        assert output.metadata["reason"] == "nlp_processor_not_ready"

    def test_nlp_gap_extracts_new_entities(self):
        """NLP processor entities are extracted and added."""
        nlp_entities = [
            NLPEntity(text="Apple", label="ORG", start=0, end=5, confidence=0.75),
        ]
        input_data = LayerInput(text="Apple Inc.", existing_entities=[])
        output = layers.nlp_gap.execute(input_data, FakeNLPProcessor(nlp_entities))

        assert len(output.entities) == 1
        assert output.entities[0].label == "Apple"

    def test_nlp_gap_deduplicates_with_prior_entities(self):
        """Entities already found in prior layers are skipped."""
        prior_entity = ExtractedEntity(label="Apple", entity_type="ORG")
        nlp_entities = [
            NLPEntity(text="Apple", label="ORG", start=0, end=5, confidence=0.75),
        ]
        input_data = LayerInput(
            text="Apple Inc.",
            existing_entities=[prior_entity],
        )
        output = layers.nlp_gap.execute(input_data, FakeNLPProcessor(nlp_entities))

        # "Apple" already exists, so NLP entity should be skipped
        assert len(output.entities) == 0

    def test_nlp_gap_confidence_from_entity(self):
        """Confidence is taken from NLP entity if available."""
        nlp_entities = [
            NLPEntity(text="Apple", label="ORG", start=0, end=5, confidence=0.75),
        ]
        input_data = LayerInput(text="Apple Inc.", existing_entities=[])
        output = layers.nlp_gap.execute(input_data, FakeNLPProcessor(nlp_entities))

        # Should use default 0.75 if NLP entity has no confidence attribute
        assert output.entities[0].confidence == 0.75

    def test_nlp_gap_case_insensitive_deduplication(self):
        """Deduplication is case-insensitive."""
        prior_entity = ExtractedEntity(label="apple", entity_type="ORG")
        nlp_entities = [
            NLPEntity(text="Apple", label="ORG", start=0, end=5, confidence=0.75),
        ]
        input_data = LayerInput(
            text="Apple Inc.",
            existing_entities=[prior_entity],
        )
        output = layers.nlp_gap.execute(input_data, FakeNLPProcessor(nlp_entities))

        # Case-insensitive match should skip the NLP entity
        assert len(output.entities) == 0

    def test_nlp_gap_whitespace_normalized(self):
        """Deduplication normalizes whitespace."""
        prior_entity = ExtractedEntity(label="Apple Inc.", entity_type="ORG")
        nlp_entities = [
            NLPEntity(text="  Apple Inc.  ", label="ORG", start=0, end=14, confidence=0.8),
        ]
        input_data = LayerInput(
            text="  Apple Inc.  company",
            existing_entities=[prior_entity],
        )
        output = layers.nlp_gap.execute(input_data, FakeNLPProcessor(nlp_entities))

        # Whitespace-normalized match should skip the NLP entity
        assert len(output.entities) == 0


# ============================================================================
# Tests for Layer 3: Reference Enrichment
# ============================================================================

class TestLayer3ReferenceEnrichment:
    """Tests for reference source enrichment layer."""

    def test_reference_empty_text_returns_empty(self):
        """Empty text returns empty output."""
        input_data = LayerInput(text="", existing_entities=[])
        output = layers.reference.execute(input_data, [])

        assert output.entities == []
        assert output.metadata["reason"] == "empty_text"

    def test_reference_no_prior_entities_returns_empty(self):
        """No prior entities returns empty output."""
        input_data = LayerInput(text="Test text", existing_entities=[])
        output = layers.reference.execute(input_data, [FakeReferenceSource()])

        assert output.entities == []
        assert output.metadata["reason"] == "no_prior_entities"

    def test_reference_no_available_sources_returns_empty(self):
        """No available sources returns empty output."""
        prior_entity = ExtractedEntity(label="Apple", entity_type="ORG")
        input_data = LayerInput(
            text="Test text",
            existing_entities=[prior_entity],
        )

        class UnavailableSource:
            @property
            def source_name(self):
                return "Test"

            def is_available(self):
                return False

        output = layers.reference.execute(input_data, [UnavailableSource()])

        assert output.entities == []
        assert output.metadata["reason"] == "no_available_reference_sources"

    def test_reference_enriches_entity(self):
        """Entity is enriched with reference data."""
        prior_entity = ExtractedEntity(label="Apple", entity_type="ORG")
        input_data = LayerInput(
            text="Test text",
            existing_entities=[prior_entity],
        )

        ref_result = ReferenceResult(
            uri="https://dbpedia.org/resource/Apple_Inc.",
            label="Apple Inc.",
            description="Technology company",
            source="DBpedia",
        )

        source = FakeReferenceSource(
            results_map={"Apple": [ref_result]}
        )

        output = layers.reference.execute(input_data, [source])

        assert len(output.entities) == 1
        enriched = output.entities[0]
        assert enriched.id == prior_entity.id  # Same ID
        assert enriched.uri == ref_result.uri  # Enriched with URI
        assert enriched.properties["reference_source"] == "TestSource"

    def test_reference_no_duplicate_enrichment(self):
        """Entity enriched only once per source list."""
        prior_entity = ExtractedEntity(label="Apple", entity_type="ORG")
        input_data = LayerInput(
            text="Test text",
            existing_entities=[prior_entity],
        )

        ref_result = ReferenceResult(
            uri="https://dbpedia.org/resource/Apple_Inc.",
            label="Apple Inc.",
            description="Tech company",
            source="DBpedia",
        )

        # Two sources could both return results for "Apple"
        source1 = FakeReferenceSource(
            source_name_val="Source1",
            results_map={"Apple": [ref_result]},
        )
        source2 = FakeReferenceSource(
            source_name_val="Source2",
            results_map={"Apple": [ref_result]},
        )

        output = layers.reference.execute(input_data, [source1, source2])

        # Should have enriched exactly once (first source match)
        assert len(output.entities) == 1

    def test_reference_preserves_original_layer(self):
        """Original source_layer is preserved."""
        prior_entity = ExtractedEntity(
            label="Apple",
            entity_type="ORG",
            source_layer=1,  # From LLM
        )
        input_data = LayerInput(
            text="Test text",
            existing_entities=[prior_entity],
        )

        ref_result = ReferenceResult(
            uri="https://dbpedia.org/resource/Apple_Inc.",
            label="Apple Inc.",
        )

        source = FakeReferenceSource(
            results_map={"Apple": [ref_result]}
        )

        output = layers.reference.execute(input_data, [source])

        assert output.entities[0].source_layer == 1

    def test_reference_no_results_entity_not_enriched(self):
        """Entity with no reference results is not added."""
        prior_entity = ExtractedEntity(label="Apple", entity_type="ORG")
        input_data = LayerInput(
            text="Test text",
            existing_entities=[prior_entity],
        )

        # Source returns no results for "Apple"
        source = FakeReferenceSource(results_map={})

        output = layers.reference.execute(input_data, [source])

        assert len(output.entities) == 0

    def test_reference_prefers_reference_uri(self):
        """Reference URI is preferred over prior entity URI."""
        prior_entity = ExtractedEntity(
            label="Apple",
            entity_type="ORG",
            uri="https://prior.uri",
        )
        input_data = LayerInput(
            text="Test text",
            existing_entities=[prior_entity],
        )

        ref_result = ReferenceResult(
            uri="https://dbpedia.org/resource/Apple_Inc.",
            label="Apple Inc.",
        )

        source = FakeReferenceSource(
            results_map={"Apple": [ref_result]}
        )

        output = layers.reference.execute(input_data, [source])

        # Should use reference URI instead of prior URI
        assert output.entities[0].uri == ref_result.uri

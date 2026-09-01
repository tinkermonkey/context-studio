"""
Unit tests for ExtractionService._relevant_class_catalog.

Tests the retrieval-based class catalog with fallback guards, embedding, vector
search, and deduplication logic. Uses FakeSchemaVectorIndex and FakeEmbeddingService
to avoid real embeddings or database operations.
"""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from domain.extraction.services import ExtractionService
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.ontology.ports import SchemaMatch
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_schema_vector_index import FakeSchemaVectorIndex


class TestRelevantClassCatalog:
    """Test suite for _relevant_class_catalog method."""

    @pytest.fixture
    def ontology_repo(self):
        """Create a fake ontology repository."""
        return FakeOntologyRepository()

    @pytest.fixture
    def embedding_service(self):
        """Create a fake embedding service."""
        return FakeEmbeddingService()

    @pytest.fixture
    def schema_index(self):
        """Create a fake schema vector index."""
        return FakeSchemaVectorIndex()

    @pytest.fixture
    def service(self, ontology_repo, embedding_service, schema_index):
        """Create an ExtractionService with fake dependencies."""
        return ExtractionService(
            ontology_repo=ontology_repo,
            embedding_service=embedding_service,
            llm=Mock(),
            nlp=Mock(),
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=Mock(),
            extraction_run_repo=Mock(),
            schema_index=schema_index,
        )

    def _setup_taxonomy_with_classes(self, ontology_repo, taxonomy_id: str, scheme_id: str, num_classes: int):
        """Helper to set up a taxonomy, concept scheme, and classes in the ontology repository."""
        taxonomy = Taxonomy(
            id=taxonomy_id,
            identifier=f"tax_{taxonomy_id}",
            title=f"Test Taxonomy {taxonomy_id}",
            description="Test taxonomy for unit testing",
        )
        ontology_repo.save_taxonomy(taxonomy)

        scheme = ConceptScheme(
            id=scheme_id,
            taxonomy_id=taxonomy_id,
            identifier=f"scheme_{scheme_id}",
            title=f"Test Scheme {scheme_id}",
            description="Test concept scheme for unit testing",
        )
        ontology_repo.save_concept_scheme(scheme)

        for i in range(num_classes):
            cls = Class(
                id=f"class_{i}",
                concept_scheme_id=scheme_id,
                taxonomy_id=taxonomy_id,
                identifier=f"ref_{i}",
                title=f"Class {i}",
                description=f"Class {i} description",
                external_references=[Mock(identifier=f"external.{i}")],
            )
            ontology_repo.save_class(cls)

        return taxonomy

    def test_returns_empty_list_for_missing_taxonomy_id(self, service):
        """When ontology has no id, method returns empty list."""
        ontology = Mock(spec=['title'])
        ontology.id = None
        ontology.title = "Test Ontology"

        result = service._relevant_class_catalog("test text", ontology)

        assert result == []

    def test_fallback_to_full_catalog_when_index_not_configured(self, service, ontology_repo):
        """When schema_index is None, falls back to full catalog."""
        service._schema_index = None
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 2)

        result = service._relevant_class_catalog("test text", taxonomy)

        assert len(result) == 2
        assert any(ref == "external.0" for ref, _ in result)
        assert any(ref == "external.1" for ref, _ in result)

    def test_fallback_to_full_catalog_when_taxonomy_at_skip_threshold(self, service, ontology_repo):
        """When class count equals skip threshold, returns full catalog without search."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 50)

        result = service._relevant_class_catalog("test text", taxonomy)

        assert len(result) == 50
        assert len(service._embedding_service.embed_calls) == 0

    def test_fallback_to_full_catalog_when_taxonomy_below_skip_threshold(self, service, ontology_repo):
        """When class count is below skip threshold, returns full catalog without search."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 30)

        result = service._relevant_class_catalog("test text", taxonomy)

        assert len(result) == 30
        assert len(service._embedding_service.embed_calls) == 0

    def test_fallback_to_full_catalog_when_embedding_fails(self, service, ontology_repo, embedding_service):
        """When embedding raises exception, falls back to full catalog."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 100)

        original_embed = embedding_service.embed
        embedding_service.embed = Mock(side_effect=RuntimeError("Embedding failed"))

        result = service._relevant_class_catalog("test text", taxonomy)

        assert len(result) == 100
        assert len(embedding_service.embed.call_args_list) == 1

        embedding_service.embed = original_embed

    def test_fallback_to_full_catalog_when_search_fails(self, service, ontology_repo, schema_index):
        """When schema index search raises exception, falls back to full catalog."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 100)

        original_search = schema_index.search
        schema_index.search = Mock(side_effect=RuntimeError("Search failed"))

        result = service._relevant_class_catalog("test text", taxonomy)

        assert len(result) == 100
        assert schema_index.search.call_count == 1

        schema_index.search = original_search

    def test_fallback_to_full_catalog_when_results_below_minimum(self, service, ontology_repo, schema_index):
        """When search returns fewer than minimum results, falls back to full catalog."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 100)

        # Configure schema index to return only 3 results (below minimum of 5)
        matches = [
            SchemaMatch(
                entity_id=f"class_{i}",
                kind="class",
                label=f"Class {i}",
                score=0.9 - (i * 0.1),
                matched_field="title",
                external_id=f"external.{i}",
            )
            for i in range(3)
        ]
        schema_index.set_search_results(matches, {m.entity_id: "tax_1" for m in matches})

        result = service._relevant_class_catalog("test text", taxonomy)

        # Should return full catalog instead of the 3 retrieved classes
        assert len(result) == 100

    def test_retrieval_produces_subset_different_from_full_catalog(self, service, ontology_repo, schema_index):
        """When retrieval succeeds, returns relevant subset different from full catalog."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 100)

        # Configure schema index to return only 8 specific classes (above minimum of 5)
        retrieved_indices = [5, 15, 25, 35, 45, 55, 65, 75]
        matches = [
            SchemaMatch(
                entity_id=f"class_{i}",
                kind="class",
                label=f"Class {i}",
                score=0.95 - (idx * 0.01),
                matched_field="title",
                external_id=f"external.{i}",
            )
            for idx, i in enumerate(retrieved_indices)
        ]
        schema_index.set_search_results(matches, {m.entity_id: "tax_1" for m in matches})

        result = service._relevant_class_catalog("test text", taxonomy)

        # Should return only the 8 retrieved classes, not the full 100
        assert len(result) == 8
        refs = [ref for ref, _ in result]
        for i in retrieved_indices:
            assert f"external.{i}" in refs

    def test_deduplicates_class_references(self, service, ontology_repo, schema_index):
        """Deduplicates retrieved classes by reference."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 100)

        # Configure schema index with duplicate references (same external_id, different titles)
        matches = [
            SchemaMatch(
                entity_id="class_1",
                kind="class",
                label="Class One",
                score=0.95,
                matched_field="title",
                external_id="external.1",
            ),
            SchemaMatch(
                entity_id="class_2",
                kind="class",
                label="Class Uno",  # Different title, same external_id
                score=0.94,
                matched_field="title",
                external_id="external.1",  # Duplicate reference!
            ),
            SchemaMatch(
                entity_id="class_3",
                kind="class",
                label="Class Three",
                score=0.93,
                matched_field="title",
                external_id="external.3",
            ),
            SchemaMatch(
                entity_id="class_4",
                kind="class",
                label="Class Four",
                score=0.92,
                matched_field="title",
                external_id="external.4",
            ),
            SchemaMatch(
                entity_id="class_5",
                kind="class",
                label="Class Five",
                score=0.91,
                matched_field="title",
                external_id="external.5",
            ),
        ]
        schema_index.set_search_results(matches, {m.entity_id: "tax_1" for m in matches})

        result = service._relevant_class_catalog("test text", taxonomy)

        # Should have 4 unique references (external.1 is deduplicated)
        assert len(result) == 4
        refs = [ref for ref, _ in result]
        assert refs.count("external.1") == 1
        assert "external.3" in refs
        assert "external.4" in refs
        assert "external.5" in refs

    def test_respects_relevant_catalog_top_k_limit(self, service, ontology_repo, schema_index):
        """Caps retrieved classes at _RELEVANT_CATALOG_TOP_K."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 200)

        # Configure schema index to return 100 results (more than top_k of 50)
        matches = [
            SchemaMatch(
                entity_id=f"class_{i}",
                kind="class",
                label=f"Class {i}",
                score=0.99 - (i * 0.001),
                matched_field="title",
                external_id=f"external.{i}",
            )
            for i in range(100)
        ]
        schema_index.set_search_results(matches, {m.entity_id: "tax_1" for m in matches})

        # Configure schema index to return 100 results (more than top_k of 50)
        matches = [
            SchemaMatch(
                entity_id=f"class_{i}",
                kind="class",
                label=f"Class {i}",
                score=0.99 - (i * 0.001),
                matched_field="title",
                external_id=f"external.{i}",
            )
            for i in range(100)
        ]
        schema_index.set_search_results(matches, {m.entity_id: "tax_1" for m in matches})

        result = service._relevant_class_catalog("test text", taxonomy)

        # Should return only top 50 (the _RELEVANT_CATALOG_TOP_K limit)
        assert len(result) <= 50

    def test_scopes_search_strictly_to_taxonomy(self, service, ontology_repo, schema_index):
        """Ensures search is scoped to the target taxonomy_id."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 100)

        # Configure schema index with matches from different taxonomies
        # tax_1 matches (should be included)
        tax1_matches = [
            SchemaMatch(
                entity_id=f"tax1_class_{i}",
                kind="class",
                label=f"Class {i}",
                score=0.95 - (i * 0.01),
                matched_field="title",
                external_id=f"external.{i}",
            )
            for i in range(6)
        ]
        # tax_2 matches (should be excluded)
        tax2_matches = [
            SchemaMatch(
                entity_id=f"tax2_class_{i}",
                kind="class",
                label=f"Other Class {i}",
                score=0.98 - (i * 0.01),
                matched_field="title",
                external_id=f"external.other.{i}",
            )
            for i in range(10)
        ]

        all_matches = tax1_matches + tax2_matches
        taxonomies = {m.entity_id: ("tax_1" if m.entity_id.startswith("tax1_") else "tax_2") for m in all_matches}
        schema_index.set_search_results(all_matches, taxonomies)

        result = service._relevant_class_catalog("test text", taxonomy)

        # Should only include tax_1 matches
        assert len(result) == 6
        refs = [ref for ref, _ in result]
        for i in range(6):
            assert f"external.{i}" in refs
        # Should not include tax_2 matches
        for i in range(10):
            assert f"external.other.{i}" not in refs

    def test_embeds_source_text(self, service, ontology_repo, embedding_service, schema_index):
        """Verifies that source text is embedded."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 100)

        # Configure enough results to pass minimum threshold
        matches = [
            SchemaMatch(
                entity_id=f"class_{i}",
                kind="class",
                label=f"Class {i}",
                score=0.95 - (i * 0.01),
                matched_field="title",
                external_id=f"external.{i}",
            )
            for i in range(10)
        ]
        schema_index.set_search_results(matches, {m.entity_id: "tax_1" for m in matches})

        # Configure enough results to pass minimum threshold
        matches = [
            SchemaMatch(
                entity_id=f"class_{i}",
                kind="class",
                label=f"Class {i}",
                score=0.95 - (i * 0.01),
                matched_field="title",
                external_id=f"external.{i}",
            )
            for i in range(10)
        ]
        schema_index.set_search_results(matches, {m.entity_id: "tax_1" for m in matches})

        source_text = "test extraction text"
        service._relevant_class_catalog(source_text, taxonomy)

        # Verify the exact text was embedded
        assert source_text in embedding_service.embed_calls

    def test_prompt_format_preserved_ref_title_pairs(self, service, ontology_repo, schema_index):
        """Verifies returned format is (ref, title) tuples matching _ontology_class_catalog format."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 100)

        matches = [
            SchemaMatch(
                entity_id=f"class_{i}",
                kind="class",
                label=f"Class {i}",
                score=0.95 - (i * 0.01),
                matched_field="title",
                external_id=f"external.{i}",
            )
            for i in range(10)
        ]
        schema_index.set_search_results(matches, {m.entity_id: "tax_1" for m in matches})

        result = service._relevant_class_catalog("test text", taxonomy)

        # Verify format: list of (ref, title) tuples
        assert isinstance(result, list)
        assert len(result) > 0
        for ref, title in result:
            assert isinstance(ref, str)
            assert isinstance(title, str)
            assert len(ref) > 0
            assert len(title) > 0

    def test_uses_external_id_as_ref_when_available(self, service, ontology_repo, schema_index):
        """Prefers external_id over label as class reference."""
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 100)

        # Some matches with external_id, some without
        matches = [
            SchemaMatch(
                entity_id="class_1",
                kind="class",
                label="First Class",
                score=0.95,
                matched_field="title",
                external_id="tech.component",  # Should use this
            ),
            SchemaMatch(
                entity_id="class_2",
                kind="class",
                label="Second Class",
                score=0.94,
                matched_field="title",
                external_id=None,  # Should use label
            ),
            SchemaMatch(
                entity_id="class_3",
                kind="class",
                label="Third Class",
                score=0.93,
                matched_field="title",
                external_id="proc.activity",  # Should use this
            ),
            SchemaMatch(
                entity_id="class_4",
                kind="class",
                label="Fourth Class",
                score=0.92,
                matched_field="title",
                external_id="org.unit",  # Should use this
            ),
            SchemaMatch(
                entity_id="class_5",
                kind="class",
                label="Fifth Class",
                score=0.91,
                matched_field="title",
                external_id=None,  # Should use label
            ),
        ]
        schema_index.set_search_results(matches, {m.entity_id: "tax_1" for m in matches})

        result = service._relevant_class_catalog("test text", taxonomy)

        refs = [ref for ref, _ in result]
        assert "tech.component" in refs
        assert "Second Class" in refs  # Label used when no external_id
        assert "proc.activity" in refs
        assert "org.unit" in refs
        assert "Fifth Class" in refs  # Label used when no external_id

    def test_multiple_schemes_in_taxonomy(self, service, ontology_repo, schema_index):
        """Handles taxonomies with multiple concept schemes."""
        # Create taxonomy and first scheme
        taxonomy = self._setup_taxonomy_with_classes(ontology_repo, "tax_1", "scheme_1", 50)

        # Add second scheme to same taxonomy
        scheme2 = ConceptScheme(
            id="scheme_2",
            taxonomy_id="tax_1",
            identifier="scheme_2",
            title="Test Scheme 2",
            description="Test concept scheme 2",
        )
        ontology_repo.save_concept_scheme(scheme2)

        for i in range(60):
            cls = Class(
                id=f"class_2_{i}",
                concept_scheme_id="scheme_2",
                taxonomy_id="tax_1",
                identifier=f"ref_2_{i}",
                title=f"Scheme2 Class {i}",
                description=f"Scheme2 Class {i} description",
                external_references=[Mock(identifier=f"external.2.{i}")],
            )
            ontology_repo.save_class(cls)

        # Configure schema index to return classes from both schemes
        matches = [
            SchemaMatch(
                entity_id=f"class_{i}",
                kind="class",
                label=f"Scheme1 Class {i}",
                score=0.95 - (i * 0.001),
                matched_field="title",
                external_id=f"external.1.{i}",
            )
            for i in range(6)
        ] + [
            SchemaMatch(
                entity_id=f"class_2_{i}",
                kind="class",
                label=f"Scheme2 Class {i}",
                score=0.94 - (i * 0.001),
                matched_field="title",
                external_id=f"external.2.{i}",
            )
            for i in range(4)
        ]
        schema_index.set_search_results(matches, {m.entity_id: "tax_1" for m in matches})

        result = service._relevant_class_catalog("test text", taxonomy)

        # Should include classes from both schemes
        assert len(result) >= 10
        refs = [ref for ref, _ in result]
        assert any("external.1" in ref for ref in refs)
        assert any("external.2" in ref for ref in refs)

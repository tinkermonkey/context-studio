"""
Unit tests for ExtractionService._relevant_class_catalog (phase 1138 pass-1 retrieval).

Tests the retrieval-based class catalog with fallback guards, embedding, vector
search, and deduplication logic. Uses FakeSchemaVectorIndex and FakeEmbeddingService
to avoid real embeddings or database operations.
"""

from dataclasses import dataclass
from unittest.mock import Mock, patch

import pytest

from domain.extraction.services import ExtractionService
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.ontology.ports import SchemaKind, SchemaMatch


@dataclass
class MockClass:
    """Mock class entity for testing."""
    id: str
    title: str
    external_references: list | None = None

    def __init__(self, id: str, title: str, external_id: str | None = None):
        self.id = id
        self.title = title
        self.identifier = id.replace("class_", "")
        self.external_references = []
        if external_id:
            mock_ref = Mock()
            mock_ref.identifier = external_id
            self.external_references.append(mock_ref)


@dataclass
class MockScheme:
    """Mock concept scheme for testing."""
    id: str
    taxonomy_id: str | None = None


@dataclass
class MockTaxonomy:
    """Mock taxonomy for testing."""
    id: str
    title: str


class FakeOntologyRepository:
    """Fake ontology repository for testing."""

    def __init__(self):
        self.classes_by_scheme: dict[str, list[MockClass]] = {}
        self.schemes: list[MockScheme] = []
        self.class_counts: dict[str, int] = {}

    def add_scheme(self, scheme_id: str, taxonomy_id: str | None = None):
        scheme = MockScheme(id=scheme_id, taxonomy_id=taxonomy_id)
        self.schemes.append(scheme)
        self.classes_by_scheme[scheme_id] = []

    def add_class_to_scheme(self, scheme_id: str, class_id: str, title: str, external_id: str | None = None):
        cls = MockClass(id=class_id, title=title, external_id=external_id)
        self.classes_by_scheme[scheme_id].append(cls)

    def set_class_count(self, scheme_id: str, count: int):
        self.class_counts[scheme_id] = count

    def list_concept_schemes(self, taxonomy_id: str | None = None, **kwargs):
        return [s for s in self.schemes if taxonomy_id is None or s.taxonomy_id == taxonomy_id]

    def list_classes(self, concept_scheme_id: str | None = None, **kwargs):
        return self.classes_by_scheme.get(concept_scheme_id, [])

    def count_classes(self, concept_scheme_id: str | None = None, **kwargs):
        return self.class_counts.get(concept_scheme_id, len(self.classes_by_scheme.get(concept_scheme_id, [])))

    def get_class(self, class_id: str):
        for classes in self.classes_by_scheme.values():
            for cls in classes:
                if cls.id == class_id:
                    return cls
        return None


class FakeEmbeddingService:
    """Fake embedding service that returns predictable embeddings."""

    def __init__(self):
        self.embeddings: dict[str, list[float]] = {}
        self.embed_calls = []

    def set_embedding(self, text: str, embedding: list[float]):
        self.embeddings[text] = embedding

    def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return self.embeddings.get(text, [0.0] * 384)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        return 0.95


class FakeSchemaVectorIndex:
    """Fake schema vector index for testing."""

    def __init__(self):
        self.search_results: list[tuple[SchemaMatch, str | None]] = []

    def index_entity(self, entity_id: str, title: str, description: str | None = None):
        pass

    def set_search_results(self, results: list[SchemaMatch], taxonomies: dict[str, str | None] | None = None):
        if taxonomies is None:
            taxonomies = {match.entity_id: None for match in results}
        self.search_results = [(match, taxonomies.get(match.entity_id)) for match in results]

    def search(
        self,
        query_embedding,
        kinds: list[SchemaKind],
        top_k: int = 20,
        threshold: float = 0.0,
        taxonomy_id: str | None = None,
    ) -> list[SchemaMatch]:
        filtered = []
        for match, match_taxonomy_id in self.search_results:
            if match.kind not in kinds:
                continue
            if taxonomy_id is not None and match_taxonomy_id != taxonomy_id:
                continue
            filtered.append(match)
        return filtered[:top_k]


class MockEventPublisher:
    """Mock event publisher."""
    def publish(self, event):
        return []


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
            event_publisher=MockEventPublisher(),
            extraction_repo=Mock(),
            extraction_run_repo=Mock(),
            schema_index=schema_index,
        )

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
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        ontology_repo.add_class_to_scheme("scheme_1", "class_1", "Class One", "external.one")
        ontology_repo.add_class_to_scheme("scheme_1", "class_2", "Class Two", "external.two")

        result = service._relevant_class_catalog("test text", ontology)

        assert len(result) == 2
        assert ("external.one", "Class One") in result
        assert ("external.two", "Class Two") in result

    def test_fallback_to_full_catalog_when_taxonomy_at_skip_threshold(self, service, ontology_repo):
        """When class count equals skip threshold, returns full catalog without search."""
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        # Add exactly 50 classes (at skip threshold)
        for i in range(50):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 50)

        result = service._relevant_class_catalog("test text", ontology)

        assert len(result) == 50
        # Verify embed was NOT called (would be in embed_calls)
        assert len(service._embedding_service.embed_calls) == 0

    def test_fallback_to_full_catalog_when_taxonomy_below_skip_threshold(self, service, ontology_repo):
        """When class count is below skip threshold, returns full catalog without search."""
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        # Add 30 classes (below skip threshold of 50)
        for i in range(30):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 30)

        result = service._relevant_class_catalog("test text", ontology)

        assert len(result) == 30
        # Verify embed was NOT called
        assert len(service._embedding_service.embed_calls) == 0

    def test_fallback_to_full_catalog_when_embedding_fails(self, service, ontology_repo, embedding_service):
        """When embedding raises exception, falls back to full catalog."""
        embedding_service.embed = Mock(side_effect=RuntimeError("Embedding failed"))

        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        # Add 100 classes (above skip threshold)
        for i in range(100):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 100)

        result = service._relevant_class_catalog("test text", ontology)

        assert len(result) == 100
        # Verify embed was called once (and failed)
        assert len(embedding_service.embed.call_args_list) == 1

    def test_fallback_to_full_catalog_when_search_fails(self, service, ontology_repo, schema_index):
        """When schema index search raises exception, falls back to full catalog."""
        schema_index.search = Mock(side_effect=RuntimeError("Search failed"))

        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        # Add 100 classes (above skip threshold)
        for i in range(100):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 100)

        result = service._relevant_class_catalog("test text", ontology)

        assert len(result) == 100
        # Verify search was called once
        assert schema_index.search.call_count == 1

    def test_fallback_to_full_catalog_when_results_below_minimum(self, service, ontology_repo, schema_index):
        """When search returns fewer than minimum results, falls back to full catalog."""
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        # Add 100 classes (above skip threshold)
        for i in range(100):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 100)

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

        result = service._relevant_class_catalog("test text", ontology)

        # Should return full catalog instead of the 3 retrieved classes
        assert len(result) == 100

    def test_retrieval_produces_subset_different_from_full_catalog(self, service, ontology_repo, schema_index):
        """When retrieval succeeds, returns relevant subset different from full catalog."""
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        # Add 100 classes
        for i in range(100):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 100)

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

        result = service._relevant_class_catalog("test text", ontology)

        # Should return only the 8 retrieved classes, not the full 100
        assert len(result) == 8
        refs = [ref for ref, _ in result]
        for i in retrieved_indices:
            assert f"external.{i}" in refs

    def test_deduplicates_class_references(self, service, ontology_repo, schema_index):
        """Deduplicates retrieved classes by reference."""
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        for i in range(100):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 100)

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

        result = service._relevant_class_catalog("test text", ontology)

        # Should have 4 unique references (external.1 is deduplicated)
        assert len(result) == 4
        refs = [ref for ref, _ in result]
        assert refs.count("external.1") == 1
        assert "external.3" in refs
        assert "external.4" in refs
        assert "external.5" in refs

    def test_respects_relevant_catalog_top_k_limit(self, service, ontology_repo, schema_index):
        """Caps retrieved classes at _RELEVANT_CATALOG_TOP_K."""
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        for i in range(200):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 200)

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

        result = service._relevant_class_catalog("test text", ontology)

        # Should return only top 50 (the _RELEVANT_CATALOG_TOP_K limit)
        assert len(result) <= 50

    def test_scopes_search_strictly_to_taxonomy(self, service, ontology_repo, schema_index):
        """Ensures search is scoped to the target taxonomy_id."""
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        for i in range(100):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 100)

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

        result = service._relevant_class_catalog("test text", ontology)

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
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        for i in range(100):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 100)

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
        service._relevant_class_catalog(source_text, ontology)

        # Verify the exact text was embedded
        assert source_text in embedding_service.embed_calls

    def test_prompt_format_preserved_ref_title_pairs(self, service, ontology_repo, schema_index):
        """Verifies returned format is (ref, title) tuples matching _ontology_class_catalog format."""
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        for i in range(100):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 100)

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

        result = service._relevant_class_catalog("test text", ontology)

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
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        ontology_repo.add_scheme("scheme_1", "tax_1")
        for i in range(100):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_{i}", f"Class {i}", f"external.{i}")
        ontology_repo.set_class_count("scheme_1", 100)

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

        result = service._relevant_class_catalog("test text", ontology)

        refs = [ref for ref, _ in result]
        assert "tech.component" in refs
        assert "Second Class" in refs  # Label used when no external_id
        assert "proc.activity" in refs
        assert "org.unit" in refs
        assert "Fifth Class" in refs  # Label used when no external_id

    def test_multiple_schemes_in_taxonomy(self, service, ontology_repo, schema_index):
        """Handles taxonomies with multiple concept schemes."""
        ontology = Mock()
        ontology.id = "tax_1"
        ontology.title = "Test"

        # Add multiple schemes to same taxonomy
        ontology_repo.add_scheme("scheme_1", "tax_1")
        ontology_repo.add_scheme("scheme_2", "tax_1")

        for i in range(50):
            ontology_repo.add_class_to_scheme("scheme_1", f"class_1_{i}", f"Scheme1 Class {i}", f"external.1.{i}")
        for i in range(60):
            ontology_repo.add_class_to_scheme("scheme_2", f"class_2_{i}", f"Scheme2 Class {i}", f"external.2.{i}")

        ontology_repo.set_class_count("scheme_1", 50)
        ontology_repo.set_class_count("scheme_2", 60)

        # Configure schema index to return classes from both schemes
        matches = [
            SchemaMatch(
                entity_id=f"class_1_{i}",
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

        result = service._relevant_class_catalog("test text", ontology)

        # Should include classes from both schemes
        assert len(result) >= 10
        refs = [ref for ref, _ in result]
        assert any("external.1" in ref for ref in refs)
        assert any("external.2" in ref for ref in refs)

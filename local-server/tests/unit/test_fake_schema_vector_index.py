"""
Unit tests for FakeSchemaVectorIndex.

Tests verify the enhanced functionality: configurable search results,
default empty list behavior, filtering by kinds and taxonomy_id.
"""

import pytest

from domain.ontology.ports import SchemaMatch
from tests.fakes.fake_schema_vector_index import FakeSchemaVectorIndex


class TestFakeSchemaVectorIndexDefault:
    """Test default behavior with no configured results."""

    def test_default_search_returns_empty_list(self):
        """Default (unconfigured) search returns an empty list."""
        fake = FakeSchemaVectorIndex()
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class"],
        )
        assert result == []

    def test_index_entity_still_works(self):
        """Existing index_entity functionality is unaffected."""
        fake = FakeSchemaVectorIndex()
        fake.index_entity("class_1", "My Class", "A test class")
        # Verify it was recorded
        assert fake._entities["class_1"] == ("My Class", "A test class")


class TestFakeSchemaVectorIndexConfigurable:
    """Test configurable search results."""

    @pytest.fixture
    def sample_matches(self):
        """Create sample SchemaMatch objects for testing."""
        return [
            SchemaMatch(
                entity_id="class_1",
                kind="class",
                label="Node",
                score=0.95,
                matched_field="title",
                external_id="technology.node",
            ),
            SchemaMatch(
                entity_id="class_2",
                kind="class",
                label="Technology",
                score=0.85,
                matched_field="title",
                external_id="technology.technology",
            ),
            SchemaMatch(
                entity_id="prop_1",
                kind="property_definition",
                label="navigates to",
                score=0.90,
                matched_field="definition",
                external_id="technology.navigates_to",
                predicate="navigates-to",
            ),
        ]

    def test_configured_results_returned(self, sample_matches):
        """Configured results are returned by search()."""
        fake = FakeSchemaVectorIndex(search_results=sample_matches)
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class", "property_definition"],
        )
        assert len(result) == 3
        assert result == sample_matches

    def test_set_search_results_replaces_results(self, sample_matches):
        """set_search_results() replaces configured results."""
        fake = FakeSchemaVectorIndex()
        assert fake.search(query_embedding=[0.1] * 8, kinds=["class"]) == []

        fake.set_search_results(sample_matches)
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class", "property_definition"],
        )
        assert len(result) == 3

    def test_search_filters_by_kinds(self, sample_matches):
        """search() filters results by kinds parameter."""
        fake = FakeSchemaVectorIndex(search_results=sample_matches)

        # Filter to only classes
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class"],
        )
        assert len(result) == 2
        assert all(match.kind == "class" for match in result)
        assert result[0].label == "Node"
        assert result[1].label == "Technology"

        # Filter to only property_definitions
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["property_definition"],
        )
        assert len(result) == 1
        assert result[0].kind == "property_definition"
        assert result[0].label == "navigates to"

    def test_search_respects_top_k(self, sample_matches):
        """search() respects top_k parameter."""
        fake = FakeSchemaVectorIndex(search_results=sample_matches)

        # Request only 2 results
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class", "property_definition"],
            top_k=2,
        )
        assert len(result) == 2
        assert result[0].entity_id == "class_1"
        assert result[1].entity_id == "class_2"

    def test_search_filters_by_taxonomy_id(self, sample_matches):
        """search() filters results by taxonomy_id when provided."""
        fake = FakeSchemaVectorIndex()
        # Set up results with different taxonomies
        taxonomies = {
            "class_1": "tax_tech",
            "class_2": "tax_bio",
            "prop_1": "tax_tech",
        }
        fake.set_search_results(sample_matches, taxonomies=taxonomies)

        # Filter to tax_tech
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class", "property_definition"],
            taxonomy_id="tax_tech",
        )
        assert len(result) == 2
        assert all(
            match.entity_id in ["class_1", "prop_1"]
            for match in result
        )

        # Filter to tax_bio
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class", "property_definition"],
            taxonomy_id="tax_bio",
        )
        assert len(result) == 1
        assert result[0].entity_id == "class_2"

    def test_search_combines_filters(self, sample_matches):
        """search() applies both kinds and taxonomy_id filters."""
        fake = FakeSchemaVectorIndex()
        taxonomies = {
            "class_1": "tax_tech",
            "class_2": "tax_tech",
            "prop_1": "tax_bio",
        }
        fake.set_search_results(sample_matches, taxonomies=taxonomies)

        # Filter for classes in tax_tech
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class"],
            taxonomy_id="tax_tech",
        )
        assert len(result) == 2
        assert all(match.kind == "class" for match in result)
        assert all(match.entity_id in ["class_1", "class_2"] for match in result)

    def test_no_taxonomy_configured_excludes_from_taxonomy_filter(self):
        """Results without configured taxonomies are excluded by taxonomy_id filters."""
        matches = [
            SchemaMatch(
                entity_id="class_1",
                kind="class",
                label="Node",
                score=0.95,
                matched_field="title",
            ),
        ]
        fake = FakeSchemaVectorIndex(search_results=matches)

        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class"],
            taxonomy_id="tax_any",
        )
        assert len(result) == 0

    def test_set_search_results_with_explicit_taxonomies(self):
        """set_search_results() with explicit taxonomies dict."""
        matches = [
            SchemaMatch(
                entity_id="class_1",
                kind="class",
                label="Node",
                score=0.95,
                matched_field="title",
            ),
            SchemaMatch(
                entity_id="class_2",
                kind="class",
                label="Technology",
                score=0.85,
                matched_field="title",
            ),
        ]
        fake = FakeSchemaVectorIndex()
        fake.set_search_results(
            matches,
            taxonomies={"class_1": "tax_a", "class_2": None}
        )

        # class_1 matches tax_a
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class"],
            taxonomy_id="tax_a",
        )
        assert len(result) == 1
        assert result[0].entity_id == "class_1"

        # class_2 has None taxonomy, so it won't match any specific taxonomy_id filter
        result = fake.search(
            query_embedding=[0.1] * 8,
            kinds=["class"],
            taxonomy_id="tax_b",
        )
        assert len(result) == 0

"""Unit tests for reference aggregators."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from typing import List

from reference.aggregators import ResultAggregator
from reference.models import (
    SourceType, SearchNode, SearchLink, MultiSourceSearchResponse
)


class TestResultAggregator:
    """Test suite for ResultAggregator class."""

    @pytest.fixture
    def aggregator(self):
        """Create ResultAggregator instance for testing."""
        return ResultAggregator()

    @pytest.fixture
    def sample_nodes(self):
        """Create sample SearchNode objects for testing."""
        return [
            SearchNode(
                id="dbpedia:http://dbpedia.org/resource/Python",
                source=SourceType.DBPEDIA,
                title="Python (programming language)",
                definition="High-level programming language",
                attributes={"uri": "http://dbpedia.org/resource/Python"},
                source_url="http://dbpedia.org/resource/Python",
                relevance_score=0.95
            ),
            SearchNode(
                id="wikidata:http://www.wikidata.org/entity/Q28865",
                source=SourceType.WIKIDATA,
                title="Python",
                definition="programming language",
                attributes={"uri": "http://www.wikidata.org/entity/Q28865"},
                source_url="http://www.wikidata.org/entity/Q28865",
                relevance_score=0.90
            ),
            SearchNode(
                id="conceptnet:/c/en/python",
                source=SourceType.CONCEPTNET,
                title="python",
                definition=None,
                attributes={"concept_uri": "/c/en/python"},
                source_url="http://conceptnet.io/c/en/python",
                relevance_score=0.85
            ),
            SearchNode(
                id="schema_org:ComputerLanguage",
                source=SourceType.SCHEMA_ORG,
                title="ComputerLanguage",
                definition="This type covers computer languages such as Scheme and Lisp",
                attributes={"identifier": "ComputerLanguage"},
                source_url="https://schema.org/ComputerLanguage",
                relevance_score=0.80
            )
        ]

    @pytest.fixture
    def sample_links(self):
        """Create sample SearchLink objects for testing."""
        return [
            SearchLink(
                id="link1",
                source=SourceType.CONCEPTNET,
                subject="conceptnet:/c/en/python",
                predicate="IsA",
                object="conceptnet:/c/en/programming_language",
                weight=0.8,
                attributes={"relation_uri": "/r/IsA"}
            ),
            SearchLink(
                id="link2",
                source=SourceType.WIKIDATA,
                subject="wikidata:http://www.wikidata.org/entity/Q28865",
                predicate="instance of",
                object="wikidata:http://www.wikidata.org/entity/Q9143",
                weight=1.0,
                attributes={"property_id": "P31"}
            ),
            SearchLink(
                id="link1",  # Duplicate ID
                source=SourceType.CONCEPTNET,
                subject="conceptnet:/c/en/python",
                predicate="IsA",
                object="conceptnet:/c/en/programming_language",
                weight=0.8,
                attributes={"relation_uri": "/r/IsA"}
            )
        ]

    def test_deduplicate_nodes_success(self, aggregator, sample_nodes):
        """Test successful node deduplication."""
        # Add duplicate node
        duplicate_node = SearchNode(
            id="dbpedia:http://dbpedia.org/resource/Python",  # Same ID as first node
            source=SourceType.DBPEDIA,
            title="Python (duplicate)",
            definition="Duplicate node",
            attributes={},
            source_url="http://dbpedia.org/resource/Python",
            relevance_score=0.50
        )

        nodes_with_duplicates = sample_nodes + [duplicate_node]

        unique_nodes = aggregator.deduplicate_nodes(nodes_with_duplicates)

        # Should keep only the first occurrence of each ID
        assert len(unique_nodes) == 4  # Original 4 nodes, duplicate removed
        assert unique_nodes[0].title == "Python (programming language)"  # First occurrence kept

        # Verify all IDs are unique
        ids = [node.id for node in unique_nodes]
        assert len(ids) == len(set(ids))

    def test_deduplicate_nodes_empty_list(self, aggregator):
        """Test node deduplication with empty list."""
        unique_nodes = aggregator.deduplicate_nodes([])
        assert len(unique_nodes) == 0

    def test_deduplicate_links_success(self, aggregator, sample_links):
        """Test successful link deduplication with valid node filtering."""
        valid_node_ids = {
            "conceptnet:/c/en/python",
            "conceptnet:/c/en/programming_language",
            "wikidata:http://www.wikidata.org/entity/Q28865",
            "wikidata:http://www.wikidata.org/entity/Q9143"
        }

        unique_links = aggregator.deduplicate_links(sample_links, valid_node_ids)

        # Should have 2 unique links (duplicate "link1" removed)
        assert len(unique_links) == 2

        # Verify all link IDs are unique
        ids = [link.id for link in unique_links]
        assert len(ids) == len(set(ids))

        # Verify all links have valid subject/object references
        for link in unique_links:
            assert link.subject in valid_node_ids
            assert link.object in valid_node_ids

    def test_deduplicate_links_invalid_nodes_filtered(self, aggregator, sample_links):
        """Test that links with invalid node references are filtered out."""
        # Only include some of the referenced nodes
        valid_node_ids = {
            "conceptnet:/c/en/python",
            "wikidata:http://www.wikidata.org/entity/Q28865"
        }

        unique_links = aggregator.deduplicate_links(sample_links, valid_node_ids)

        # Should have 0 links because all links reference nodes not in valid_node_ids
        assert len(unique_links) == 0

    def test_discover_cross_references_success(self, aggregator):
        """Test successful cross-reference discovery."""
        # Create nodes with similar titles from different sources
        nodes = [
            SearchNode(
                id="dbpedia:http://dbpedia.org/resource/Python",
                source=SourceType.DBPEDIA,
                title="Python (programming language)",
                definition="High-level programming language",
                attributes={},
                source_url="http://dbpedia.org/resource/Python",
                relevance_score=0.95
            ),
            SearchNode(
                id="wikidata:http://www.wikidata.org/entity/Q28865",
                source=SourceType.WIKIDATA,
                title="Python",
                definition="programming language",
                attributes={},
                source_url="http://www.wikidata.org/entity/Q28865",
                relevance_score=0.90
            ),
            SearchNode(
                id="conceptnet:/c/en/python",
                source=SourceType.CONCEPTNET,
                title="python",
                definition=None,
                attributes={},
                source_url="http://conceptnet.io/c/en/python",
                relevance_score=0.85
            )
        ]

        cross_links = aggregator.discover_cross_references(nodes)

        # Should create cross-reference links between similar titles
        assert len(cross_links) > 0

        # Verify cross-reference properties
        for link in cross_links:
            assert link.predicate == "sameAs"
            assert link.source == SourceType.CONCEPTNET
            assert link.attributes["link_type"] == "cross_reference"
            assert "confidence" in link.attributes
            assert link.attributes["confidence"] >= 0.8  # High confidence threshold

    def test_discover_cross_references_no_matches(self, aggregator):
        """Test cross-reference discovery with no matching titles."""
        nodes = [
            SearchNode(
                id="dbpedia:http://dbpedia.org/resource/Python",
                source=SourceType.DBPEDIA,
                title="Python programming language",
                definition="High-level programming language",
                attributes={},
                source_url="http://dbpedia.org/resource/Python",
                relevance_score=0.95
            ),
            SearchNode(
                id="wikidata:http://www.wikidata.org/entity/Q28865",
                source=SourceType.WIKIDATA,
                title="Java programming language",
                definition="Object-oriented programming language",
                attributes={},
                source_url="http://www.wikidata.org/entity/Q28865",
                relevance_score=0.90
            )
        ]

        cross_links = aggregator.discover_cross_references(nodes)

        # Should not create cross-references for dissimilar titles
        assert len(cross_links) == 0

    def test_discover_cross_references_same_source(self, aggregator):
        """Test that cross-references are not created between nodes from the same source."""
        nodes = [
            SearchNode(
                id="dbpedia:http://dbpedia.org/resource/Python1",
                source=SourceType.DBPEDIA,
                title="Python",
                definition="Programming language",
                attributes={},
                source_url="http://dbpedia.org/resource/Python1",
                relevance_score=0.95
            ),
            SearchNode(
                id="dbpedia:http://dbpedia.org/resource/Python2",
                source=SourceType.DBPEDIA,
                title="Python",
                definition="Programming language",
                attributes={},
                source_url="http://dbpedia.org/resource/Python2",
                relevance_score=0.90
            )
        ]

        cross_links = aggregator.discover_cross_references(nodes)

        # Should not create cross-references between nodes from the same source
        assert len(cross_links) == 0

    def test_merge_responses_success(self, aggregator):
        """Test successful merging of multiple responses."""
        response1 = MultiSourceSearchResponse(
            query="python",
            results=[
                SearchNode(
                    id="dbpedia:python",
                    source=SourceType.DBPEDIA,
                    title="Python",
                    definition="Programming language",
                    attributes={},
                    source_url="http://dbpedia.org/resource/Python",
                    relevance_score=0.95
                )
            ],
            links=[],
            total_results=1,
            total_links=0,
            sources_queried=["dbpedia"],
            source_errors={},
            offset=0,
            limit=10,
            search_time_ms=100.0
        )

        response2 = MultiSourceSearchResponse(
            query="python",
            results=[
                SearchNode(
                    id="wikidata:python",
                    source=SourceType.WIKIDATA,
                    title="Python",
                    definition="Programming language",
                    attributes={},
                    source_url="http://www.wikidata.org/entity/Q28865",
                    relevance_score=0.90
                )
            ],
            links=[],
            total_results=1,
            total_links=0,
            sources_queried=["wikidata"],
            source_errors={"wikidata": "timeout"},
            offset=0,
            limit=10,
            search_time_ms=200.0
        )

        merged = aggregator.merge_responses([response1, response2])

        # Verify merged response
        assert merged.query == "python"
        assert len(merged.results) == 2
        assert merged.total_results == 2
        assert set(merged.sources_queried) == {"dbpedia", "wikidata"}
        assert merged.source_errors == {"wikidata": "timeout"}
        assert merged.search_time_ms == 300.0  # Sum of individual times

    def test_merge_responses_empty_list(self, aggregator):
        """Test merging empty list of responses."""
        merged = aggregator.merge_responses([])

        assert merged.query == ""
        assert len(merged.results) == 0
        assert merged.total_results == 0
        assert len(merged.sources_queried) == 0
        assert merged.search_time_ms == 0.0

    def test_aggregate_source_results_success(self, aggregator):
        """Test successful aggregation of source results."""
        source_results = [
            (SourceType.DBPEDIA, ([
                SearchNode(
                    id="dbpedia:python",
                    source=SourceType.DBPEDIA,
                    title="Python",
                    definition="Programming language",
                    attributes={},
                    source_url="http://dbpedia.org/resource/Python",
                    relevance_score=0.95
                )
            ], [])),
            (SourceType.WIKIDATA, ([
                SearchNode(
                    id="wikidata:python",
                    source=SourceType.WIKIDATA,
                    title="Python",
                    definition="Programming language",
                    attributes={},
                    source_url="http://www.wikidata.org/entity/Q28865",
                    relevance_score=0.90
                )
            ], []))
        ]

        response = aggregator.aggregate_source_results(
            source_results=source_results,
            query="python",
            limit=10,
            offset=0,
            search_time_ms=150.0,
            source_errors={}
        )

        assert response.query == "python"
        assert len(response.results) == 2
        assert response.total_results == 2
        assert set(response.sources_queried) == {"dbpedia", "wikidata"}
        assert response.search_time_ms == 150.0

    def test_normalize_title_success(self, aggregator):
        """Test title normalization for cross-reference matching."""
        # Test basic normalization
        assert aggregator._normalize_title("  Python  ") == "python"
        assert aggregator._normalize_title("The Python Language") == "python language"
        assert aggregator._normalize_title("A Python (programming)") == "python"

        # Test file type handling
        assert aggregator._normalize_title("image file") == "image file"
        assert aggregator._normalize_title("document file") == "document file"

        # Test empty/None handling
        assert aggregator._normalize_title("") == ""
        assert aggregator._normalize_title(None) == ""

    def test_calculate_title_similarity_success(self, aggregator):
        """Test title similarity calculation."""
        # Identical titles
        assert aggregator._calculate_title_similarity("python", "python") == 1.0

        # Similar titles (case differences are normalized away, so these are identical)
        similarity = aggregator._calculate_title_similarity("python", "Python")
        assert similarity == 1.0  # Should be identical after normalization

        # Actually similar but not identical titles
        similarity = aggregator._calculate_title_similarity("python", "python lang")
        assert 0.5 < similarity < 1.0  # Should be high but not perfect

        # Different titles
        similarity = aggregator._calculate_title_similarity("python", "java")
        assert similarity < 0.5

        # Empty titles (should return 0.0 as they can't be meaningfully compared)
        assert aggregator._calculate_title_similarity("", "") == 0.0
        assert aggregator._calculate_title_similarity("python", "") == 0.0
        assert aggregator._calculate_title_similarity("", "python") == 0.0

    def test_cross_reference_confidence_threshold(self, aggregator):
        """Test that cross-references are only created above confidence threshold."""
        nodes = [
            SearchNode(
                id="dbpedia:python",
                source=SourceType.DBPEDIA,
                title="Python programming",  # Somewhat similar
                definition="Programming language",
                attributes={},
                source_url="http://dbpedia.org/resource/Python",
                relevance_score=0.95
            ),
            SearchNode(
                id="wikidata:python",
                source=SourceType.WIKIDATA,
                title="Java language",  # Not similar enough
                definition="Programming language",
                attributes={},
                source_url="http://www.wikidata.org/entity/Q28865",
                relevance_score=0.90
            )
        ]

        cross_links = aggregator.discover_cross_references(nodes)

        # Should not create cross-references below confidence threshold (0.8)
        assert len(cross_links) == 0

    def test_complex_aggregation_with_cross_references(self, aggregator):
        """Test complex aggregation scenario with cross-references."""
        # Create nodes that should have cross-references
        source_results = [
            (SourceType.DBPEDIA, ([
                SearchNode(
                    id="dbpedia:python",
                    source=SourceType.DBPEDIA,
                    title="Python",
                    definition="Programming language",
                    attributes={},
                    source_url="http://dbpedia.org/resource/Python",
                    relevance_score=0.95
                )
            ], [])),
            (SourceType.WIKIDATA, ([
                SearchNode(
                    id="wikidata:python",
                    source=SourceType.WIKIDATA,
                    title="Python",
                    definition="Programming language",
                    attributes={},
                    source_url="http://www.wikidata.org/entity/Q28865",
                    relevance_score=0.90
                )
            ], []))
        ]

        response = aggregator.aggregate_source_results(
            source_results=source_results,
            query="python",
            limit=10,
            offset=0,
            search_time_ms=150.0,
            source_errors={}
        )

        # Should have nodes + cross-reference links
        assert len(response.results) == 2
        assert len(response.links) > 0  # Should have cross-reference links

        # Verify cross-reference link exists
        cross_ref_links = [link for link in response.links if link.predicate == "sameAs"]
        assert len(cross_ref_links) > 0

        cross_ref = cross_ref_links[0]
        assert cross_ref.attributes["link_type"] == "cross_reference"
        assert cross_ref.subject in ["dbpedia:python", "wikidata:python"]
        assert cross_ref.object in ["dbpedia:python", "wikidata:python"]
        assert cross_ref.subject != cross_ref.object
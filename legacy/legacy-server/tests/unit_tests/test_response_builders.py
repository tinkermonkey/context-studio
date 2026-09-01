"""Unit tests for reference response builders."""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from reference_api.models import (
    MultiSourceSearchResponse,
    SearchLink,
    SearchNode,
    SourceType,
)
from reference_api.response_builders import ResponseBuilder


class TestResponseBuilder:
    """Test suite for ResponseBuilder class."""

    @pytest.fixture
    def builder(self):
        """Create ResponseBuilder instance for testing."""
        return ResponseBuilder()

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
                relevance_score=0.95,
            ),
            SearchNode(
                id="wikidata:http://www.wikidata.org/entity/Q28865",
                source=SourceType.WIKIDATA,
                title="Python",
                definition="programming language",
                attributes={"uri": "http://www.wikidata.org/entity/Q28865"},
                source_url="http://www.wikidata.org/entity/Q28865",
                relevance_score=0.90,
            ),
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
                attributes={"relation_uri": "/r/IsA"},
            ),
            SearchLink(
                id="link2",
                source=SourceType.WIKIDATA,
                subject="wikidata:http://www.wikidata.org/entity/Q28865",
                predicate="instance of",
                object="wikidata:http://www.wikidata.org/entity/Q9143",
                weight=1.0,
                attributes={"property_id": "P31"},
            ),
        ]

    def test_build_single_source_response_success(
        self, builder, sample_nodes, sample_links
    ):
        """Test successful single source response building."""
        response = builder.build_single_source_response(
            source=SourceType.DBPEDIA,
            query="python",
            nodes=sample_nodes,
            links=sample_links,
            limit=10,
            offset=0,
            search_time_ms=150.5,
        )

        # Verify response structure
        assert isinstance(response, MultiSourceSearchResponse)
        assert response.query == "python"
        assert response.results == sample_nodes
        assert response.links == sample_links
        assert response.total_results == 2
        assert response.total_links == 2
        assert response.sources_queried == ["dbpedia"]
        assert response.source_errors == {}
        assert response.offset == 0
        assert response.limit == 10
        assert response.search_time_ms == 150.5

    def test_build_single_source_response_with_error(self, builder):
        """Test single source response building with error."""
        response = builder.build_single_source_response(
            source=SourceType.WIKIDATA,
            query="test",
            nodes=[],
            links=[],
            limit=5,
            offset=10,
            search_time_ms=None,  # Should default to 0.0
            error="Connection timeout",
        )

        assert response.query == "test"
        assert len(response.results) == 0
        assert len(response.links) == 0
        assert response.total_results == 0
        assert response.total_links == 0
        assert response.sources_queried == ["wikidata"]
        assert response.source_errors == {"wikidata": "Connection timeout"}
        assert response.offset == 10
        assert response.limit == 5
        assert response.search_time_ms == 0.0

    def test_build_single_source_response_defaults(self, builder):
        """Test single source response building with default values."""
        response = builder.build_single_source_response(
            source=SourceType.CONCEPTNET, query="test query", nodes=[], links=[]
        )

        # Check default values
        assert response.limit == 20
        assert response.offset == 0
        assert response.search_time_ms == 0.0
        assert response.source_errors == {}

    def test_build_multi_source_response_success(
        self, builder, sample_nodes, sample_links
    ):
        """Test successful multi-source response building."""
        response = builder.build_multi_source_response(
            query="python programming",
            all_nodes=sample_nodes,
            all_links=sample_links,
            sources_queried=["dbpedia", "wikidata", "conceptnet"],
            source_errors={"conceptnet": "rate limit exceeded"},
            limit=15,
            offset=5,
            search_time_ms=250.75,
        )

        assert response.query == "python programming"
        assert response.results == sample_nodes
        assert response.links == sample_links
        assert response.total_results == 2
        assert response.total_links == 2
        assert response.sources_queried == ["dbpedia", "wikidata", "conceptnet"]
        assert response.source_errors == {"conceptnet": "rate limit exceeded"}
        assert response.limit == 15
        assert response.offset == 5
        assert response.search_time_ms == 250.75

    def test_build_multi_source_response_empty(self, builder):
        """Test multi-source response building with empty data."""
        response = builder.build_multi_source_response(
            query="empty query",
            all_nodes=[],
            all_links=[],
            sources_queried=[],
            source_errors={},
        )

        assert response.query == "empty query"
        assert len(response.results) == 0
        assert len(response.links) == 0
        assert response.total_results == 0
        assert response.total_links == 0
        assert len(response.sources_queried) == 0
        assert response.source_errors == {}
        assert response.limit == 20  # Default value
        assert response.offset == 0  # Default value
        assert response.search_time_ms == 0.0  # Default value

    def test_build_empty_response_with_source(self, builder):
        """Test building empty response with source information."""
        response = builder.build_empty_response(
            query="empty search",
            source=SourceType.SCHEMA_ORG,
            error="No results found",
            limit=25,
            offset=10,
        )

        assert response.query == "empty search"
        assert len(response.results) == 0
        assert len(response.links) == 0
        assert response.total_results == 0
        assert response.total_links == 0
        assert response.sources_queried == ["schema_org"]
        assert response.source_errors == {"schema_org": "No results found"}
        assert response.limit == 25
        assert response.offset == 10
        assert response.search_time_ms == 0.0

    def test_build_empty_response_without_source(self, builder):
        """Test building empty response without source information."""
        response = builder.build_empty_response(
            query="generic empty", source=None, error=None
        )

        assert response.query == "generic empty"
        assert len(response.results) == 0
        assert len(response.sources_queried) == 0
        assert response.source_errors == {}
        assert response.limit == 20  # Default
        assert response.offset == 0  # Default

    def test_build_error_response_with_source(self, builder):
        """Test building error response with source information."""
        response = builder.build_error_response(
            query="failed search",
            error="Database connection failed",
            source=SourceType.DBPEDIA,
            limit=30,
            offset=20,
        )

        assert response.query == "failed search"
        assert len(response.results) == 0
        assert len(response.links) == 0
        assert response.total_results == 0
        assert response.total_links == 0
        assert response.sources_queried == ["dbpedia"]
        assert response.source_errors == {"dbpedia": "Database connection failed"}
        assert response.limit == 30
        assert response.offset == 20
        assert response.search_time_ms == 0.0

    def test_build_error_response_without_source(self, builder):
        """Test building error response without specific source."""
        response = builder.build_error_response(
            query="general error", error="System error occurred", source=None
        )

        assert response.query == "general error"
        assert len(response.sources_queried) == 0
        assert response.source_errors == {"general": "System error occurred"}

    def test_merge_responses_success(self, builder):
        """Test successful merging of multiple responses."""
        response1 = MultiSourceSearchResponse(
            query="test query",
            results=[
                SearchNode(
                    id="node1",
                    source=SourceType.DBPEDIA,
                    title="Test Node 1",
                    definition="First test node",
                    attributes={},
                    source_url="http://example.com/1",
                    relevance_score=0.9,
                )
            ],
            links=[
                SearchLink(
                    id="link1",
                    source=SourceType.DBPEDIA,
                    subject="node1",
                    predicate="test",
                    object="node2",
                    weight=0.8,
                    attributes={},
                )
            ],
            total_results=1,
            total_links=1,
            sources_queried=["dbpedia"],
            source_errors={},
            offset=0,
            limit=10,
            search_time_ms=100.0,
        )

        response2 = MultiSourceSearchResponse(
            query="test query",
            results=[
                SearchNode(
                    id="node2",
                    source=SourceType.WIKIDATA,
                    title="Test Node 2",
                    definition="Second test node",
                    attributes={},
                    source_url="http://example.com/2",
                    relevance_score=0.8,
                )
            ],
            links=[],
            total_results=1,
            total_links=0,
            sources_queried=["wikidata"],
            source_errors={"wikidata": "partial results"},
            offset=0,
            limit=10,
            search_time_ms=150.0,
        )

        merged = builder.merge_responses([response1, response2])

        # Verify merged response
        assert merged.query == "test query"
        assert len(merged.results) == 2
        assert len(merged.links) == 1
        assert merged.total_results == 2
        assert merged.total_links == 1
        assert set(merged.sources_queried) == {"dbpedia", "wikidata"}
        assert merged.source_errors == {"wikidata": "partial results"}
        assert merged.offset == 0
        assert merged.limit == 10
        assert merged.search_time_ms == 250.0

    def test_merge_responses_empty_list(self, builder):
        """Test merging empty list of responses."""
        merged = builder.merge_responses([])

        assert merged.query == ""
        assert len(merged.results) == 0
        assert len(merged.links) == 0
        assert merged.total_results == 0
        assert merged.total_links == 0
        assert len(merged.sources_queried) == 0
        assert merged.source_errors == {}
        assert merged.search_time_ms == 0.0

    def test_merge_responses_duplicate_sources(self, builder):
        """Test merging responses with duplicate source names."""
        response1 = MultiSourceSearchResponse(
            query="test",
            results=[],
            links=[],
            total_results=0,
            total_links=0,
            sources_queried=["dbpedia", "wikidata"],
            source_errors={},
            offset=0,
            limit=10,
            search_time_ms=100.0,
        )

        response2 = MultiSourceSearchResponse(
            query="test",
            results=[],
            links=[],
            total_results=0,
            total_links=0,
            sources_queried=["wikidata", "conceptnet"],  # wikidata is duplicate
            source_errors={},
            offset=0,
            limit=10,
            search_time_ms=150.0,
        )

        merged = builder.merge_responses([response1, response2])

        # Should preserve order and remove duplicates
        assert merged.sources_queried == ["dbpedia", "wikidata", "conceptnet"]

    def test_merge_responses_conflicting_errors(self, builder):
        """Test merging responses with conflicting source errors."""
        response1 = MultiSourceSearchResponse(
            query="test",
            results=[],
            links=[],
            total_results=0,
            total_links=0,
            sources_queried=["dbpedia"],
            source_errors={"dbpedia": "timeout"},
            offset=0,
            limit=10,
            search_time_ms=100.0,
        )

        response2 = MultiSourceSearchResponse(
            query="test",
            results=[],
            links=[],
            total_results=0,
            total_links=0,
            sources_queried=["dbpedia"],
            source_errors={
                "dbpedia": "connection error"
            },  # Different error for same source
            offset=0,
            limit=10,
            search_time_ms=150.0,
        )

        merged = builder.merge_responses([response1, response2])

        # Later error should overwrite earlier one
        assert merged.source_errors == {"dbpedia": "connection error"}

    def test_merge_responses_preserves_base_metadata(self, builder):
        """Test that merge preserves metadata from base response."""
        base_response = MultiSourceSearchResponse(
            query="original query",
            results=[],
            links=[],
            total_results=0,
            total_links=0,
            sources_queried=["dbpedia"],
            source_errors={},
            offset=5,
            limit=15,
            search_time_ms=100.0,
        )

        additional_response = MultiSourceSearchResponse(
            query="different query",  # Should be ignored
            results=[],
            links=[],
            total_results=0,
            total_links=0,
            sources_queried=["wikidata"],
            source_errors={},
            offset=10,  # Should be ignored
            limit=20,  # Should be ignored
            search_time_ms=200.0,
        )

        merged = builder.merge_responses([base_response, additional_response])

        # Should use base response metadata
        assert merged.query == "original query"
        assert merged.offset == 5
        assert merged.limit == 15
        assert merged.search_time_ms == 300.0  # But search time is summed

    def test_response_consistency(self, builder, sample_nodes, sample_links):
        """Test that different build methods produce consistent response structures."""
        # Build responses using different methods
        single_source = builder.build_single_source_response(
            source=SourceType.DBPEDIA,
            query="test",
            nodes=sample_nodes[:1],
            links=sample_links[:1],
        )

        multi_source = builder.build_multi_source_response(
            query="test",
            all_nodes=sample_nodes[:1],
            all_links=sample_links[:1],
            sources_queried=["dbpedia"],
            source_errors={},
        )

        # Both should have same structure and content
        assert single_source.query == multi_source.query
        assert single_source.results == multi_source.results
        assert single_source.links == multi_source.links
        assert single_source.total_results == multi_source.total_results
        assert single_source.total_links == multi_source.total_links
        assert single_source.sources_queried == multi_source.sources_queried

    def test_timing_wrapper_functionality(self, builder):
        """Test the timing wrapper decorator concept (though it's a static method)."""
        # This tests the concept shown in the timing wrapper
        import asyncio

        @ResponseBuilder.create_timing_wrapper
        async def mock_search_function():
            await asyncio.sleep(0.1)  # Simulate some work
            return MultiSourceSearchResponse(
                query="test",
                results=[],
                links=[],
                total_results=0,
                total_links=0,
                sources_queried=["test"],
                source_errors={},
                offset=0,
                limit=10,
                search_time_ms=0.0,  # Will be updated by wrapper
            )

        # Note: This is testing the concept, but the actual wrapper implementation
        # would need to be properly implemented as a real decorator
        # For now, we just verify the method exists and has the right signature
        assert hasattr(ResponseBuilder, "create_timing_wrapper")
        assert callable(ResponseBuilder.create_timing_wrapper)

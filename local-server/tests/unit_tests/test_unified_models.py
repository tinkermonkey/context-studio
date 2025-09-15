"""Unit tests for unified reference models"""

import pytest
from pydantic import ValidationError
from datetime import datetime

# Add parent directories to path to find modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enrichment.unified.models import (
    ReferenceSource,
    UnifiedNode,
    UnifiedLink,
    UnifiedSearchRequest,
    UnifiedSearchResponse,
    UnifiedLinksRequest,
    UnifiedLinksResponse
)


class TestReferenceSource:
    """Test ReferenceSource enum"""

    def test_all_sources_available(self):
        """Test that all expected sources are available"""
        expected_sources = {"conceptnet", "wordnet", "dbpedia", "wikidata", "schema_org"}
        available_sources = {source.value for source in ReferenceSource}
        assert expected_sources == available_sources

    def test_source_values(self):
        """Test specific source values"""
        assert ReferenceSource.CONCEPTNET.value == "conceptnet"
        assert ReferenceSource.WORDNET.value == "wordnet"
        assert ReferenceSource.DBPEDIA.value == "dbpedia"
        assert ReferenceSource.WIKIDATA.value == "wikidata"
        assert ReferenceSource.SCHEMA_ORG.value == "schema_org"


class TestUnifiedNode:
    """Test UnifiedNode model"""

    def test_valid_node_creation(self):
        """Test creating a valid node"""
        node = UnifiedNode(
            id="test_id",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple",
            title="Apple",
            definition="A fruit or a company",
            attributes={"type": "fruit"},
            source_url="http://conceptnet.io/c/en/apple",
            confidence_score=0.95
        )

        assert node.id == "test_id"
        assert node.source == ReferenceSource.CONCEPTNET
        assert node.source_id == "/c/en/apple"
        assert node.title == "Apple"
        assert node.definition == "A fruit or a company"
        assert node.attributes == {"type": "fruit"}
        assert node.source_url == "http://conceptnet.io/c/en/apple"
        assert node.confidence_score == 0.95
        assert node.merged_from is None

    def test_minimal_node_creation(self):
        """Test creating a node with minimal required fields"""
        node = UnifiedNode(
            id="minimal_id",
            source=ReferenceSource.WORDNET,
            source_id="test.n.01",
            title="Test"
        )

        assert node.id == "minimal_id"
        assert node.source == ReferenceSource.WORDNET
        assert node.source_id == "test.n.01"
        assert node.title == "Test"
        assert node.definition is None
        assert node.attributes == {}
        assert node.source_url is None
        assert node.confidence_score == 1.0
        assert node.merged_from is None

    def test_invalid_confidence_score(self):
        """Test validation of confidence score bounds"""
        # Test score > 1.0
        with pytest.raises(ValidationError) as exc_info:
            UnifiedNode(
                id="test_id",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/test",
                title="Test",
                confidence_score=1.5
            )
        assert "Input should be less than or equal to 1" in str(exc_info.value)

        # Test score < 0
        with pytest.raises(ValidationError) as exc_info:
            UnifiedNode(
                id="test_id",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/test",
                title="Test",
                confidence_score=-0.1
            )
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_invalid_url(self):
        """Test validation of source URL"""
        with pytest.raises(ValidationError) as exc_info:
            UnifiedNode(
                id="test_id",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/test",
                title="Test",
                source_url="invalid_url"
            )
        assert "Invalid URL format" in str(exc_info.value)

    def test_empty_title(self):
        """Test validation of empty title"""
        with pytest.raises(ValidationError) as exc_info:
            UnifiedNode(
                id="test_id",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/test",
                title=""
            )
        assert "String should have at least 1 character" in str(exc_info.value)


class TestUnifiedLink:
    """Test UnifiedLink model"""

    def test_valid_link_creation(self):
        """Test creating a valid link"""
        link = UnifiedLink(
            id="link_id",
            source=ReferenceSource.CONCEPTNET,
            subject="subject_id",
            predicate="IsA",
            object="object_id",
            weight=0.8,
            attributes={"surface_text": "an apple is a fruit"}
        )

        assert link.id == "link_id"
        assert link.source == ReferenceSource.CONCEPTNET
        assert link.subject == "subject_id"
        assert link.predicate == "IsA"
        assert link.object == "object_id"
        assert link.weight == 0.8
        assert link.attributes == {"surface_text": "an apple is a fruit"}

    def test_default_weight(self):
        """Test default weight value"""
        link = UnifiedLink(
            id="link_id",
            source=ReferenceSource.CONCEPTNET,
            subject="subject_id",
            predicate="IsA",
            object="object_id"
        )

        assert link.weight == 1.0
        assert link.attributes == {}

    def test_invalid_weight(self):
        """Test validation of weight bounds"""
        # Test weight > 1.0
        with pytest.raises(ValidationError) as exc_info:
            UnifiedLink(
                id="link_id",
                source=ReferenceSource.CONCEPTNET,
                subject="subject_id",
                predicate="IsA",
                object="object_id",
                weight=1.5
            )
        assert "Input should be less than or equal to 1" in str(exc_info.value)

        # Test weight < 0
        with pytest.raises(ValidationError) as exc_info:
            UnifiedLink(
                id="link_id",
                source=ReferenceSource.CONCEPTNET,
                subject="subject_id",
                predicate="IsA",
                object="object_id",
                weight=-0.1
            )
        assert "Input should be greater than or equal to 0" in str(exc_info.value)


class TestUnifiedSearchRequest:
    """Test UnifiedSearchRequest model"""

    def test_valid_search_request(self):
        """Test creating a valid search request"""
        request = UnifiedSearchRequest(
            query="apple",
            search_type="title",
            sources=[ReferenceSource.CONCEPTNET, ReferenceSource.WORDNET],
            limit=10,
            offset=0
        )

        assert request.query == "apple"
        assert request.search_type == "title"
        assert request.sources == [ReferenceSource.CONCEPTNET, ReferenceSource.WORDNET]
        assert request.limit == 10
        assert request.offset == 0

    def test_default_values(self):
        """Test default values for search request"""
        request = UnifiedSearchRequest(query="test")

        assert request.query == "test"
        assert request.search_type == "title"
        assert request.sources is None
        assert request.limit == 20
        assert request.offset == 0
        assert request.direction == "both"

    def test_invalid_search_type(self):
        """Test validation of search type"""
        with pytest.raises(ValidationError) as exc_info:
            UnifiedSearchRequest(
                query="test",
                search_type="invalid"
            )
        assert "String should match pattern" in str(exc_info.value)

    def test_invalid_direction(self):
        """Test validation of direction"""
        with pytest.raises(ValidationError) as exc_info:
            UnifiedSearchRequest(
                query="test",
                direction="invalid"
            )
        assert "String should match pattern" in str(exc_info.value)

    def test_limit_bounds(self):
        """Test limit validation"""
        # Test limit too large
        with pytest.raises(ValidationError) as exc_info:
            UnifiedSearchRequest(
                query="test",
                limit=150
            )
        assert "Input should be less than or equal to 100" in str(exc_info.value)

        # Test limit too small
        with pytest.raises(ValidationError) as exc_info:
            UnifiedSearchRequest(
                query="test",
                limit=0
            )
        assert "Input should be greater than or equal to 1" in str(exc_info.value)

    def test_negative_offset(self):
        """Test negative offset validation"""
        with pytest.raises(ValidationError) as exc_info:
            UnifiedSearchRequest(
                query="test",
                offset=-1
            )
        assert "Input should be greater than or equal to 0" in str(exc_info.value)


class TestUnifiedSearchResponse:
    """Test UnifiedSearchResponse model"""

    def test_valid_search_response(self):
        """Test creating a valid search response"""
        node = UnifiedNode(
            id="test_id",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/test",
            title="Test"
        )

        response = UnifiedSearchResponse(
            query="test",
            results=[node],
            total_results=1,
            sources_queried=["conceptnet"],
            source_errors={},
            offset=0,
            limit=20,
            search_time_ms=150.5
        )

        assert response.query == "test"
        assert len(response.results) == 1
        assert response.results[0] == node
        assert response.total_results == 1
        assert response.sources_queried == ["conceptnet"]
        assert response.source_errors == {}
        assert response.offset == 0
        assert response.limit == 20
        assert response.search_time_ms == 150.5

    def test_empty_results(self):
        """Test response with no results"""
        response = UnifiedSearchResponse(
            query="nonexistent",
            results=[],
            total_results=0,
            sources_queried=["conceptnet", "wordnet"],
            source_errors={"dbpedia": "Connection timeout"},
            offset=0,
            limit=20,
            search_time_ms=1000.0
        )

        assert response.query == "nonexistent"
        assert response.results == []
        assert response.total_results == 0
        assert response.sources_queried == ["conceptnet", "wordnet"]
        assert response.source_errors == {"dbpedia": "Connection timeout"}


class TestUnifiedLinksRequest:
    """Test UnifiedLinksRequest model"""

    def test_valid_links_request(self):
        """Test creating a valid links request"""
        request = UnifiedLinksRequest(
            node_id="test_node_id",
            direction="from",
            sources=[ReferenceSource.CONCEPTNET],
            limit=25
        )

        assert request.node_id == "test_node_id"
        assert request.direction == "from"
        assert request.sources == [ReferenceSource.CONCEPTNET]
        assert request.limit == 25

    def test_default_values(self):
        """Test default values for links request"""
        request = UnifiedLinksRequest(node_id="test_id")

        assert request.node_id == "test_id"
        assert request.direction == "both"
        assert request.sources is None
        assert request.limit == 50

    def test_limit_bounds(self):
        """Test limit validation"""
        # Test limit too large
        with pytest.raises(ValidationError) as exc_info:
            UnifiedLinksRequest(
                node_id="test_id",
                limit=250
            )
        assert "Input should be less than or equal to 200" in str(exc_info.value)

        # Test limit too small
        with pytest.raises(ValidationError) as exc_info:
            UnifiedLinksRequest(
                node_id="test_id",
                limit=0
            )
        assert "Input should be greater than or equal to 1" in str(exc_info.value)


class TestUnifiedLinksResponse:
    """Test UnifiedLinksResponse model"""

    def test_valid_links_response(self):
        """Test creating a valid links response"""
        link = UnifiedLink(
            id="link_id",
            source=ReferenceSource.CONCEPTNET,
            subject="subject_id",
            predicate="IsA",
            object="object_id"
        )

        response = UnifiedLinksResponse(
            node_id="test_node_id",
            links=[link],
            total_links=1,
            sources_queried=["conceptnet"],
            source_errors={}
        )

        assert response.node_id == "test_node_id"
        assert len(response.links) == 1
        assert response.links[0] == link
        assert response.total_links == 1
        assert response.sources_queried == ["conceptnet"]
        assert response.source_errors == {}

    def test_empty_links(self):
        """Test response with no links"""
        response = UnifiedLinksResponse(
            node_id="isolated_node",
            links=[],
            total_links=0,
            sources_queried=["conceptnet", "wordnet"],
            source_errors={"wikidata": "Service unavailable"}
        )

        assert response.node_id == "isolated_node"
        assert response.links == []
        assert response.total_links == 0
        assert response.sources_queried == ["conceptnet", "wordnet"]
        assert response.source_errors == {"wikidata": "Service unavailable"}
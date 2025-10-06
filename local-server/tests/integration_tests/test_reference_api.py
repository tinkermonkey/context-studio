"""
Integration tests for the Reference API endpoints - Updated for new architecture.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from datetime import datetime, UTC
from reference_api.models import (
    SourceType, SearchNode, SearchLink, MultiSourceSearchResponse
)


class TestReferenceAPIIntegration:
    """Integration tests for reference API endpoints"""

    def test_health_endpoint(self, client):
        """Test the reference health endpoint"""
        response = client.get("/api/reference/health")

        assert response.status_code == 200
        data = response.json()
        assert "overall" in data
        assert "sources" in data
        assert "timestamp" in data
        assert isinstance(data["sources"], dict)

    def test_dbpedia_search_endpoint_success(self, client):
        """Test DBpedia search endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.dbpedia_search"
        ) as mock_search:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_search.return_value = MultiSourceSearchResponse(
                query="Apple",
                results=[
                    SearchNode(
                        id="dbpedia:http://dbpedia.org/resource/Apple",
                        source=SourceType.DBPEDIA,
                        title="Apple",
                        definition="A fruit",
                        attributes={"types": ["Food"], "uri": "http://dbpedia.org/resource/Apple", "raw_score": 0.95},
                        source_url="http://dbpedia.org/resource/Apple",
                        relevance_score=0.95
                    )
                ],
                links=[],
                total_results=1,
                total_links=0,
                sources_queried=["dbpedia"],
                source_errors={},
                offset=0,
                limit=5,
                search_time_ms=100.0
            )

            response = client.get(
                "/api/reference/dbpedia/search",
                params={"query": "Apple", "limit": 5},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "Apple"
            assert "results" in data
            assert len(data["results"]) == 1
            assert data["total_results"] == 1
            assert "dbpedia" in data["sources_queried"]

    def test_dbpedia_search_endpoint_validation_error(self, client):
        """Test DBpedia search endpoint with validation error"""
        response = client.get(
            "/api/reference/dbpedia/search",
            params={"query": "Apple", "limit": 101},  # Exceeds max limit
        )

        assert response.status_code == 422  # Validation error

    def test_dbpedia_resource_endpoint_success(self, client):
        """Test DBpedia resource endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.dbpedia_get_resource"
        ) as mock_resource:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_resource.return_value = MultiSourceSearchResponse(
                query="http://dbpedia.org/resource/Apple",
                results=[
                    SearchNode(
                        id="dbpedia:http://dbpedia.org/resource/Apple",
                        source=SourceType.DBPEDIA,
                        title="Apple",
                        definition="A fruit",
                        attributes={"uri": "http://dbpedia.org/resource/Apple", "data_url": "http://dbpedia.org/data/Apple.json"},
                        source_url="http://dbpedia.org/resource/Apple",
                        relevance_score=1.0
                    )
                ],
                links=[],
                total_results=1,
                total_links=0,
                sources_queried=["dbpedia"],
                source_errors={},
                offset=0,
                limit=1,
                search_time_ms=100.0
            )

            response = client.get(
                "/api/reference/dbpedia/resource",
                params={"resource_url": "http://dbpedia.org/resource/Apple"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "http://dbpedia.org/resource/Apple"
            assert "results" in data
            assert len(data["results"]) == 1
            assert data["results"][0]["id"] == "dbpedia:http://dbpedia.org/resource/Apple"

    def test_dbpedia_sparql_endpoint_success(self, client):
        """Test DBpedia SPARQL endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.dbpedia_sparql"
        ) as mock_sparql:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_sparql.return_value = MultiSourceSearchResponse(
                query="SELECT ?s WHERE { ?s a ?o } LIMIT 10",
                results=[],
                links=[],
                total_results=0,
                total_links=0,
                sources_queried=["dbpedia"],
                source_errors={},
                offset=0,
                limit=20,
                search_time_ms=100.0
            )

            response = client.post(
                "/api/reference/dbpedia/sparql",
                json={
                    "query": "SELECT ?s WHERE { ?s a ?o } LIMIT 10",
                    "format": "json",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "SELECT ?s WHERE { ?s a ?o } LIMIT 10"
            assert "dbpedia" in data["sources_queried"]
            assert data["total_results"] == 0

    def test_conceptnet_query_endpoint_success(self, client):
        """Test ConceptNet query endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.conceptnet_query"
        ) as mock_query:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_query.return_value = MultiSourceSearchResponse(
                query="/c/en/apple",
                results=[
                    SearchNode(
                        id="conceptnet:/c/en/apple",
                        source=SourceType.CONCEPTNET,
                        title="apple",
                        definition=None,
                        attributes={"language": "en", "concept_uri": "/c/en/apple"},
                        source_url="http://conceptnet.io/c/en/apple",
                        relevance_score=0.8
                    ),
                    SearchNode(
                        id="conceptnet:/c/en/fruit",
                        source=SourceType.CONCEPTNET,
                        title="fruit",
                        definition=None,
                        attributes={"language": "en", "concept_uri": "/c/en/fruit"},
                        source_url="http://conceptnet.io/c/en/fruit",
                        relevance_score=0.8
                    )
                ],
                links=[
                    SearchLink(
                        id="conceptnet:/c/en/apple-/r/IsA-/c/en/fruit",
                        source=SourceType.CONCEPTNET,
                        subject="conceptnet:/c/en/apple",
                        predicate="IsA",
                        object="conceptnet:/c/en/fruit",
                        weight=0.8,
                        attributes={"edge_uri": "/c/en/apple-/r/IsA-/c/en/fruit", "relation_uri": "/r/IsA"}
                    )
                ],
                total_results=2,
                total_links=1,
                sources_queried=["conceptnet"],
                source_errors={},
                offset=0,
                limit=20,
                search_time_ms=150.0
            )

            response = client.get(
                "/api/reference/conceptnet/query",
                params={"start": "/c/en/apple", "limit": 20},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "/c/en/apple"
            assert "conceptnet" in data["sources_queried"]
            assert len(data["results"]) == 2
            assert len(data["links"]) == 1

    def test_conceptnet_concept_endpoint_success(self, client):
        """Test ConceptNet concept endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.conceptnet_get_concept"
        ) as mock_concept:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_concept.return_value = MultiSourceSearchResponse(
                query="/c/en/apple",
                results=[
                    SearchNode(
                        id="conceptnet:/c/en/apple",
                        source=SourceType.CONCEPTNET,
                        title="apple",
                        definition=None,
                        attributes={"language": "en", "concept_uri": "/c/en/apple", "raw_data": {"id": "/c/en/apple", "label": "apple", "language": "en"}},
                        source_url="http://conceptnet.io/c/en/apple",
                        relevance_score=1.0
                    )
                ],
                links=[],
                total_results=1,
                total_links=0,
                sources_queried=["conceptnet"],
                source_errors={},
                offset=0,
                limit=1,
                search_time_ms=100.0
            )

            response = client.get(
                "/api/reference/conceptnet/concept/c/en/apple"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "/c/en/apple"
            assert "conceptnet" in data["sources_queried"]
            assert len(data["results"]) == 1

    def test_conceptnet_related_endpoint_success(self, client):
        """Test ConceptNet related concepts endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.conceptnet_get_related"
        ) as mock_related:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_related.return_value = MultiSourceSearchResponse(
                query="/c/en/apple",
                results=[
                    SearchNode(
                        id="conceptnet:/c/en/fruit",
                        source=SourceType.CONCEPTNET,
                        title="fruit",
                        definition=None,
                        attributes={"language": "en", "concept_uri": "/c/en/fruit"},
                        source_url="http://conceptnet.io/c/en/fruit",
                        relevance_score=0.8
                    )
                ],
                links=[],
                total_results=1,
                total_links=0,
                sources_queried=["conceptnet"],
                source_errors={},
                offset=0,
                limit=10,
                search_time_ms=100.0
            )

            response = client.get(
                "/api/reference/conceptnet/related/c/en/apple",
                params={"limit": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "/c/en/apple"
            assert "conceptnet" in data["sources_queried"]
            assert len(data["results"]) == 1

    def test_wikidata_sparql_endpoint_success(self, client):
        """Test Wikidata SPARQL endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.wikidata_sparql"
        ) as mock_sparql:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_sparql.return_value = MultiSourceSearchResponse(
                query="SELECT ?item WHERE { ?item wdt:P31 wd:Q5 } LIMIT 10",
                results=[],
                links=[],
                total_results=0,
                total_links=0,
                sources_queried=["wikidata"],
                source_errors={},
                offset=0,
                limit=20,
                search_time_ms=200.0
            )

            response = client.post(
                "/api/reference/wikidata/sparql",
                json={
                    "query": "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 } LIMIT 10",
                    "format": "json",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 } LIMIT 10"
            assert "wikidata" in data["sources_queried"]

    def test_wikidata_entity_endpoint_success(self, client):
        """Test Wikidata entity endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.wikidata_get_entity"
        ) as mock_entity:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_entity.return_value = MultiSourceSearchResponse(
                query="http://www.wikidata.org/entity/Q312",
                results=[
                    SearchNode(
                        id="wikidata:http://www.wikidata.org/entity/Q312",
                        source=SourceType.WIKIDATA,
                        title="Apple",
                        definition="Fruit of the apple tree",
                        attributes={"entity_id": "Q312", "uri": "http://www.wikidata.org/entity/Q312"},
                        source_url="http://www.wikidata.org/entity/Q312",
                        relevance_score=1.0
                    )
                ],
                links=[],
                total_results=1,
                total_links=0,
                sources_queried=["wikidata"],
                source_errors={},
                offset=0,
                limit=1,
                search_time_ms=150.0
            )

            response = client.get(
                "/api/reference/wikidata/entity",
                params={"entity_url": "http://www.wikidata.org/entity/Q312"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "http://www.wikidata.org/entity/Q312"
            assert "wikidata" in data["sources_queried"]
            assert len(data["results"]) == 1
            assert data["results"][0]["attributes"]["entity_id"] == "Q312"

    def test_schema_org_entity_endpoint_success(self, client):
        """Test Schema.org entity endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.schema_org_get_entity"
        ) as mock_entity:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_entity.return_value = MultiSourceSearchResponse(
                query="Person",
                results=[
                    SearchNode(
                        id="schema_org:Person",
                        source=SourceType.SCHEMA_ORG,
                        title="Person",
                        definition="A person (alive, dead, undead, or fictional).",
                        attributes={"identifier": "Person", "parent_identifier": "Thing", "properties": [], "children": []},
                        source_url="https://schema.org/Person",
                        relevance_score=1.0
                    )
                ],
                links=[],
                total_results=1,
                total_links=0,
                sources_queried=["schema_org"],
                source_errors={},
                offset=0,
                limit=1,
                search_time_ms=100.0
            )

            response = client.get(
                "/api/reference/schema-org/entity/Person"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "Person"
            assert "schema_org" in data["sources_queried"]
            assert len(data["results"]) == 1

    def test_schema_org_property_endpoint_success(self, client):
        """Test Schema.org property endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.schema_org_get_property"
        ) as mock_property:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_property.return_value = MultiSourceSearchResponse(
                query="name",
                results=[
                    SearchNode(
                        id="schema_org:name",
                        source=SourceType.SCHEMA_ORG,
                        title="name",
                        definition="The name of the item.",
                        attributes={"identifier": "name", "domain_includes": ["Thing"], "range_includes": ["Text"], "inverse_of": [], "used_by_entities": []},
                        source_url="https://schema.org/name",
                        relevance_score=1.0
                    )
                ],
                links=[],
                total_results=1,
                total_links=0,
                sources_queried=["schema_org"],
                source_errors={},
                offset=0,
                limit=1,
                search_time_ms=100.0
            )

            response = client.get(
                "/api/reference/schema-org/property/name"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "name"
            assert "schema_org" in data["sources_queried"]
            assert len(data["results"]) == 1

    def test_schema_org_search_endpoint_success(self, client):
        """Test Schema.org search endpoint with successful response"""
        with patch(
            "reference_api.service.ReferenceService.schema_org_search"
        ) as mock_search:
            # Mock returns MultiSourceSearchResponse instead of dict
            mock_search.return_value = MultiSourceSearchResponse(
                query="person",
                results=[
                    SearchNode(
                        id="schema_org:Person",
                        source=SourceType.SCHEMA_ORG,
                        title="Person",
                        definition="A person.",
                        attributes={"type": "entity", "identifier": "Person"},
                        source_url="https://schema.org/Person",
                        relevance_score=0.95
                    )
                ],
                links=[],
                total_results=1,
                total_links=0,
                sources_queried=["schema_org"],
                source_errors={},
                offset=0,
                limit=10,
                search_time_ms=100.0
            )

            response = client.get(
                "/api/reference/schema-org/search",
                params={"query": "person", "limit": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "person"
            assert "schema_org" in data["sources_queried"]
            assert len(data["results"]) == 1

    def test_service_error_handling(self, client):
        """Test API error handling for service errors"""
        with patch(
            "reference_api.service.ReferenceService.dbpedia_search"
        ) as mock_search:
            from reference_api.exceptions import SourceTimeoutError

            mock_search.side_effect = SourceTimeoutError("Request timed out")

            response = client.get(
                "/api/reference/dbpedia/search",
                params={"query": "Apple", "limit": 5},
            )

            assert response.status_code == 504  # Gateway timeout
            assert "Request timed out" in response.json()["detail"]

    def test_source_unavailable_error_handling(self, client):
        """Test API error handling for source unavailable errors"""
        with patch(
            "reference_api.service.ReferenceService.conceptnet_query"
        ) as mock_query:
            from reference_api.exceptions import SourceError

            mock_query.side_effect = SourceError("ConceptNet unavailable")

            response = client.get(
                "/api/reference/conceptnet/query",
                params={"start": "/c/en/apple"},
            )

            assert response.status_code == 503  # Service unavailable
            assert "ConceptNet unavailable" in response.json()["detail"]

    def test_reference_error_handling(self, client):
        """Test API error handling for reference errors"""
        with patch(
            "reference_api.service.ReferenceService.wikidata_get_entity"
        ) as mock_entity:
            from reference_api.exceptions import ReferenceError

            mock_entity.side_effect = ReferenceError("Invalid entity URL")

            response = client.get(
                "/api/reference/wikidata/entity",
                params={"entity_url": "http://www.wikidata.org/entity/Q999999999"},
            )

            assert response.status_code == 400  # Bad request
            assert "Invalid entity URL" in response.json()["detail"]

    def test_unexpected_error_handling(self, client):
        """Test API error handling for unexpected errors"""
        with patch(
            "reference_api.service.ReferenceService.schema_org_get_entity"
        ) as mock_entity:
            mock_entity.side_effect = RuntimeError("Unexpected error")

            response = client.get(
                "/api/reference/schema-org/entity/Person"
            )

            assert response.status_code == 500  # Internal server error
            assert "Internal server error" in response.json()["detail"]

    def test_health_endpoint_service_failure(self, client):
        """Test health endpoint when service fails"""
        with patch("reference_api.service.ReferenceService.health_check") as mock_health:
            mock_health.side_effect = RuntimeError("Health check failed")

            response = client.get("/api/reference/health")

            assert response.status_code == 503  # Service unavailable
            data = response.json()
            assert data["overall"] == "unhealthy"
            assert "Health check failed" in data["error"]

    def test_endpoint_parameter_validation(self, client):
        """Test endpoint parameter validation"""
        # Test negative limit
        response = client.get(
            "/api/reference/dbpedia/search",
            params={"query": "Apple", "limit": -1},
        )
        assert response.status_code == 422

        # Test limit too high
        response = client.get(
            "/api/reference/conceptnet/query",
            params={"start": "/c/en/apple", "limit": 101},
        )
        assert response.status_code == 422

        # Test negative offset
        response = client.get(
            "/api/reference/dbpedia/search",
            params={"query": "Apple", "offset": -1},
        )
        assert response.status_code == 422

    def test_missing_required_parameters(self, client):
        """Test endpoints with missing required parameters"""
        # Test DBpedia search without query
        response = client.get("/api/reference/dbpedia/search")
        assert response.status_code == 422

        # Test DBpedia resource without resource_url
        response = client.get("/api/reference/dbpedia/resource")
        assert response.status_code == 422

        # Test Wikidata entity without entity_url
        response = client.get("/api/reference/wikidata/entity")
        assert response.status_code == 422

    def test_schema_org_search_type_validation(self, client):
        """Test Schema.org search endpoint with invalid search type"""
        response = client.get(
            "/api/reference/schema-org/search",
            params={"query": "person", "search_type": "invalid"},
        )
        assert response.status_code == 422

    def test_similarity_threshold_validation(self, client):
        """Test Schema.org search endpoint with invalid similarity threshold"""
        # Test threshold too high
        response = client.get(
            "/api/reference/schema-org/search",
            params={"query": "person", "similarity_threshold": 1.5},
        )
        assert response.status_code == 422

        # Test negative threshold
        response = client.get(
            "/api/reference/schema-org/search",
            params={"query": "person", "similarity_threshold": -0.1},
        )
        assert response.status_code == 422

    def test_multi_source_search_endpoint_success(self, client):
        """Test multi-source search endpoint with successful response"""
        with patch("reference_api.service.ReferenceService.search") as mock_search:
            # Mock returns MultiSourceSearchResponse directly (already the correct format)
            mock_search.return_value = MultiSourceSearchResponse(
                query="apple",
                results=[
                    SearchNode(
                        id="dbpedia:http://dbpedia.org/resource/Apple",
                        source=SourceType.DBPEDIA,
                        title="Apple",
                        definition="A fruit",
                        attributes={"types": ["Food"]},
                        source_url="http://dbpedia.org/resource/Apple",
                        relevance_score=0.95
                    ),
                    SearchNode(
                        id="conceptnet:/c/en/apple",
                        source=SourceType.CONCEPTNET,
                        title="apple",
                        definition=None,
                        attributes={"weight": 0.8},
                        source_url="http://conceptnet.io/c/en/apple",
                        relevance_score=0.8
                    )
                ],
                links=[],
                total_results=2,
                total_links=0,
                sources_queried=["dbpedia", "conceptnet"],
                source_errors={},
                offset=0,
                limit=20,
                search_time_ms=150.5
            )

            response = client.post(
                "/api/reference/search",
                json={
                    "query": "apple",
                    "sources": ["dbpedia", "conceptnet"],
                    "limit": 20,
                    "offset": 0
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "apple"
            assert len(data["results"]) == 2
            assert data["total_results"] == 2
            assert "dbpedia" in data["sources_queried"]
            assert "conceptnet" in data["sources_queried"]
            assert data["search_time_ms"] == 150.5

    def test_multi_source_search_get_endpoint_success(self, client):
        """Test multi-source search GET endpoint with successful response"""
        with patch("reference_api.service.ReferenceService.search") as mock_search:
            # Mock returns MultiSourceSearchResponse directly
            mock_search.return_value = MultiSourceSearchResponse(
                query="apple",
                results=[
                    SearchNode(
                        id="dbpedia:http://dbpedia.org/resource/Apple",
                        source=SourceType.DBPEDIA,
                        title="Apple",
                        definition="A fruit",
                        attributes={"types": ["Food"]},
                        source_url="http://dbpedia.org/resource/Apple",
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

            response = client.get(
                "/api/reference/search",
                params={
                    "query": "apple",
                    "sources": "dbpedia",
                    "limit": 10,
                    "offset": 0
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "apple"
            assert len(data["results"]) == 1
            assert data["total_results"] == 1
            assert "dbpedia" in data["sources_queried"]

    def test_multi_source_search_with_source_errors(self, client):
        """Test multi-source search with some source errors"""
        with patch("reference_api.service.ReferenceService.search") as mock_search:
            # Mock returns MultiSourceSearchResponse with source errors
            mock_search.return_value = MultiSourceSearchResponse(
                query="apple",
                results=[
                    SearchNode(
                        id="dbpedia:http://dbpedia.org/resource/Apple",
                        source=SourceType.DBPEDIA,
                        title="Apple",
                        definition="A fruit",
                        attributes={"types": ["Food"]},
                        source_url="http://dbpedia.org/resource/Apple",
                        relevance_score=0.95
                    )
                ],
                links=[],
                total_results=1,
                total_links=0,
                sources_queried=["dbpedia", "wikidata"],
                source_errors={"wikidata": "Timeout error"},
                offset=0,
                limit=20,
                search_time_ms=200.0
            )

            response = client.post(
                "/api/reference/search",
                json={
                    "query": "apple",
                    "sources": ["dbpedia", "wikidata"],
                    "limit": 20
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "apple"
            assert len(data["results"]) == 1
            assert "wikidata" in data["source_errors"]
            assert data["source_errors"]["wikidata"] == "Timeout error"

    def test_multi_source_search_invalid_source(self, client):
        """Test multi-source search with invalid source"""
        response = client.get(
            "/api/reference/search",
            params={
                "query": "apple",
                "sources": "invalid_source",
                "limit": 10
            }
        )

        assert response.status_code == 400
        assert "Invalid source: invalid_source" in response.json()["detail"]

    def test_multi_source_search_validation_errors(self, client):
        """Test multi-source search parameter validation"""
        # Test empty query
        response = client.post(
            "/api/reference/search",
            json={"query": "", "limit": 10}
        )
        assert response.status_code == 422

        # Test limit too high
        response = client.post(
            "/api/reference/search",
            json={"query": "apple", "limit": 101}
        )
        assert response.status_code == 422

        # Test negative offset
        response = client.post(
            "/api/reference/search",
            json={"query": "apple", "offset": -1}
        )
        assert response.status_code == 422
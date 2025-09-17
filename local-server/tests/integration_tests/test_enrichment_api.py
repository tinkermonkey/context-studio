"""
Integration tests for the Enrichment API endpoints.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch


class TestEnrichmentAPIIntegration:
    """Integration tests for enrichment API endpoints"""

    def test_health_endpoint(self, client):
        """Test the enrichment health endpoint"""
        response = client.get("/api/nlp_analysis/reference/health")

        assert response.status_code == 200
        data = response.json()
        assert "overall" in data
        assert "sources" in data
        assert "timestamp" in data
        assert isinstance(data["sources"], dict)

    def test_dbpedia_search_endpoint_success(self, client):
        """Test DBpedia search endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.dbpedia_search"
        ) as mock_search:
            mock_search.return_value = {
                "success": True,
                "source": "dbpedia",
                "results": [
                    {
                        "uri": "http://dbpedia.org/resource/Apple",
                        "label": "Apple",
                        "description": "A fruit",
                        "score": 0.95,
                        "types": ["Food"],
                    }
                ],
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.get(
                "/api/nlp_analysis/reference/dbpedia/search",
                params={"query": "Apple", "limit": 5},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "dbpedia"
            assert "results" in data
            assert len(data["results"]) == 1

    def test_dbpedia_search_endpoint_validation_error(self, client):
        """Test DBpedia search endpoint with validation error"""
        response = client.get(
            "/api/nlp_analysis/reference/dbpedia/search",
            params={"query": "Apple", "limit": 101},  # Exceeds max limit
        )

        assert response.status_code == 422  # Validation error

    def test_dbpedia_resource_endpoint_success(self, client):
        """Test DBpedia resource endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.dbpedia_get_resource"
        ) as mock_resource:
            mock_resource.return_value = {
                "success": True,
                "source": "dbpedia",
                "data": {"uri": "http://dbpedia.org/resource/Apple", "properties": {}},
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.get(
                "/api/nlp_analysis/reference/dbpedia/resource",
                params={"resource_url": "http://dbpedia.org/resource/Apple"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "dbpedia"
            assert "data" in data

    def test_dbpedia_sparql_endpoint_success(self, client):
        """Test DBpedia SPARQL endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.dbpedia_sparql"
        ) as mock_sparql:
            mock_sparql.return_value = {
                "success": True,
                "source": "dbpedia",
                "results": {"bindings": []},
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.post(
                "/api/nlp_analysis/reference/dbpedia/sparql",
                json={
                    "query": "SELECT ?s WHERE { ?s a ?o } LIMIT 10",
                    "format": "json",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "dbpedia"

    def test_conceptnet_query_endpoint_success(self, client):
        """Test ConceptNet query endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.conceptnet_query"
        ) as mock_query:
            mock_query.return_value = {
                "success": True,
                "source": "conceptnet",
                "edges": [
                    {
                        "@id": "/c/en/apple-/r/IsA-/c/en/fruit",
                        "start": {"@id": "/c/en/apple", "label": "apple"},
                        "end": {"@id": "/c/en/fruit", "label": "fruit"},
                        "rel": {"@id": "/r/IsA", "label": "IsA"},
                        "weight": 0.8,
                    }
                ],
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.get(
                "/api/nlp_analysis/reference/conceptnet/query",
                params={"start": "/c/en/apple", "limit": 20},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "conceptnet"
            assert "edges" in data

    def test_conceptnet_concept_endpoint_success(self, client):
        """Test ConceptNet concept endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.conceptnet_get_concept"
        ) as mock_concept:
            mock_concept.return_value = {
                "success": True,
                "source": "conceptnet",
                "concept": "/c/en/apple",
                "data": {"id": "/c/en/apple", "label": "apple", "language": "en"},
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.get(
                "/api/nlp_analysis/reference/conceptnet/concept/c/en/apple"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "conceptnet"
            assert "concept" in data

    def test_conceptnet_related_endpoint_success(self, client):
        """Test ConceptNet related concepts endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.conceptnet_get_related"
        ) as mock_related:
            mock_related.return_value = {
                "success": True,
                "source": "conceptnet",
                "concept": "/c/en/apple",
                "related": [{"@id": "/c/en/fruit", "label": "fruit", "weight": 2.5}],
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.get(
                "/api/nlp_analysis/reference/conceptnet/related/c/en/apple",
                params={"limit": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "conceptnet"
            assert "related" in data

    def test_wikidata_sparql_endpoint_success(self, client):
        """Test Wikidata SPARQL endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.wikidata_sparql"
        ) as mock_sparql:
            mock_sparql.return_value = {
                "success": True,
                "source": "wikidata",
                "results": {"bindings": []},
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.post(
                "/api/nlp_analysis/reference/wikidata/sparql",
                json={
                    "query": "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 } LIMIT 10",
                    "format": "json",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "wikidata"

    def test_wikidata_entity_endpoint_success(self, client):
        """Test Wikidata entity endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.wikidata_get_entity"
        ) as mock_entity:
            mock_entity.return_value = {
                "success": True,
                "source": "wikidata",
                "entity_id": "Q312",
                "entity_url": "http://www.wikidata.org/entity/Q312",
                "data": {
                    "id": "Q312",
                    "labels": {"en": {"value": "Apple"}},
                    "claims": {},
                },
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.get(
                "/api/nlp_analysis/reference/wikidata/entity",
                params={"entity_url": "http://www.wikidata.org/entity/Q312"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "wikidata"
            assert "data" in data
            assert data["entity_id"] == "Q312"

    def test_schema_org_entity_endpoint_success(self, client):
        """Test Schema.org entity endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.schema_org_get_entity"
        ) as mock_entity:
            mock_entity.return_value = {
                "success": True,
                "source": "schema_org",
                "identifier": "Person",
                "entity": {
                    "id": "Person",
                    "identifier": "Person",
                    "title": "Person",
                    "definition": "A person (alive, dead, undead, or fictional).",
                    "properties": [],
                },
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.get(
                "/api/nlp_analysis/reference/schema-org/entity/Person"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "schema_org"
            assert "entity" in data

    def test_schema_org_property_endpoint_success(self, client):
        """Test Schema.org property endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.schema_org_get_property"
        ) as mock_property:
            mock_property.return_value = {
                "success": True,
                "source": "schema_org",
                "identifier": "name",
                "property": {
                    "id": "name",
                    "identifier": "name",
                    "title": "name",
                    "definition": "The name of the item.",
                    "domain_includes": ["Thing"],
                    "range_includes": ["Text"],
                },
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.get(
                "/api/nlp_analysis/reference/schema-org/property/name"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "schema_org"
            assert "property" in data

    def test_schema_org_search_endpoint_success(self, client):
        """Test Schema.org search endpoint with successful response"""
        with patch(
            "enrichment.service.EnrichmentService.schema_org_search"
        ) as mock_search:
            mock_search.return_value = {
                "success": True,
                "source": "schema_org",
                "query": "person",
                "results": [
                    {
                        "type": "entity",
                        "identifier": "Person",
                        "title": "Person",
                        "definition": "A person.",
                        "relevance_score": 0.95,
                    }
                ],
                "retrieved_at": "2025-08-29T15:00:00Z",
            }

            response = client.get(
                "/api/nlp_analysis/reference/schema-org/search",
                params={"query": "person", "limit": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "schema_org"
            assert "results" in data

    def test_service_error_handling(self, client):
        """Test API error handling for service errors"""
        with patch(
            "enrichment.service.EnrichmentService.dbpedia_search"
        ) as mock_search:
            from enrichment.exceptions import SourceTimeoutError

            mock_search.side_effect = SourceTimeoutError("Request timed out")

            response = client.get(
                "/api/nlp_analysis/reference/dbpedia/search",
                params={"query": "Apple", "limit": 5},
            )

            assert response.status_code == 504  # Gateway timeout
            assert "Request timed out" in response.json()["detail"]

    def test_source_unavailable_error_handling(self, client):
        """Test API error handling for source unavailable errors"""
        with patch(
            "enrichment.service.EnrichmentService.conceptnet_query"
        ) as mock_query:
            from enrichment.exceptions import SourceError

            mock_query.side_effect = SourceError("ConceptNet unavailable")

            response = client.get(
                "/api/nlp_analysis/reference/conceptnet/query",
                params={"start": "/c/en/apple"},
            )

            assert response.status_code == 503  # Service unavailable
            assert "ConceptNet unavailable" in response.json()["detail"]

    def test_enrichment_error_handling(self, client):
        """Test API error handling for enrichment errors"""
        with patch(
            "enrichment.service.EnrichmentService.wikidata_get_entity"
        ) as mock_entity:
            from enrichment.exceptions import EnrichmentError

            mock_entity.side_effect = EnrichmentError("Invalid entity URL")

            response = client.get(
                "/api/nlp_analysis/reference/wikidata/entity",
                params={"entity_url": "http://www.wikidata.org/entity/Q999999999"},
            )

            assert response.status_code == 400  # Bad request
            assert "Invalid entity URL" in response.json()["detail"]

    def test_unexpected_error_handling(self, client):
        """Test API error handling for unexpected errors"""
        with patch(
            "enrichment.service.EnrichmentService.schema_org_get_entity"
        ) as mock_entity:
            mock_entity.side_effect = RuntimeError("Unexpected error")

            response = client.get(
                "/api/nlp_analysis/reference/schema-org/entity/Person"
            )

            assert response.status_code == 500  # Internal server error
            assert "Internal server error" in response.json()["detail"]

    def test_health_endpoint_service_failure(self, client):
        """Test health endpoint when service fails"""
        with patch("enrichment.service.EnrichmentService.health_check") as mock_health:
            mock_health.side_effect = RuntimeError("Health check failed")

            response = client.get("/api/nlp_analysis/reference/health")

            assert response.status_code == 503  # Service unavailable
            data = response.json()
            assert data["overall"] == "unhealthy"
            assert "Health check failed" in data["error"]

    def test_endpoint_parameter_validation(self, client):
        """Test endpoint parameter validation"""
        # Test negative limit
        response = client.get(
            "/api/nlp_analysis/reference/dbpedia/search",
            params={"query": "Apple", "limit": -1},
        )
        assert response.status_code == 422

        # Test limit too high
        response = client.get(
            "/api/nlp_analysis/reference/conceptnet/query",
            params={"start": "/c/en/apple", "limit": 101},
        )
        assert response.status_code == 422

        # Test negative offset
        response = client.get(
            "/api/nlp_analysis/reference/dbpedia/search",
            params={"query": "Apple", "offset": -1},
        )
        assert response.status_code == 422

    def test_missing_required_parameters(self, client):
        """Test endpoints with missing required parameters"""
        # Test DBpedia search without query
        response = client.get("/api/nlp_analysis/reference/dbpedia/search")
        assert response.status_code == 422

        # Test DBpedia resource without resource_url
        response = client.get("/api/nlp_analysis/reference/dbpedia/resource")
        assert response.status_code == 422

        # Test Wikidata entity without entity_url
        response = client.get("/api/nlp_analysis/reference/wikidata/entity")
        assert response.status_code == 422

    def test_schema_org_search_type_validation(self, client):
        """Test Schema.org search endpoint with invalid search type"""
        response = client.get(
            "/api/nlp_analysis/reference/schema-org/search",
            params={"query": "person", "search_type": "invalid"},
        )
        assert response.status_code == 422

    def test_similarity_threshold_validation(self, client):
        """Test Schema.org search endpoint with invalid similarity threshold"""
        # Test threshold too high
        response = client.get(
            "/api/nlp_analysis/reference/schema-org/search",
            params={"query": "person", "similarity_threshold": 1.5},
        )
        assert response.status_code == 422

        # Test negative threshold
        response = client.get(
            "/api/nlp_analysis/reference/schema-org/search",
            params={"query": "person", "similarity_threshold": -0.1},
        )
        assert response.status_code == 422

    def test_multi_source_search_endpoint_success(self, client):
        """Test multi-source search endpoint with successful response"""
        with patch("enrichment.service.EnrichmentService.search") as mock_search:
            mock_search.return_value = {
                "query": "apple",
                "results": [
                    {
                        "id": "dbpedia:http://dbpedia.org/resource/Apple",
                        "source": "dbpedia",
                        "title": "Apple",
                        "definition": "A fruit",
                        "attributes": {"types": ["Food"]},
                        "source_url": "http://dbpedia.org/resource/Apple",
                        "relevance_score": 0.95
                    },
                    {
                        "id": "conceptnet:/c/en/apple",
                        "source": "conceptnet",
                        "title": "apple",
                        "definition": "Related via IsA",
                        "attributes": {"weight": 0.8},
                        "source_url": "http://conceptnet.io/c/en/apple",
                        "relevance_score": 0.8
                    }
                ],
                "total_results": 2,
                "sources_queried": ["dbpedia", "conceptnet"],
                "source_errors": {},
                "offset": 0,
                "limit": 20,
                "search_time_ms": 150.5
            }

            response = client.post(
                "/api/nlp_analysis/reference/search",
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
        with patch("enrichment.service.EnrichmentService.search") as mock_search:
            mock_search.return_value = {
                "query": "apple",
                "results": [
                    {
                        "id": "dbpedia:http://dbpedia.org/resource/Apple",
                        "source": "dbpedia",
                        "title": "Apple",
                        "definition": "A fruit",
                        "attributes": {"types": ["Food"]},
                        "source_url": "http://dbpedia.org/resource/Apple",
                        "relevance_score": 0.95
                    }
                ],
                "total_results": 1,
                "sources_queried": ["dbpedia"],
                "source_errors": {},
                "offset": 0,
                "limit": 10,
                "search_time_ms": 100.0
            }

            response = client.get(
                "/api/nlp_analysis/reference/search",
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
        with patch("enrichment.service.EnrichmentService.search") as mock_search:
            mock_search.return_value = {
                "query": "apple",
                "results": [
                    {
                        "id": "dbpedia:http://dbpedia.org/resource/Apple",
                        "source": "dbpedia",
                        "title": "Apple",
                        "definition": "A fruit",
                        "attributes": {"types": ["Food"]},
                        "source_url": "http://dbpedia.org/resource/Apple",
                        "relevance_score": 0.95
                    }
                ],
                "total_results": 1,
                "sources_queried": ["dbpedia", "wikidata"],
                "source_errors": {"wikidata": "Timeout error"},
                "offset": 0,
                "limit": 20,
                "search_time_ms": 200.0
            }

            response = client.post(
                "/api/nlp_analysis/reference/search",
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
            "/api/nlp_analysis/reference/search",
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
            "/api/nlp_analysis/reference/search",
            json={"query": "", "limit": 10}
        )
        assert response.status_code == 422

        # Test limit too high
        response = client.post(
            "/api/nlp_analysis/reference/search",
            json={"query": "apple", "limit": 101}
        )
        assert response.status_code == 422

        # Test negative offset
        response = client.post(
            "/api/nlp_analysis/reference/search",
            json={"query": "apple", "offset": -1}
        )
        assert response.status_code == 422

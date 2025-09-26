"""Integration tests for refactored reference service."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC

from reference.service import ReferenceService
from reference.models import (
    SourceType, SearchNode, SearchLink, MultiSourceSearchResponse,
    DBpediaSearchRequest, DBpediaResourceRequest, DBpediaSparqlRequest,
    ConceptNetQueryRequest, WikidataSparqlRequest, WikidataEntityRequest, WikidataSearchRequest,
    SchemaOrgSearchRequest, SchemaOrgEntityRequest, SchemaOrgPropertyRequest,
    DBpediaSearchResponse, DBpediaSearchResult, ConceptNetQueryResponse, ConceptNetEdge,
    WikidataSparqlResponse, SchemaOrgSearchResponse, SchemaOrgSearchResult
)
from config import ConfigurationManager


class TestReferenceServiceRefactored:
    """Integration test suite for refactored ReferenceService."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager."""
        config_manager = Mock(spec=ConfigurationManager)

        # Mock settings
        settings = Mock()
        settings.reference_sources.default_language = "en"
        settings.reference_sources.search_timeout = 30

        # Mock source configs
        def mock_get_source_config(source_name):
            source_config = Mock()
            source_config.enabled = True
            source_config.use_proxy = False
            source_config.upstream_url = f"https://{source_name}.example.com"
            source_config.timeout = 10
            source_config.rate_limit.requests_per_hour = 1000
            return source_config

        settings.get_source_config = mock_get_source_config
        config_manager.settings = settings

        return config_manager

    @pytest.fixture
    def service(self, mock_config_manager):
        """Create ReferenceService instance with mocked dependencies."""
        return ReferenceService(mock_config_manager)

    @pytest.fixture
    def mock_dbpedia_source(self):
        """Create mock DBpedia source."""
        source = AsyncMock()
        source.__aenter__ = AsyncMock(return_value=source)
        source.__aexit__ = AsyncMock(return_value=None)

        # Mock search response
        search_response = DBpediaSearchResponse(
            success=True,
            source=SourceType.DBPEDIA,
            retrieved_at=datetime.now(UTC),
            query="python",
            total_results=1,
            results=[
                DBpediaSearchResult(
                    uri="http://dbpedia.org/resource/Python",
                    label="Python (programming language)",
                    description="High-level programming language",
                    score=0.95,
                    types=["ProgrammingLanguage"]
                )
            ]
        )
        source.search.return_value = search_response

        return source

    @pytest.fixture
    def mock_conceptnet_source(self):
        """Create mock ConceptNet source."""
        source = AsyncMock()
        source.__aenter__ = AsyncMock(return_value=source)
        source.__aexit__ = AsyncMock(return_value=None)

        # Mock query response
        query_response = ConceptNetQueryResponse(
            success=True,
            source=SourceType.CONCEPTNET,
            retrieved_at=datetime.now(UTC),
            edges=[
                {
                    "@id": "/e/test1",
                    "start": {"@id": "/c/en/python", "label": "python"},
                    "rel": {"@id": "/r/IsA", "label": "IsA"},
                    "end": {"@id": "/c/en/programming_language", "label": "programming language"},
                    "weight": 0.8,
                    "sources": []
                }
            ]
        )
        source.query.return_value = query_response

        return source

    @pytest.fixture
    def mock_wikidata_source(self):
        """Create mock Wikidata source."""
        source = AsyncMock()
        source.__aenter__ = AsyncMock(return_value=source)
        source.__aexit__ = AsyncMock(return_value=None)

        # Mock SPARQL response
        sparql_response = WikidataSparqlResponse(
            success=True,
            source=SourceType.WIKIDATA,
            retrieved_at=datetime.now(UTC),
            results={
                "results": {
                    "bindings": [
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q28865"},
                            "itemLabel": {"value": "Python"},
                            "itemDescription": {"value": "programming language"}
                        }
                    ]
                }
            }
        )
        source.sparql_query.return_value = sparql_response

        return source

    @pytest.fixture
    def mock_schema_org_source(self):
        """Create mock Schema.org source."""
        source = AsyncMock()
        source.__aenter__ = AsyncMock(return_value=source)
        source.__aexit__ = AsyncMock(return_value=None)

        # Mock search response
        search_response = SchemaOrgSearchResponse(
            success=True,
            source=SourceType.SCHEMA_ORG,
            retrieved_at=datetime.now(UTC),
            query="ComputerLanguage",
            total_results=1,
            results=[
                SchemaOrgSearchResult(
                    type="entity",
                    identifier="ComputerLanguage",
                    title="ComputerLanguage",
                    definition="Computer programming language",
                    relevance_score=0.9
                )
            ]
        )
        source.search.return_value = search_response

        return source

    @pytest.mark.asyncio
    async def test_dbpedia_search_returns_normalized_response(self, service, mock_dbpedia_source):
        """Test that DBpedia search returns normalized MultiSourceSearchResponse."""
        with patch.object(service, '_get_source', return_value=mock_dbpedia_source):
            request = DBpediaSearchRequest(query="python", limit=10)
            response = await service.dbpedia_search(request)

            # Verify response type and structure
            assert isinstance(response, MultiSourceSearchResponse)
            assert response.query == "python"
            assert len(response.results) == 1
            assert len(response.sources_queried) == 1
            assert response.sources_queried[0] == "dbpedia"

            # Verify node normalization
            node = response.results[0]
            assert node.id == "dbpedia:http://dbpedia.org/resource/Python"
            assert node.source == SourceType.DBPEDIA
            assert node.title == "Python (programming language)"
            assert node.definition == "High-level programming language"
            assert node.relevance_score == 1.0  # Max score normalized

    @pytest.mark.asyncio
    async def test_conceptnet_query_returns_normalized_response(self, service, mock_conceptnet_source):
        """Test that ConceptNet query returns normalized MultiSourceSearchResponse."""
        with patch.object(service, '_get_source', return_value=mock_conceptnet_source):
            request = ConceptNetQueryRequest(node="/c/en/python", limit=20)
            response = await service.conceptnet_query(request)

            # Verify response type and structure
            assert isinstance(response, MultiSourceSearchResponse)
            assert len(response.results) == 2  # start and end nodes
            assert len(response.links) == 1    # IsA relation
            assert response.sources_queried == ["conceptnet"]

            # Verify nodes
            python_node = next(n for n in response.results if "python" in n.title)
            assert python_node.id == "conceptnet:/c/en/python"
            assert python_node.source == SourceType.CONCEPTNET

            # Verify link
            isa_link = response.links[0]
            assert isa_link.predicate == "IsA"
            assert isa_link.source == SourceType.CONCEPTNET

    @pytest.mark.asyncio
    async def test_wikidata_sparql_returns_normalized_response(self, service, mock_wikidata_source):
        """Test that Wikidata SPARQL returns normalized MultiSourceSearchResponse."""
        with patch.object(service, '_get_source', return_value=mock_wikidata_source):
            request = WikidataSparqlRequest(query="SELECT ?item WHERE { ?item rdfs:label \"Python\"@en }")
            response = await service.wikidata_sparql(request)

            # Verify response type and structure
            assert isinstance(response, MultiSourceSearchResponse)
            assert len(response.results) == 1
            assert response.sources_queried == ["wikidata"]

            # Verify node normalization
            node = response.results[0]
            assert node.id == "wikidata:http://www.wikidata.org/entity/Q28865"
            assert node.source == SourceType.WIKIDATA
            assert node.title == "Python"
            assert node.definition == "programming language"

    @pytest.mark.asyncio
    async def test_schema_org_search_returns_normalized_response(self, service, mock_schema_org_source):
        """Test that Schema.org search returns normalized MultiSourceSearchResponse."""
        with patch.object(service, '_get_source', return_value=mock_schema_org_source):
            request = SchemaOrgSearchRequest(query="ComputerLanguage", limit=10)
            response = await service.schema_org_search(request)

            # Verify response type and structure
            assert isinstance(response, MultiSourceSearchResponse)
            assert response.query == "ComputerLanguage"
            assert len(response.results) == 1
            assert response.sources_queried == ["schema_org"]

            # Verify node normalization
            node = response.results[0]
            assert node.id == "schema_org:ComputerLanguage"
            assert node.source == SourceType.SCHEMA_ORG
            assert node.title == "ComputerLanguage"

    @pytest.mark.asyncio
    async def test_multi_source_search_integration(self, service):
        """Test full multi-source search integration with all sources."""
        # Mock all sources
        mock_sources = {}

        # DBpedia mock
        dbpedia_source = AsyncMock()
        dbpedia_source.__aenter__ = AsyncMock(return_value=dbpedia_source)
        dbpedia_source.__aexit__ = AsyncMock(return_value=None)
        dbpedia_source.search.return_value = DBpediaSearchResponse(
            success=True,
            source=SourceType.DBPEDIA,
            retrieved_at=datetime.now(UTC),
            query="python",
            total_results=1,
            results=[
                DBpediaSearchResult(
                    uri="http://dbpedia.org/resource/Python",
                    label="Python",
                    description="Programming language",
                    score=0.95,
                    types=["ProgrammingLanguage"]
                )
            ]
        )
        mock_sources[SourceType.DBPEDIA] = dbpedia_source

        # ConceptNet mock
        conceptnet_source = AsyncMock()
        conceptnet_source.__aenter__ = AsyncMock(return_value=conceptnet_source)
        conceptnet_source.__aexit__ = AsyncMock(return_value=None)
        conceptnet_source.query.return_value = ConceptNetQueryResponse(
            success=True,
            source=SourceType.CONCEPTNET,
            retrieved_at=datetime.now(UTC),
            edges=[
                {
                    "@id": "/e/test1",
                    "start": {"@id": "/c/en/python", "label": "python"},
                    "rel": {"@id": "/r/IsA", "label": "IsA"},
                    "end": {"@id": "/c/en/language", "label": "language"},
                    "weight": 0.8,
                    "sources": []
                }
            ]
        )
        mock_sources[SourceType.CONCEPTNET] = conceptnet_source

        # Wikidata mock
        wikidata_source = AsyncMock()
        wikidata_source.__aenter__ = AsyncMock(return_value=wikidata_source)
        wikidata_source.__aexit__ = AsyncMock(return_value=None)
        wikidata_source.sparql_query.return_value = WikidataSparqlResponse(
            success=True,
            source=SourceType.WIKIDATA,
            retrieved_at=datetime.now(UTC),
            results={
                "results": {
                    "bindings": [
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q28865"},
                            "itemLabel": {"value": "Python"},
                            "itemDescription": {"value": "programming language"}
                        }
                    ]
                }
            }
        )
        mock_sources[SourceType.WIKIDATA] = wikidata_source

        # Schema.org mock
        schema_org_source = AsyncMock()
        schema_org_source.__aenter__ = AsyncMock(return_value=schema_org_source)
        schema_org_source.__aexit__ = AsyncMock(return_value=None)
        schema_org_source.search.return_value = SchemaOrgSearchResponse(
            success=True,
            source=SourceType.SCHEMA_ORG,
            retrieved_at=datetime.now(UTC),
            query="python",
            total_results=0,
            results=[]
        )
        mock_sources[SourceType.SCHEMA_ORG] = schema_org_source

        def mock_get_source(source_type):
            return mock_sources[source_type]

        with patch.object(service, '_get_source', side_effect=mock_get_source):
            from reference.models import MultiSourceSearchRequest

            request = MultiSourceSearchRequest(query="python", limit=10)
            response = await service.search(request)

            # Verify aggregated response
            assert isinstance(response, MultiSourceSearchResponse)
            assert response.query == "python"
            assert len(response.results) >= 3  # At least one from each successful source
            assert len(response.sources_queried) == 4  # All sources queried

            # Verify we have nodes from different sources
            sources_with_results = {node.source for node in response.results}
            assert SourceType.DBPEDIA in sources_with_results
            assert SourceType.CONCEPTNET in sources_with_results
            assert SourceType.WIKIDATA in sources_with_results

            # Verify cross-reference links were discovered
            cross_ref_links = [link for link in response.links if link.predicate == "sameAs"]
            assert len(cross_ref_links) > 0, "Expected cross-reference links between similar nodes"

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, service):
        """Test error handling in the integrated service."""
        # Mock a source that raises an exception
        failing_source = AsyncMock()
        failing_source.__aenter__ = AsyncMock(return_value=failing_source)
        failing_source.__aexit__ = AsyncMock(return_value=None)
        failing_source.search.side_effect = Exception("Connection timeout")

        with patch.object(service, '_get_source', return_value=failing_source):
            request = DBpediaSearchRequest(query="test", limit=5)
            response = await service.dbpedia_search(request)

            # Should return error response
            assert isinstance(response, MultiSourceSearchResponse)
            assert response.query == "test"
            assert len(response.results) == 0
            assert "dbpedia" in response.source_errors
            assert "Connection timeout" in response.source_errors["dbpedia"]

    @pytest.mark.asyncio
    async def test_parallel_source_execution(self, service):
        """Test that multi-source search executes sources in parallel."""
        import time

        # Create sources with artificial delays
        slow_sources = {}

        for source_type in [SourceType.DBPEDIA, SourceType.CONCEPTNET, SourceType.WIKIDATA]:
            source = AsyncMock()
            source.__aenter__ = AsyncMock(return_value=source)
            source.__aexit__ = AsyncMock(return_value=None)

            # Add delay to simulate network latency
            async def slow_response(*args, **kwargs):
                await asyncio.sleep(0.1)  # 100ms delay
                return getattr(source_type, 'mock_response', MultiSourceSearchResponse(
                    query="test",
                    results=[],
                    links=[],
                    total_results=0,
                    total_links=0,
                    sources_queried=[source_type.value],
                    source_errors={},
                    offset=0,
                    limit=10,
                    search_time_ms=100.0
                ))

            # Mock appropriate methods based on source type
            if source_type == SourceType.DBPEDIA:
                source.search = slow_response
            elif source_type == SourceType.CONCEPTNET:
                source.query = slow_response
            elif source_type == SourceType.WIKIDATA:
                source.sparql_query = slow_response

            slow_sources[source_type] = source

        def mock_get_source(source_type):
            return slow_sources.get(source_type, AsyncMock())

        with patch.object(service, '_get_source', side_effect=mock_get_source):
            from reference.models import MultiSourceSearchRequest

            start_time = time.time()
            request = MultiSourceSearchRequest(
                query="test",
                sources=[SourceType.DBPEDIA, SourceType.CONCEPTNET, SourceType.WIKIDATA],
                limit=5
            )
            response = await service.search(request)
            execution_time = time.time() - start_time

            # Should complete in roughly 100ms (parallel) rather than 300ms (sequential)
            assert execution_time < 0.2, f"Expected parallel execution, but took {execution_time:.3f}s"
            assert isinstance(response, MultiSourceSearchResponse)

    @pytest.mark.asyncio
    async def test_backwards_compatibility_legacy_methods(self, service, mock_dbpedia_source):
        """Test that legacy wrapper methods still work for backwards compatibility."""
        with patch.object(service, '_get_source', return_value=mock_dbpedia_source):
            # Test legacy DBpedia search method exists and works
            assert hasattr(service, 'dbpedia_search_legacy')

            request = DBpediaSearchRequest(query="python", limit=10)
            legacy_response = await service.dbpedia_search_legacy(request)

            # Should return original format (DBpediaSearchResponse)
            assert isinstance(legacy_response, DBpediaSearchResponse)
            assert legacy_response.success is True
            assert len(legacy_response.results) == 1

    @pytest.mark.asyncio
    async def test_cross_reference_discovery_integration(self, service):
        """Test that cross-references are discovered correctly in multi-source search."""
        # Create sources that return similar entities
        dbpedia_source = AsyncMock()
        dbpedia_source.__aenter__ = AsyncMock(return_value=dbpedia_source)
        dbpedia_source.__aexit__ = AsyncMock(return_value=None)
        dbpedia_source.search.return_value = DBpediaSearchResponse(
            success=True,
            source=SourceType.DBPEDIA,
            retrieved_at=datetime.now(UTC),
            query="Python",
            total_results=1,
            results=[
                DBpediaSearchResult(
                    uri="http://dbpedia.org/resource/Python",
                    label="Python",  # Same title
                    description="Programming language",
                    score=0.95,
                    types=["ProgrammingLanguage"]
                )
            ]
        )

        wikidata_source = AsyncMock()
        wikidata_source.__aenter__ = AsyncMock(return_value=wikidata_source)
        wikidata_source.__aexit__ = AsyncMock(return_value=wikidata_source)
        wikidata_source.sparql_query.return_value = WikidataSparqlResponse(
            success=True,
            source=SourceType.WIKIDATA,
            retrieved_at=datetime.now(UTC),
            results={
                "results": {
                    "bindings": [
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q28865"},
                            "itemLabel": {"value": "Python"},  # Same title
                            "itemDescription": {"value": "programming language"}
                        }
                    ]
                }
            }
        )

        mock_sources = {
            SourceType.DBPEDIA: dbpedia_source,
            SourceType.WIKIDATA: wikidata_source
        }

        def mock_get_source(source_type):
            return mock_sources[source_type]

        with patch.object(service, '_get_source', side_effect=mock_get_source):
            from reference.models import MultiSourceSearchRequest

            request = MultiSourceSearchRequest(
                query="Python",
                sources=[SourceType.DBPEDIA, SourceType.WIKIDATA],
                limit=10
            )
            response = await service.search(request)

            # Should have cross-reference links
            cross_ref_links = [link for link in response.links if link.predicate == "sameAs"]
            assert len(cross_ref_links) > 0

            # Verify cross-reference link properties
            cross_ref = cross_ref_links[0]
            assert cross_ref.attributes["link_type"] == "cross_reference"
            assert cross_ref.attributes["confidence"] >= 0.8
            assert "dbpedia:" in cross_ref.subject or "dbpedia:" in cross_ref.object
            assert "wikidata:" in cross_ref.subject or "wikidata:" in cross_ref.object

    @pytest.mark.asyncio
    async def test_service_components_integration(self, service):
        """Test that all service components work together correctly."""
        # Verify service has all expected components
        assert hasattr(service, 'normalizer')
        assert hasattr(service, 'aggregator')
        assert hasattr(service, 'response_builder')

        # Verify components are properly initialized
        assert service.normalizer is not None
        assert service.aggregator is not None
        assert service.response_builder is not None

        # Test that components have expected methods
        assert hasattr(service.normalizer, 'normalize_dbpedia_search_response')
        assert hasattr(service.aggregator, 'deduplicate_nodes')
        assert hasattr(service.response_builder, 'build_single_source_response')
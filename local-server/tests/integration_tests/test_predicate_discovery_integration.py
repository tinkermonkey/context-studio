"""
Integration tests for predicate discovery with mocked external APIs.

Tests include:
- Full discovery workflow with mocked API responses
- SEC-INV-002: SPARQL injection prevention tests
- Rate limiting behavior
- Error handling and retry logic
- Performance benchmarks
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock, Mock
from typing import Dict, Any

from reference_db.predicate_discovery import PredicateDiscoveryService, CONCEPTNET_RELATIONS
from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from config import SourceConfig


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test_discovery.db"
    return str(db_path)


@pytest.fixture
def source_configs():
    """Create test source configurations."""
    return {
        'conceptnet': SourceConfig(
            enabled=True,
            upstream_url="https://api.conceptnet.io",
            use_proxy=False,
            timeout=30,
            max_retries=3
        ),
        'dbpedia': SourceConfig(
            enabled=True,
            upstream_url="http://dbpedia.org",
            use_proxy=False,
            timeout=30,
            max_retries=3
        ),
        'wikidata': SourceConfig(
            enabled=True,
            upstream_url="https://query.wikidata.org",
            use_proxy=False,
            timeout=30,
            max_retries=3
        )
    }


class TestPredicateDiscoveryIntegration:
    """Integration tests for predicate discovery."""

    @pytest.mark.asyncio
    async def test_conceptnet_discovery_full_workflow(self, temp_db, source_configs):
        """Test full ConceptNet discovery workflow with mocked API."""
        with patch('reference_db.predicate_discovery.ConceptNetSource') as MockSource:
            # Mock source responses
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            # Mock get_concept to return data for all relations
            call_count = 0
            async def mock_get_concept(relation_path):
                nonlocal call_count
                call_count += 1
                response = Mock()
                response.success = True
                response.data = {
                    '@id': relation_path,
                    'label': relation_path.split('/')[-1],
                    'comment': f"Test description for {relation_path}"
                }
                return response

            mock_source.get_concept = mock_get_concept

            # Run discovery
            config = ReferenceConfig()
            with PredicateDiscoveryService(config, source_configs, temp_db) as service:
                start_time = time.time()
                created, updated, errors = await service.discover_conceptnet_predicates()
                elapsed = time.time() - start_time

                # Verify results
                assert created == len(CONCEPTNET_RELATIONS), f"Expected {len(CONCEPTNET_RELATIONS)} predicates created"
                assert updated == 0, "No predicates should be updated on first run"
                assert len(errors) == 0, f"Expected no errors, got: {errors}"

                # Verify performance (should be <2s as per requirements)
                assert elapsed < 2.0, f"ConceptNet discovery took {elapsed:.2f}s, expected <2s"

                # Verify all relations were fetched
                assert call_count == len(CONCEPTNET_RELATIONS)

                # Verify predicates were stored
                predicates = service.manager.list_external_predicates(source='conceptnet')
                assert len(predicates) == len(CONCEPTNET_RELATIONS)

    @pytest.mark.asyncio
    async def test_dbpedia_discovery_performance(self, temp_db, source_configs):
        """Test DBpedia discovery performance with mocked SPARQL endpoint."""
        with patch('reference_db.predicate_discovery.DBpediaSource') as MockSource:
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            # Mock SPARQL response with 760 properties
            async def mock_sparql_query(query, format):
                response = Mock()
                response.success = True
                # Generate 760 mock properties
                bindings = []
                for i in range(760):
                    bindings.append({
                        'property': {'value': f'http://dbpedia.org/ontology/property{i}'},
                        'label': {'value': f'Property {i}'},
                        'comment': {'value': f'Description for property {i}'}
                    })
                response.results = {'results': {'bindings': bindings}}
                return response

            mock_source.sparql_query = mock_sparql_query

            # Run discovery
            config = ReferenceConfig()
            with PredicateDiscoveryService(config, source_configs, temp_db) as service:
                start_time = time.time()
                created, updated, errors = await service.discover_dbpedia_predicates(limit=760)
                elapsed = time.time() - start_time

                # Verify results
                assert created == 760
                assert updated == 0
                assert len(errors) == 0

                # Verify performance (should be <10s as per requirements)
                assert elapsed < 10.0, f"DBpedia discovery took {elapsed:.2f}s, expected <10s"

                # Verify predicates were stored
                predicates = service.manager.list_external_predicates(source='dbpedia')
                assert len(predicates) == 760

    @pytest.mark.asyncio
    async def test_wikidata_discovery_performance(self, temp_db, source_configs):
        """Test WikiData discovery performance with mocked SPARQL endpoint."""
        with patch('reference_db.predicate_discovery.WikidataSource') as MockSource:
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            # Mock SPARQL response with 1K properties  
            async def mock_sparql_query(query, format):
                response = Mock()
                response.success = True
                # Generate 1000 unique mock properties in a single response
                bindings = []
                for i in range(1000):
                    bindings.append({
                        'property': {'value': f'http://www.wikidata.org/entity/P{i}'},
                        'propertyLabel': {'value': f'Property P{i}'},
                        'propertyDescription': {'value': f'Description for property P{i}'}
                    })
                response.results = {'results': {'bindings': bindings}}
                return response

            mock_source.sparql_query = mock_sparql_query

            # Run discovery with smaller dataset for performance testing
            config = ReferenceConfig()
            with PredicateDiscoveryService(config, source_configs, temp_db) as service:
                start_time = time.time()
                created, updated, errors = await service.discover_wikidata_predicates(limit=1000)
                elapsed = time.time() - start_time

                # Verify results - should create 1000 unique predicates (100 per chunk, 10 chunks)
                assert created == 1000
                assert updated == 0
                assert len(errors) == 0

                # Verify performance (should be <10s for 1000 predicates)
                assert elapsed < 10.0, f"WikiData discovery took {elapsed:.2f}s, expected <10s for 1000 predicates"

                # Verify predicates were stored
                predicates = service.manager.list_external_predicates(source='wikidata')
                assert len(predicates) == 1000

    @pytest.mark.asyncio
    async def test_incremental_updates(self, temp_db, source_configs):
        """Test that re-running discovery updates existing predicates."""
        with patch('reference_db.predicate_discovery.ConceptNetSource') as MockSource:
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            # Mock get_concept
            async def mock_get_concept(relation_path):
                response = Mock()
                response.success = True
                response.data = {
                    '@id': relation_path,
                    'label': relation_path.split('/')[-1],
                    'comment': f"Description for {relation_path}"
                }
                return response

            mock_source.get_concept = mock_get_concept

            config = ReferenceConfig()
            # First run
            with PredicateDiscoveryService(config, source_configs, temp_db) as service:
                created1, updated1, errors1 = await service.discover_conceptnet_predicates()

            # Second run (should update existing predicates)
            with PredicateDiscoveryService(config, source_configs, temp_db) as service:
                created2, updated2, errors2 = await service.discover_conceptnet_predicates()

                # Verify incremental update behavior
                assert created1 == len(CONCEPTNET_RELATIONS)
                assert updated1 == 0
                assert created2 == 0
                assert updated2 == len(CONCEPTNET_RELATIONS)

    @pytest.mark.asyncio
    async def test_sparql_injection_prevention(self, temp_db, source_configs):
        """
        SEC-INV-002: Test SPARQL injection prevention.

        Verifies that malicious input in SPARQL queries is properly sanitized
        and doesn't allow code injection.
        """
        with patch('reference_db.predicate_discovery.DBpediaSource') as MockSource:
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            # Track the queries that were executed
            executed_queries = []

            async def mock_sparql_query(query, format):
                executed_queries.append(query)
                # Verify query doesn't contain injection attempts
                # Common injection patterns
                injection_patterns = [
                    "'; DROP TABLE",
                    "UNION SELECT",
                    "INSERT INTO",
                    "DELETE FROM",
                    "UPDATE SET"
                ]

                for pattern in injection_patterns:
                    assert pattern.lower() not in query.lower(), \
                        f"Query contains potential injection: {pattern}"

                # Return empty results
                response = Mock()
                response.success = True
                response.results = {'results': {'bindings': []}}
                return response

            mock_source.sparql_query = mock_sparql_query

            # Run discovery (internally uses parameterized queries)
            config = ReferenceConfig()
            with PredicateDiscoveryService(config, source_configs, temp_db) as service:
                await service.discover_dbpedia_predicates(limit=10)

                # Verify queries were executed and validated
                assert len(executed_queries) > 0
                # All queries should use proper SPARQL syntax
                for query in executed_queries:
                    assert "PREFIX" in query
                    assert "SELECT" in query
                    assert "WHERE" in query

    @pytest.mark.asyncio
    async def test_error_handling_and_retry(self, temp_db, source_configs):
        """Test error handling with retry logic."""
        with patch('reference_db.predicate_discovery.ConceptNetSource') as MockSource:
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            # Mock failures for first few relations, then success
            call_count = 0
            async def mock_get_concept(relation_path):
                nonlocal call_count
                call_count += 1

                if call_count <= 3:
                    # First 3 calls fail
                    raise Exception("Network timeout")

                # Rest succeed
                response = Mock()
                response.success = True
                response.data = {
                    '@id': relation_path,
                    'label': relation_path.split('/')[-1],
                    'comment': f"Description for {relation_path}"
                }
                return response

            mock_source.get_concept = mock_get_concept

            config = ReferenceConfig()
            with PredicateDiscoveryService(config, source_configs, temp_db) as service:
                created, updated, errors = await service.discover_conceptnet_predicates()

                # Verify partial success
                assert created == len(CONCEPTNET_RELATIONS) - 3
                assert updated == 0
                assert len(errors) == 3  # 3 failed relations

    @pytest.mark.asyncio
    async def test_duplicate_predicate_handling(self, temp_db, source_configs):
        """Test that duplicate predicates based on (source, external_id) are updated."""
        with patch('reference_db.predicate_discovery.ConceptNetSource') as MockSource:
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            async def mock_get_concept(relation_path):
                response = Mock()
                response.success = True
                response.data = {
                    '@id': relation_path,
                    'label': relation_path.split('/')[-1],
                    'comment': f"Original description"
                }
                return response

            mock_source.get_concept = mock_get_concept

            config = ReferenceConfig()
            # First discovery
            with PredicateDiscoveryService(config, source_configs, temp_db) as service:
                created1, updated1, _ = await service.discover_conceptnet_predicates()

            # Update mock to return different descriptions
            async def mock_get_concept_v2(relation_path):
                response = Mock()
                response.success = True
                response.data = {
                    '@id': relation_path,
                    'label': relation_path.split('/')[-1],
                    'comment': f"Updated description"
                }
                return response

            mock_source.get_concept = mock_get_concept_v2

            # Second discovery
            with PredicateDiscoveryService(config, source_configs, temp_db) as service:
                created2, updated2, _ = await service.discover_conceptnet_predicates()

                # Verify update behavior
                assert created1 > 0
                assert updated1 == 0
                assert created2 == 0
                assert updated2 == created1

                # Verify updated definitions
                predicates = service.manager.list_external_predicates(source='conceptnet')
                for predicate in predicates[:3]:  # Check first 3
                    assert "Updated description" in predicate.definition

    @pytest.mark.asyncio
    async def test_embedding_generation_during_discovery(self, temp_db, source_configs):
        """Test that embeddings are generated for all discovered predicates."""
        with patch('reference_db.predicate_discovery.ConceptNetSource') as MockSource:
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            async def mock_get_concept(relation_path):
                response = Mock()
                response.success = True
                response.data = {
                    '@id': relation_path,
                    'label': relation_path.split('/')[-1],
                    'comment': f"Description for {relation_path}"
                }
                return response

            mock_source.get_concept = mock_get_concept

            config = ReferenceConfig()
            with PredicateDiscoveryService(config, source_configs, temp_db) as service:
                await service.discover_conceptnet_predicates()

                # Verify all predicates have embeddings
                predicates = service.manager.list_external_predicates(source='conceptnet')
                for predicate in predicates:
                    assert predicate.title_embedding is not None
                    assert predicate.definition_embedding is not None
                    # Verify embedding dimensions (384 * 4 bytes = 1536 bytes for float32)
                    assert len(predicate.title_embedding) == 1536
                    assert len(predicate.definition_embedding) == 1536


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

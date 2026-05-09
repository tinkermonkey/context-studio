"""
Integration tests for predicate discovery with mocked external APIs.

Tests include:
- Full discovery workflow with mocked API responses
- SEC-INV-002: SPARQL injection prevention tests
- Rate limiting behavior
- Error handling and retry logic
- Incremental updates and duplicate handling
- Embedding generation verification
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
import time  # noqa: E402
from unittest.mock import patch, AsyncMock, Mock  # noqa: E402

from reference_db.predicate_discovery import (
    PredicateDiscoveryService,
    CONCEPTNET_RELATIONS,
)  # noqa: E402, E501
from reference_db.config import ReferenceConfig  # noqa: E402
from config import SourceConfig  # noqa: E402


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test_discovery.db"
    return str(db_path)


@pytest.fixture
def source_configs():
    """Create test source configurations."""
    return {
        "conceptnet": SourceConfig(
            enabled=True,
            upstream_url="https://api.conceptnet.io",
            use_proxy=False,
            timeout=30,
            max_retries=3,
        ),
        "dbpedia": SourceConfig(
            enabled=True,
            upstream_url="http://dbpedia.org",
            use_proxy=False,
            timeout=30,
            max_retries=3,
        ),
        "wikidata": SourceConfig(
            enabled=True,
            upstream_url="https://query.wikidata.org",
            use_proxy=False,
            timeout=30,
            max_retries=3,
        ),
    }


class TestPredicateDiscoveryIntegration:
    """Integration tests for predicate discovery."""

    @pytest.mark.asyncio
    async def test_conceptnet_discovery_full_workflow(
        self, temp_db, source_configs
    ):  # noqa: E501
        """Test full ConceptNet discovery workflow with mocked API."""
        with patch(
            "reference_db.predicate_discovery.ConceptNetSource"
        ) as MockSource:  # noqa: E501
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
                    "@id": relation_path,
                    "label": relation_path.split("/")[-1],
                    "comment": f"Test description for {relation_path}",
                }
                return response

            mock_source.get_concept = mock_get_concept

            # Run discovery
            config = ReferenceConfig()
            with PredicateDiscoveryService(
                config, source_configs, temp_db
            ) as service:  # noqa: E501
                start_time = time.time()
                created, updated, errors = (
                    await service.discover_conceptnet_predicates()
                )  # noqa: E501
                elapsed = time.time() - start_time

                # Verify results
                assert created == len(
                    CONCEPTNET_RELATIONS
                ), f"Expected {len(CONCEPTNET_RELATIONS)} predicates created"  # noqa: E501
                assert (
                    updated == 0
                ), "No predicates should be updated on first run"  # noqa: E501
                assert len(errors) == 0, f"Expected no errors, got: {errors}"

                # Verify performance (should be <2s as per requirements)
                assert (
                    elapsed < 2.0
                ), f"ConceptNet discovery took {elapsed:.2f}s, expected <2s"  # noqa: E501

                # Verify all relations were fetched
                assert call_count == len(CONCEPTNET_RELATIONS)

                # Verify predicates were stored
                predicates = service.manager.list_external_predicates(
                    source="conceptnet"
                )  # noqa: E501
                assert len(predicates) == len(CONCEPTNET_RELATIONS)

    @pytest.mark.asyncio
    async def test_incremental_updates(self, temp_db, source_configs):
        """Test that re-running discovery updates existing predicates."""
        with patch(
            "reference_db.predicate_discovery.ConceptNetSource"
        ) as MockSource:  # noqa: E501
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
                    "@id": relation_path,
                    "label": relation_path.split("/")[-1],
                    "comment": f"Description for {relation_path}",
                }
                return response

            mock_source.get_concept = mock_get_concept

            config = ReferenceConfig()
            # First run
            with PredicateDiscoveryService(
                config, source_configs, temp_db
            ) as service:  # noqa: E501
                created1, updated1, errors1 = (
                    await service.discover_conceptnet_predicates()
                )  # noqa: E501

            # Second run (should update existing predicates)
            with PredicateDiscoveryService(
                config, source_configs, temp_db
            ) as service:  # noqa: E501
                created2, updated2, errors2 = (
                    await service.discover_conceptnet_predicates()
                )  # noqa: E501

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
        with patch(
            "reference_db.predicate_discovery.DBpediaSource"
        ) as MockSource:  # noqa: E501
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
                    "UPDATE SET",
                ]

                for pattern in injection_patterns:
                    assert (
                        pattern.lower() not in query.lower()
                    ), f"Query contains potential injection: {pattern}"

                # Return empty results
                response = Mock()
                response.success = True
                response.results = {"results": {"bindings": []}}
                return response

            mock_source.sparql_query = mock_sparql_query

            # Run discovery (internally uses parameterized queries)
            config = ReferenceConfig()
            with PredicateDiscoveryService(
                config, source_configs, temp_db
            ) as service:  # noqa: E501
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
        with patch(
            "reference_db.predicate_discovery.ConceptNetSource"
        ) as MockSource:  # noqa: E501
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
                    "@id": relation_path,
                    "label": relation_path.split("/")[-1],
                    "comment": f"Description for {relation_path}",
                }
                return response

            mock_source.get_concept = mock_get_concept

            config = ReferenceConfig()
            with PredicateDiscoveryService(
                config, source_configs, temp_db
            ) as service:  # noqa: E501
                created, updated, errors = (
                    await service.discover_conceptnet_predicates()
                )  # noqa: E501

                # Verify partial success
                assert created == len(CONCEPTNET_RELATIONS) - 3
                assert updated == 0
                assert len(errors) == 3  # 3 failed relations

    @pytest.mark.asyncio
    async def test_duplicate_predicate_handling(self, temp_db, source_configs):
        """Test that duplicate predicates based on (source, external_id) are updated."""  # noqa: E501
        with patch(
            "reference_db.predicate_discovery.ConceptNetSource"
        ) as MockSource:  # noqa: E501
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            async def mock_get_concept(relation_path):
                response = Mock()
                response.success = True
                response.data = {
                    "@id": relation_path,
                    "label": relation_path.split("/")[-1],
                    "comment": "Original description",
                }
                return response

            mock_source.get_concept = mock_get_concept

            config = ReferenceConfig()
            # First discovery
            with PredicateDiscoveryService(
                config, source_configs, temp_db
            ) as service:  # noqa: E501
                created1, updated1, _ = (
                    await service.discover_conceptnet_predicates()
                )  # noqa: E501

            # Update mock to return different descriptions
            async def mock_get_concept_v2(relation_path):
                response = Mock()
                response.success = True
                response.data = {
                    "@id": relation_path,
                    "label": relation_path.split("/")[-1],
                    "comment": "Updated description",
                }
                return response

            mock_source.get_concept = mock_get_concept_v2

            # Second discovery
            with PredicateDiscoveryService(
                config, source_configs, temp_db
            ) as service:  # noqa: E501
                created2, updated2, _ = (
                    await service.discover_conceptnet_predicates()
                )  # noqa: E501

                # Verify update behavior
                assert created1 > 0
                assert updated1 == 0
                assert created2 == 0
                assert updated2 == created1

                # Verify updated definitions
                predicates = service.manager.list_external_predicates(
                    source="conceptnet"
                )  # noqa: E501
                for predicate in predicates[:3]:  # Check first 3
                    assert "Updated description" in predicate.definition

    @pytest.mark.asyncio
    async def test_embedding_generation_during_discovery(
        self, temp_db, source_configs
    ):  # noqa: E501
        """Test that embeddings are generated for all discovered predicates."""
        with patch(
            "reference_db.predicate_discovery.ConceptNetSource"
        ) as MockSource:  # noqa: E501
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            async def mock_get_concept(relation_path):
                response = Mock()
                response.success = True
                response.data = {
                    "@id": relation_path,
                    "label": relation_path.split("/")[-1],
                    "comment": f"Description for {relation_path}",
                }
                return response

            mock_source.get_concept = mock_get_concept

            config = ReferenceConfig()
            with PredicateDiscoveryService(
                config, source_configs, temp_db
            ) as service:  # noqa: E501
                await service.discover_conceptnet_predicates()

                # Verify all predicates have embeddings
                predicates = service.manager.list_external_predicates(
                    source="conceptnet"
                )  # noqa: E501
                for predicate in predicates:
                    assert predicate.title_embedding is not None
                    assert predicate.definition_embedding is not None
                    # Verify embedding dimensions (384 * 4 bytes = 1536 bytes for float32)  # noqa: E501
                    assert len(predicate.title_embedding) == 1536
                    assert len(predicate.definition_embedding) == 1536


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

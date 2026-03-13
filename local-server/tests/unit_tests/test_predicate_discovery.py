"""
Unit tests for predicate discovery service.

Tests the PredicateDiscoveryService class for:
- ConceptNet predicate discovery
- DBpedia predicate discovery
- WikiData predicate discovery
- Embedding generation with adaptive batch sizing
- Upsert functionality (update vs insert)
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from unittest.mock import Mock, AsyncMock, patch  # noqa: E402
from datetime import date  # noqa: E402

from reference_db.predicate_discovery import (
    PredicateDiscoveryService,
    CONCEPTNET_RELATIONS,
)  # noqa: E402, E501
from reference_db.models import ExternalPredicate  # noqa: E402
from reference_db.config import ReferenceConfig  # noqa: E402
from config import SourceConfig  # noqa: E402


@pytest.fixture
def mock_source_configs():
    """Create mock source configurations."""
    conceptnet_config = SourceConfig(
        enabled=True,
        upstream_url="https://api.conceptnet.io",
        use_proxy=False,
        timeout=30,
        max_retries=3,
    )

    dbpedia_config = SourceConfig(
        enabled=True,
        upstream_url="http://dbpedia.org",
        use_proxy=False,
        timeout=30,
        max_retries=3,
    )

    wikidata_config = SourceConfig(
        enabled=True,
        upstream_url="https://query.wikidata.org",
        use_proxy=False,
        timeout=30,
        max_retries=3,
    )

    return {
        "conceptnet": conceptnet_config,
        "dbpedia": dbpedia_config,
        "wikidata": wikidata_config,
    }


@pytest.fixture
def mock_ref_config(tmp_path):
    """Create mock reference configuration."""
    tmp_path / "test_reference.db"
    config = ReferenceConfig()
    return config


@pytest.fixture
def mock_manager():
    """Create mock reference manager."""
    manager = Mock()
    manager.session = Mock()
    manager.session.commit = Mock()
    manager.get_external_predicate_by_source = Mock(return_value=None)
    manager.add_external_predicate = Mock()
    return manager


class TestPredicateDiscoveryService:
    """Tests for PredicateDiscoveryService."""

    def test_calculate_batch_size_high_memory(
        self, mock_ref_config, mock_source_configs
    ):
        """Test batch size calculation with high available memory."""
        with patch(
            "reference_db.predicate_discovery.psutil.virtual_memory"
        ) as mock_mem:
            # Mock 10GB available memory
            mock_mem.return_value = Mock(available=10 * 1024**3)

            service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
            batch_size = service._calculate_batch_size()

            assert batch_size == 128  # max_size

    def test_calculate_batch_size_medium_memory(
        self, mock_ref_config, mock_source_configs
    ):
        """Test batch size calculation with medium available memory."""
        with patch(
            "reference_db.predicate_discovery.psutil.virtual_memory"
        ) as mock_mem:
            # Mock 6GB available memory
            mock_mem.return_value = Mock(available=6 * 1024**3)

            service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
            batch_size = service._calculate_batch_size()

            assert batch_size == 64

    def test_calculate_batch_size_low_memory(
        self, mock_ref_config, mock_source_configs
    ):
        """Test batch size calculation with low available memory."""
        with patch(
            "reference_db.predicate_discovery.psutil.virtual_memory"
        ) as mock_mem:
            # Mock 1GB available memory
            mock_mem.return_value = Mock(available=1 * 1024**3)

            service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
            batch_size = service._calculate_batch_size()

            assert batch_size == 8  # min_size

    def test_calculate_batch_size_error_handling(
        self, mock_ref_config, mock_source_configs
    ):
        """Test batch size calculation handles errors gracefully."""
        with patch(
            "reference_db.predicate_discovery.psutil.virtual_memory",
            side_effect=Exception("Memory error"),
        ):
            service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
            batch_size = service._calculate_batch_size()

            assert batch_size == 8  # Falls back to min_size

    def test_generate_embeddings_batch(self, mock_ref_config, mock_source_configs):
        """Test embedding generation for a batch of texts."""
        with patch("reference_db.predicate_discovery.get_model") as mock_get_model:
            mock_model = Mock()
            import numpy as np

            # Return different batch sizes based on input

            def mock_encode(batch):
                return [
                    np.random.rand(768).astype(np.float32) for _ in range(len(batch))
                ]

            mock_model.encode.side_effect = mock_encode
            mock_get_model.return_value = mock_model

            service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
            texts = ["text1", "text2", "text3"]
            embeddings = service._generate_embeddings_batch(texts, batch_size=2)

            assert len(embeddings) == 3
            assert all(isinstance(emb, bytes) for emb in embeddings)
            # Verify batch processing was used
            assert mock_model.encode.call_count == 2  # 2 batches: [2, 1]

    def test_upsert_predicate_insert(
        self, mock_ref_config, mock_source_configs, mock_manager
    ):
        """Test upserting a new predicate (insert)."""
        with patch("reference_db.predicate_discovery.generate_embedding") as mock_embed:
            mock_embed.return_value = b"\x00" * 3072  # 768 dimensions * 4 bytes

            service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
            service.manager = mock_manager

            # Mock: predicate doesn't exist
            mock_manager.get_external_predicate_by_source.return_value = None

            # Mock add_external_predicate
            new_predicate = ExternalPredicate(
                id="test-id",
                title="Test Predicate",
                definition="Test definition",
                source="test_source",
                external_id="test_ext_id",
                attributes=None,
                title_embedding=b"\x00" * 3072,
                definition_embedding=b"\x00" * 3072,
                created_at=date.today().isoformat(),
                updated_at=date.today().isoformat(),
            )
            mock_manager.add_external_predicate.return_value = new_predicate

            result = service._upsert_predicate(
                title="Test Predicate",
                definition="Test definition",
                source="test_source",
                external_id="test_ext_id",
            )

            assert result.title == "Test Predicate"
            mock_manager.add_external_predicate.assert_called_once()

    def test_upsert_predicate_update(
        self, mock_ref_config, mock_source_configs, mock_manager
    ):
        """Test upserting an existing predicate (update)."""
        with patch("reference_db.predicate_discovery.generate_embedding") as mock_embed:
            mock_embed.return_value = b"\x00" * 3072

            service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
            service.manager = mock_manager

            # Mock: predicate exists
            existing_predicate = Mock()
            existing_predicate.id = "existing-id"
            existing_predicate.title = "Old Title"
            existing_predicate.definition = "Old definition"
            mock_manager.get_external_predicate_by_source.return_value = (
                existing_predicate
            )

            service._upsert_predicate(
                title="Updated Title",
                definition="Updated definition",
                source="test_source",
                external_id="test_ext_id",
            )

            # Verify update
            assert existing_predicate.title == "Updated Title"
            assert existing_predicate.definition == "Updated definition"
            mock_manager.session.commit.assert_called_once()
            mock_manager.add_external_predicate.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_conceptnet_predicates_success(
        self, mock_ref_config, mock_source_configs, mock_manager
    ):
        """Test successful ConceptNet predicate discovery."""
        with patch("reference_db.predicate_discovery.ConceptNetSource") as MockSource:
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            # Mock successful responses for each relation
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

            service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
            service.manager = mock_manager
            mock_manager.add_external_predicate.return_value = Mock()

            # Run discovery
            created, updated, errors = await service.discover_conceptnet_predicates()

            # Verify results
            assert created == len(CONCEPTNET_RELATIONS)
            assert updated == 0
            assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_discover_conceptnet_predicates_disabled(
        self, mock_ref_config, mock_source_configs
    ):
        """Test ConceptNet discovery when source is disabled."""
        # Disable ConceptNet
        mock_source_configs["conceptnet"].enabled = False

        service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)

        created, updated, errors = await service.discover_conceptnet_predicates()

        assert created == 0
        assert updated == 0
        assert len(errors) == 1
        assert "not enabled" in errors[0]

    @pytest.mark.asyncio
    async def test_discover_dbpedia_predicates_success(
        self, mock_ref_config, mock_source_configs, mock_manager
    ):
        """Test successful DBpedia predicate discovery."""
        with patch("reference_db.predicate_discovery.DBpediaSource") as MockSource:
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            # Mock SPARQL response
            async def mock_sparql_query(query, format):
                response = Mock()
                response.success = True
                response.results = {
                    "results": {
                        "bindings": [
                            {
                                "property": {
                                    "value": "http://dbpedia.org/ontology/birthPlace"
                                },
                                "label": {"value": "birth place"},
                                "comment": {
                                    "value": "The place where a person was born"
                                },
                            },
                            {
                                "property": {
                                    "value": "http://dbpedia.org/ontology/spouse"
                                },
                                "label": {"value": "spouse"},
                                "comment": {
                                    "value": "The person to whom someone is married"
                                },
                            },
                        ]
                    }
                }
                return response

            mock_source.sparql_query = mock_sparql_query

            service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
            service.manager = mock_manager
            mock_manager.add_external_predicate.return_value = Mock()

            # Run discovery
            created, updated, errors = await service.discover_dbpedia_predicates(
                limit=2
            )

            # Verify results
            assert created == 2
            assert updated == 0
            assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_discover_wikidata_predicates_success(
        self, mock_ref_config, mock_source_configs, mock_manager
    ):
        """Test successful WikiData predicate discovery."""
        with patch("reference_db.predicate_discovery.WikidataSource") as MockSource:
            # Mock source
            mock_source = AsyncMock()
            mock_source.__aenter__.return_value = mock_source
            mock_source.__aexit__.return_value = None
            MockSource.return_value = mock_source

            # Mock SPARQL response
            async def mock_sparql_query(query, format):
                response = Mock()
                response.success = True
                response.results = {
                    "results": {
                        "bindings": [
                            {
                                "property": {
                                    "value": "http://www.wikidata.org/entity/P31"
                                },
                                "propertyLabel": {"value": "instance of"},
                                "propertyDescription": {
                                    "value": "that class of which this subject is a particular example and member"
                                },
                            },
                            {
                                "property": {
                                    "value": "http://www.wikidata.org/entity/P279"
                                },
                                "propertyLabel": {"value": "subclass of"},
                                "propertyDescription": {
                                    "value": "next higher class or type"
                                },
                            },
                        ]
                    }
                }
                return response

            mock_source.sparql_query = mock_sparql_query

            service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
            service.manager = mock_manager
            mock_manager.add_external_predicate.return_value = Mock()

            # Run discovery
            created, updated, errors = await service.discover_wikidata_predicates(
                limit=2
            )

            # Verify results
            assert created == 2
            assert updated == 0
            assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_discover_all_predicates(
        self, mock_ref_config, mock_source_configs, mock_manager
    ):
        """Test discovering predicates from all sources."""
        service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
        service.manager = mock_manager

        # Mock individual discovery methods
        service.discover_conceptnet_predicates = AsyncMock(return_value=(40, 0, []))
        service.discover_dbpedia_predicates = AsyncMock(return_value=(760, 0, []))
        service.discover_wikidata_predicates = AsyncMock(return_value=(10000, 0, []))

        # Run discovery for all sources
        results = await service.discover_all_predicates()

        # Verify all sources were called
        assert "conceptnet" in results
        assert "dbpedia" in results
        assert "wikidata" in results

        assert results["conceptnet"] == (40, 0, [])
        assert results["dbpedia"] == (760, 0, [])
        assert results["wikidata"] == (10000, 0, [])

    @pytest.mark.asyncio
    async def test_discover_all_predicates_partial(
        self, mock_ref_config, mock_source_configs, mock_manager
    ):
        """Test discovering predicates from selected sources."""
        service = PredicateDiscoveryService(mock_ref_config, mock_source_configs)
        service.manager = mock_manager

        # Mock individual discovery methods
        service.discover_conceptnet_predicates = AsyncMock(return_value=(40, 0, []))
        service.discover_dbpedia_predicates = AsyncMock(return_value=(760, 0, []))
        service.discover_wikidata_predicates = AsyncMock(return_value=(10000, 0, []))

        # Run discovery for only ConceptNet and DBpedia
        results = await service.discover_all_predicates(
            sources=["conceptnet", "dbpedia"]
        )

        # Verify only specified sources were called
        assert "conceptnet" in results
        assert "dbpedia" in results
        assert "wikidata" not in results

        service.discover_conceptnet_predicates.assert_called_once()
        service.discover_dbpedia_predicates.assert_called_once()
        service.discover_wikidata_predicates.assert_not_called()

    def test_context_manager(self, mock_ref_config, mock_source_configs):
        """Test PredicateDiscoveryService context manager."""
        with patch("reference_db.predicate_discovery.ReferenceManager") as MockManager:
            mock_manager = Mock()
            mock_manager.close = Mock()
            MockManager.return_value = mock_manager

            with PredicateDiscoveryService(
                mock_ref_config, mock_source_configs
            ) as service:
                assert service.manager is not None

            # Verify cleanup
            mock_manager.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

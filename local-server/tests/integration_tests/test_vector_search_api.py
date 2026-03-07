"""
Integration tests for vector search and link retrieval API endpoints.

Tests the FastAPI endpoints for:
- /api/reference/ref-db/search (vector similarity search)
- /api/reference/ref-db/nodes/{node_id} (node retrieval)
- /api/reference/ref-db/nodes/{node_id}/links (link retrieval)
"""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
import numpy as np

from reference_db.models import ReferenceLink
from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager


@pytest.fixture(scope="module")
def test_database():
    """Create a test database with sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    config = ReferenceConfig()
    manager = ReferenceManager(config, db_path=db_path)

    # Create embeddings helper
    def create_embedding(value: float) -> bytes:
        vec = np.full(384, value, dtype=np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    # Add test nodes
    node1 = manager.add_reference_node(
        title="Person",
        definition="A human being",
        source="schema.org",
        external_id="Person",
        title_embedding=create_embedding(0.5),
        definition_embedding=create_embedding(0.5),
        embedding_dims=384
    )

    node2 = manager.add_reference_node(
        title="Organization",
        definition="An organized group of people",
        source="schema.org",
        external_id="Organization",
        title_embedding=create_embedding(0.6),
        definition_embedding=create_embedding(0.6),
        embedding_dims=384
    )

    node3 = manager.add_reference_node(
        title="Thing",
        definition="The most generic type",
        source="schema.org",
        external_id="Thing",
        title_embedding=create_embedding(0.1),
        definition_embedding=create_embedding(0.1),
        embedding_dims=384
    )

    # Rollback any pending transactions before adding links
    # (workaround for SQLAlchemy autobegin + explicit begin() conflict)
    if manager.session.in_transaction():
        manager.session.rollback()

    # Add test links using direct session operations
    # (workaround for transaction conflict issue)
    from uuid import uuid4
    from datetime import date

    link1 = ReferenceLink(
        id=str(uuid4()),
        subject_node=node1.id,
        predicate="subClassOf",
        object_node=node3.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )
    link2 = ReferenceLink(
        id=str(uuid4()),
        subject_node=node2.id,
        predicate="subClassOf",
        object_node=node3.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )
    link3 = ReferenceLink(
        id=str(uuid4()),
        subject_node=node1.id,
        predicate="relatedTo",
        object_node=node2.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    manager.session.add_all([link1, link2, link3])
    manager.session.commit()

    # Store IDs as strings before closing session (to avoid detached instance errors)  # noqa: E501
    node_ids = (node1.id, node2.id, node3.id)
    link_ids = (link1.id, link2.id, link3.id)

    manager.close()

    yield db_path, node_ids, link_ids, create_embedding

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestVectorSearchAPI:
    """Test suite for vector search API endpoint."""

    def test_search_endpoint_basic(self, client, test_database):
        """Test basic vector search API endpoint."""
        db_path, nodes, links, create_embedding = test_database

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            with patch('embeddings.generate_embeddings.generate_embedding') as mock_embed:  # noqa: E501
                mock_embed.return_value = create_embedding(0.5)

                response = client.get(
                    "/api/reference/ref-db/search",
                    params={
                        "query": "person",
                        "limit": 10,
                        "threshold": 0.0
                    }
                )

                assert response.status_code == 200
                data = response.json()

                assert "query" in data
                assert data["query"] == "person"
                assert "total_results" in data
                assert "results" in data
                assert isinstance(data["results"], list)

    def test_search_endpoint_with_source_filter(self, client, test_database):
        """Test vector search with source filtering."""
        db_path, nodes, links, create_embedding = test_database

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            with patch('embeddings.generate_embeddings.generate_embedding') as mock_embed:  # noqa: E501
                mock_embed.return_value = create_embedding(0.5)

                response = client.get(
                    "/api/reference/ref-db/search",
                    params={
                        "query": "person",
                        "source": "schema.org",
                        "limit": 10,
                        "threshold": 0.0
                    }
                )

                assert response.status_code == 200
                data = response.json()

                # All results should be from schema.org
                for result in data["results"]:
                    assert result["source"] == "schema.org"

    def test_search_endpoint_threshold_validation(self, client):
        """Test that search endpoint validates threshold parameter."""
        # Test threshold too high
        response = client.get(
            "/api/reference/ref-db/search",
            params={
                "query": "test",
                "threshold": 1.5
            }
        )
        assert response.status_code == 422  # Pydantic validation error
        assert "detail" in response.json()

        # Test threshold too low
        response = client.get(
            "/api/reference/ref-db/search",
            params={
                "query": "test",
                "threshold": -1.5
            }
        )
        assert response.status_code == 422  # Pydantic validation error
        assert "detail" in response.json()

    def test_search_endpoint_limit_validation(self, client):
        """Test that search endpoint validates limit parameter."""
        # Test limit too high
        response = client.get(
            "/api/reference/ref-db/search",
            params={
                "query": "test",
                "limit": 10001
            }
        )
        assert response.status_code == 422  # Pydantic validation error
        assert "detail" in response.json()

        # Test negative limit
        response = client.get(
            "/api/reference/ref-db/search",
            params={
                "query": "test",
                "limit": -1
            }
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_search_endpoint_empty_query(self, client):
        """Test that search endpoint rejects empty query."""
        response = client.get(
            "/api/reference/ref-db/search",
            params={
                "query": "   ",
                "limit": 10
            }
        )
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]

    def test_search_endpoint_includes_similarity_scores(self, client, test_database):  # noqa: E501
        """Test that search results include similarity scores."""
        db_path, nodes, links, create_embedding = test_database

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            with patch('embeddings.generate_embeddings.generate_embedding') as mock_embed:  # noqa: E501
                mock_embed.return_value = create_embedding(0.5)

                response = client.get(
                    "/api/reference/ref-db/search",
                    params={
                        "query": "person",
                        "limit": 10,
                        "threshold": 0.0
                    }
                )

                assert response.status_code == 200
                data = response.json()

                # Verify similarity scores are included
                for result in data["results"]:
                    assert "similarity_score" in result
                    assert isinstance(result["similarity_score"], (int, float))
                    assert -1.0 <= result["similarity_score"] <= 1.0

    def test_search_endpoint_fails_fast_on_error(self, client):
        """Test that search endpoint returns 500 on vector search errors."""
        # Create a custom context manager that raises an error
        from contextlib import contextmanager

        @contextmanager
        def test_reference_manager_context_error(config):
            mock_manager = MagicMock()
            mock_manager.search_by_similarity.side_effect = RuntimeError("Vector search failed")  # noqa: E501
            yield mock_manager

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context_error):  # noqa: E501
            response = client.get(
                "/api/reference/ref-db/search",
                params={
                    "query": "test",
                    "limit": 10
                }
            )

            assert response.status_code == 500
            assert "Vector search failed" in response.json()["detail"]


class TestNodeRetrievalAPI:
    """Test suite for node retrieval API endpoint."""

    def test_get_node_by_id(self, client, test_database):
        """Test retrieving a node by ID."""
        db_path, (node1_id, node2_id, node3_id), link_ids, create_embedding = test_database  # noqa: E501

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            response = client.get(f"/api/reference/ref-db/nodes/{node1_id}")

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == node1_id
            assert data["title"] == "Person"
            assert data["definition"] == "A human being"
            assert data["source"] == "schema.org"
            assert data["external_id"] == "Person"
            assert "created_at" in data
            assert "updated_at" in data

    def test_get_node_not_found(self, client, test_database):
        """Test retrieving a non-existent node returns 404."""
        db_path, nodes, links, create_embedding = test_database

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            response = client.get("/api/reference/ref-db/nodes/nonexistent-id")

            assert response.status_code == 404
            assert "Node not found" in response.json()["detail"]


class TestLinkRetrievalAPI:
    """Test suite for link retrieval API endpoint."""

    def test_get_outbound_links(self, client, test_database):
        """Test retrieving outbound links for a node."""
        db_path, (node1_id, node2_id, node3_id), (link1_id, link2_id, link3_id), create_embedding = test_database  # noqa: E501

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            response = client.get(
                f"/api/reference/ref-db/nodes/{node1_id}/links",
                params={"direction": "outbound"}
            )

            assert response.status_code == 200
            data = response.json()

            assert "total_links" in data
            assert "links" in data
            assert data["total_links"] == 2  # node1 has 2 outbound links

            # Verify all links have node1 as subject
            for link in data["links"]:
                assert link["subject_node"] == node1_id

    def test_get_inbound_links(self, client, test_database):
        """Test retrieving inbound links for a node."""
        db_path, (node1_id, node2_id, node3_id), (link1_id, link2_id, link3_id), create_embedding = test_database  # noqa: E501

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            response = client.get(
                f"/api/reference/ref-db/nodes/{node3_id}/links",
                params={"direction": "inbound"}
            )

            assert response.status_code == 200
            data = response.json()

            assert data["total_links"] == 2  # node3 has 2 inbound links

            # Verify all links have node3 as object
            for link in data["links"]:
                assert link["object_node"] == node3_id

    def test_get_both_direction_links(self, client, test_database):
        """Test retrieving links in both directions."""
        db_path, (node1_id, node2_id, node3_id), (link1_id, link2_id, link3_id), create_embedding = test_database  # noqa: E501

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            response = client.get(
                f"/api/reference/ref-db/nodes/{node1_id}/links",
                params={"direction": "both"}
            )

            assert response.status_code == 200
            data = response.json()

            assert data["total_links"] == 2  # node1 has 2 total links (both outbound)  # noqa: E501

    def test_get_links_with_predicate_filter(self, client, test_database):
        """Test retrieving links filtered by predicate."""
        db_path, (node1_id, node2_id, node3_id), (link1_id, link2_id, link3_id), create_embedding = test_database  # noqa: E501

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            response = client.get(
                f"/api/reference/ref-db/nodes/{node1_id}/links",
                params={
                    "direction": "outbound",
                    "predicate": "subClassOf"
                }
            )

            assert response.status_code == 200
            data = response.json()

            assert data["total_links"] == 1  # Only 1 subClassOf link

            # Verify predicate filter worked
            for link in data["links"]:
                assert link["predicate"] == "subClassOf"

    def test_get_links_with_limit(self, client, test_database):
        """Test that link retrieval respects limit parameter."""
        db_path, (node1_id, node2_id, node3_id), (link1_id, link2_id, link3_id), create_embedding = test_database  # noqa: E501

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            response = client.get(
                f"/api/reference/ref-db/nodes/{node1_id}/links",
                params={
                    "direction": "outbound",
                    "limit": 1
                }
            )

            assert response.status_code == 200
            data = response.json()

            assert len(data["links"]) == 1

    def test_get_links_node_not_found(self, client, test_database):
        """Test that getting links for non-existent node returns 404."""
        db_path, nodes, links, create_embedding = test_database

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            response = client.get(
                "/api/reference/ref-db/nodes/nonexistent-id/links",
                params={"direction": "both"}
            )

            assert response.status_code == 404
            assert "Node not found" in response.json()["detail"]

    def test_get_links_invalid_direction(self, client, test_database):
        """Test that invalid direction parameter returns error."""
        db_path, (node1_id, node2_id, node3_id), link_ids, create_embedding = test_database  # noqa: E501

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            response = client.get(
                f"/api/reference/ref-db/nodes/{node1_id}/links",
                params={"direction": "invalid"}
            )

            # Should return 400 or 500 depending on where validation happens
            assert response.status_code in [400, 500]

    def test_get_links_ordered_by_created_at(self, client, test_database):
        """Test that links are returned ordered by created_at DESC."""
        db_path, (node1_id, node2_id, node3_id), (link1_id, link2_id, link3_id), create_embedding = test_database  # noqa: E501

        # Create a custom context manager that uses our test database
        from contextlib import contextmanager
        from reference_db.manager import ReferenceManager

        @contextmanager
        def test_reference_manager_context(config):
            manager = ReferenceManager(config, db_path=db_path)
            try:
                yield manager
            finally:
                manager.close()

        with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):  # noqa: E501
            response = client.get(
                f"/api/reference/ref-db/nodes/{node1_id}/links",
                params={"direction": "outbound"}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify links have created_at timestamps
            for link in data["links"]:
                assert "created_at" in link

            # Verify ordering (newer first)
            if len(data["links"]) > 1:
                created_ats = [link["created_at"] for link in data["links"]]
                assert created_ats == sorted(created_ats, reverse=True), \
                    "Links should be ordered by created_at DESC"

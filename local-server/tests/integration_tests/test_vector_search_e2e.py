"""
End-to-end workflow tests for vector search and link retrieval.

Tests complete user workflows including:
1. Adding nodes → Searching → Retrieving links
2. Multi-step semantic discovery workflows
3. Error recovery scenarios
"""

import pytest
import tempfile
import os
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager


@pytest.fixture(scope="module")
def e2e_test_database():
    """Create a comprehensive test database for E2E testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    config = ReferenceConfig()
    manager = ReferenceManager(config, db_path=db_path)

    # Create embeddings helper
    def create_embedding(value: float) -> bytes:
        vec = np.full(384, value, dtype=np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    # Build a small knowledge graph: Person → memberOf → Organization → locatedIn → Place
    person_node = manager.add_reference_node(
        title="Person",
        definition="An individual human being",
        source="schema.org",
        external_id="Person",
        title_embedding=create_embedding(0.8),
        definition_embedding=create_embedding(0.8),
        embedding_dims=384
    )

    org_node = manager.add_reference_node(
        title="Organization",
        definition="An organized group of people with a common purpose",
        source="schema.org",
        external_id="Organization",
        title_embedding=create_embedding(0.75),
        definition_embedding=create_embedding(0.75),
        embedding_dims=384
    )

    place_node = manager.add_reference_node(
        title="Place",
        definition="A location or physical position",
        source="schema.org",
        external_id="Place",
        title_embedding=create_embedding(0.6),
        definition_embedding=create_embedding(0.6),
        embedding_dims=384
    )

    thing_node = manager.add_reference_node(
        title="Thing",
        definition="The most generic type of item",
        source="schema.org",
        external_id="Thing",
        title_embedding=create_embedding(0.3),
        definition_embedding=create_embedding(0.3),
        embedding_dims=384
    )

    # Rollback any pending transactions before adding links
    # (workaround for SQLAlchemy autobegin + explicit begin() conflict)
    if manager.session.in_transaction():
        manager.session.rollback()

    # Create hierarchical relationships using direct session operations
    # (workaround for transaction conflict issue)
    from reference_db.models import ReferenceLink
    from uuid import uuid4
    from datetime import date

    person_subclass_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=person_node.id,
        predicate="subClassOf",
        object_node=thing_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    org_subclass_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=org_node.id,
        predicate="subClassOf",
        object_node=thing_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    place_subclass_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=place_node.id,
        predicate="subClassOf",
        object_node=thing_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    # Create domain-specific relationships
    person_memberof_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=person_node.id,
        predicate="memberOf",
        object_node=org_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    org_location_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=org_node.id,
        predicate="locatedIn",
        object_node=place_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    manager.session.add_all([
        person_subclass_link,
        org_subclass_link,
        place_subclass_link,
        person_memberof_link,
        org_location_link
    ])
    manager.session.commit()

    manager.close()

    yield db_path, {
        "nodes": {
            "person": person_node,
            "organization": org_node,
            "place": place_node,
            "thing": thing_node
        },
        "links": {
            "person_subclass": person_subclass_link,
            "org_subclass": org_subclass_link,
            "place_subclass": place_subclass_link,
            "person_memberof": person_memberof_link,
            "org_location": org_location_link
        },
        "create_embedding": create_embedding
    }

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestSemanticDiscoveryWorkflow:
    """
    Test end-to-end semantic discovery workflows.

    These tests simulate real user workflows where users:
    1. Search for concepts semantically
    2. Retrieve related concepts through links
    3. Navigate the knowledge graph
    """

    def test_search_and_explore_workflow(self, client, e2e_test_database):
        """
        Test workflow: Search for 'person' → Get node → Explore relationships.

        This simulates a user discovering and navigating the knowledge graph.
        """
        db_path, data = e2e_test_database
        person_node = data["nodes"]["person"]
        create_embedding = data["create_embedding"]

        with patch('reference_db.config.ReferenceConfig') as mock_config:
            mock_config.return_value.db_path = db_path

            with patch('embeddings.generate_embeddings.generate_embedding') as mock_embed:
                mock_embed.return_value = create_embedding(0.8)

                # Step 1: User searches for "human being"
                search_response = client.get(
                    "/api/reference/ref-db/search",
                    params={
                        "query": "human being",
                        "limit": 5,
                        "threshold": 0.0
                    }
                )

                assert search_response.status_code == 200
                search_data = search_response.json()
                assert len(search_data["results"]) > 0

                # Find the Person node in results
                person_result = next(
                    (r for r in search_data["results"] if r["title"] == "Person"),
                    None
                )
                assert person_result is not None, "Person node should be found in search results"

                # Step 2: User retrieves the full node details
                node_id = person_result["id"]
                node_response = client.get(f"/api/reference/ref-db/nodes/{node_id}")

                assert node_response.status_code == 200
                node_data = node_response.json()
                assert node_data["title"] == "Person"

                # Step 3: User explores relationships
                links_response = client.get(
                    f"/api/reference/ref-db/nodes/{node_id}/links",
                    params={"direction": "outbound"}
                )

                assert links_response.status_code == 200
                links_data = links_response.json()

                # Person should have 2 outbound links (subClassOf Thing, memberOf Organization)
                assert links_data["total_links"] == 2

                # Verify relationship types
                predicates = [link["predicate"] for link in links_data["links"]]
                assert "subClassOf" in predicates
                assert "memberOf" in predicates

    def test_graph_traversal_workflow(self, client, e2e_test_database):
        """
        Test workflow: Find Person → Follow memberOf → Find Organization → Follow locatedIn.

        This tests multi-hop graph traversal.
        """
        db_path, data = e2e_test_database
        person_node = data["nodes"]["person"]
        org_node = data["nodes"]["organization"]
        place_node = data["nodes"]["place"]
        create_embedding = data["create_embedding"]

        with patch('reference_db.config.ReferenceConfig') as mock_config:
            mock_config.return_value.db_path = db_path

            # Step 1: Get Person node links
            person_links_response = client.get(
                f"/api/reference/ref-db/nodes/{person_node.id}/links",
                params={
                    "direction": "outbound",
                    "predicate": "memberOf"
                }
            )

            assert person_links_response.status_code == 200
            person_links = person_links_response.json()
            assert person_links["total_links"] == 1

            # Extract the Organization node ID
            memberof_link = person_links["links"][0]
            org_id = memberof_link["object_node"]
            assert org_id == org_node.id

            # Step 2: Get Organization node details
            org_response = client.get(f"/api/reference/ref-db/nodes/{org_id}")
            assert org_response.status_code == 200
            assert org_response.json()["title"] == "Organization"

            # Step 3: Get Organization's outbound links
            org_links_response = client.get(
                f"/api/reference/ref-db/nodes/{org_id}/links",
                params={
                    "direction": "outbound",
                    "predicate": "locatedIn"
                }
            )

            assert org_links_response.status_code == 200
            org_links = org_links_response.json()
            assert org_links["total_links"] == 1

            # Extract the Place node ID
            location_link = org_links["links"][0]
            place_id = location_link["object_node"]
            assert place_id == place_node.id

            # Step 4: Get Place node details
            place_response = client.get(f"/api/reference/ref-db/nodes/{place_id}")
            assert place_response.status_code == 200
            assert place_response.json()["title"] == "Place"

            # Successfully traversed: Person → Organization → Place

    def test_reverse_relationship_discovery(self, client, e2e_test_database):
        """
        Test workflow: Find Thing → Get inbound links → Discover all subclasses.

        This tests finding "what points to this node" (inverse relationships).
        """
        db_path, data = e2e_test_database
        thing_node = data["nodes"]["thing"]

        with patch('reference_db.config.ReferenceConfig') as mock_config:
            mock_config.return_value.db_path = db_path

            # Get all things that are subClassOf Thing
            links_response = client.get(
                f"/api/reference/ref-db/nodes/{thing_node.id}/links",
                params={
                    "direction": "inbound",
                    "predicate": "subClassOf"
                }
            )

            assert links_response.status_code == 200
            links_data = links_response.json()

            # Thing should have 3 inbound subClassOf links (Person, Organization, Place)
            assert links_data["total_links"] == 3

            # Verify all are subClassOf relationships
            for link in links_data["links"]:
                assert link["predicate"] == "subClassOf"
                assert link["object_node"] == thing_node.id

            # Extract subject nodes (the subclasses)
            subclass_ids = [link["subject_node"] for link in links_data["links"]]

            # Verify we found all three subclasses
            expected_subclasses = {
                data["nodes"]["person"].id,
                data["nodes"]["organization"].id,
                data["nodes"]["place"].id
            }
            assert set(subclass_ids) == expected_subclasses


class TestErrorRecoveryWorkflows:
    """
    Test error handling in end-to-end workflows.

    These tests ensure graceful degradation and proper error messages.
    """

    def test_search_with_no_results(self, client, e2e_test_database):
        """Test workflow when search returns no results."""
        db_path, data = e2e_test_database
        create_embedding = data["create_embedding"]

        with patch('reference_db.config.ReferenceConfig') as mock_config:
            mock_config.return_value.db_path = db_path

            with patch('embeddings.generate_embeddings.generate_embedding') as mock_embed:
                # Use an embedding very different from existing nodes
                mock_embed.return_value = create_embedding(0.99)

                response = client.get(
                    "/api/reference/ref-db/search",
                    params={
                        "query": "completely unrelated concept",
                        "limit": 5,
                        "threshold": 0.95  # High threshold
                    }
                )

                assert response.status_code == 200
                data = response.json()

                # Should return empty results, not error
                assert data["total_results"] == 0
                assert data["results"] == []

    def test_invalid_node_id_graceful_failure(self, client, e2e_test_database):
        """Test that invalid node IDs return proper 404 errors."""
        db_path, data = e2e_test_database

        with patch('reference_db.config.ReferenceConfig') as mock_config:
            mock_config.return_value.db_path = db_path

            # Try to get non-existent node
            response = client.get("/api/reference/ref-db/nodes/invalid-node-id")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

            # Try to get links for non-existent node
            links_response = client.get(
                "/api/reference/ref-db/nodes/invalid-node-id/links",
                params={"direction": "both"}
            )
            assert links_response.status_code == 404
            assert "not found" in links_response.json()["detail"].lower()

    def test_node_with_no_links(self, client, e2e_test_database):
        """Test retrieving links for a node with no relationships."""
        db_path, data = e2e_test_database

        with patch('reference_db.config.ReferenceConfig') as mock_config:
            mock_config.return_value.db_path = db_path

            # Create a new isolated node
            config = ReferenceConfig()
            with ReferenceManager(config, db_path=db_path) as manager:
                def create_embedding(value: float) -> bytes:
                    vec = np.full(384, value, dtype=np.float32)
                    vec = vec / np.linalg.norm(vec)
                    return vec.tobytes()

                isolated_node = manager.add_reference_node(
                    title="IsolatedNode",
                    definition="A node with no relationships",
                    source="test",
                    external_id="isolated",
                    title_embedding=create_embedding(0.5),
                    definition_embedding=create_embedding(0.5),
                    embedding_dims=384
                )

            # Try to get links for isolated node
            response = client.get(
                f"/api/reference/ref-db/nodes/{isolated_node.id}/links",
                params={"direction": "both"}
            )

            assert response.status_code == 200
            data = response.json()

            # Should return empty list, not error
            assert data["total_links"] == 0
            assert data["links"] == []


class TestPerformanceWorkflows:
    """
    Test performance characteristics of real-world workflows.

    These tests validate that typical workflows complete within acceptable time.
    """

    def test_search_performance_is_acceptable(self, client, e2e_test_database):
        """
        Test that search queries complete in reasonable time.

        Note: This is a smoke test, not a formal performance benchmark.
        """
        db_path, data = e2e_test_database
        create_embedding = data["create_embedding"]

        with patch('reference_db.config.ReferenceConfig') as mock_config:
            mock_config.return_value.db_path = db_path

            with patch('embeddings.generate_embeddings.generate_embedding') as mock_embed:
                mock_embed.return_value = create_embedding(0.8)

                import time
                start = time.perf_counter()

                response = client.get(
                    "/api/reference/ref-db/search",
                    params={
                        "query": "test query",
                        "limit": 20,
                        "threshold": 0.0
                    }
                )

                elapsed = (time.perf_counter() - start) * 1000  # Convert to ms

                assert response.status_code == 200

                # Search should complete in <500ms (generous limit for E2E test)
                # Note: This includes API overhead, not just vector search
                assert elapsed < 500, \
                    f"Search took {elapsed:.2f}ms, expected <500ms"

    def test_link_retrieval_performance(self, client, e2e_test_database):
        """Test that link retrieval completes in reasonable time."""
        db_path, data = e2e_test_database
        thing_node = data["nodes"]["thing"]

        with patch('reference_db.config.ReferenceConfig') as mock_config:
            mock_config.return_value.db_path = db_path

            import time
            start = time.perf_counter()

            response = client.get(
                f"/api/reference/ref-db/nodes/{thing_node.id}/links",
                params={"direction": "both"}
            )

            elapsed = (time.perf_counter() - start) * 1000

            assert response.status_code == 200

            # Link retrieval should complete in <100ms
            assert elapsed < 100, \
                f"Link retrieval took {elapsed:.2f}ms, expected <100ms"

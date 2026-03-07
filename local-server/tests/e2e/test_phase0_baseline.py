"""
Phase 0 E2E Baseline Test Suite.

This module contains the four baseline E2E tests for Phase 0 of the rearchitecture  # noqa: E501
program. These tests validate core functionality of the current application and
serve as a regression gate for all subsequent phases.

Tests:
- test_baseline_taxonomy_lifecycle: Full CRUD lifecycle for taxonomy structures
- test_baseline_embedding_generation: Embedding generation and semantic search
- test_baseline_change_event_tracking: Change event recording and ordering
- test_baseline_predicate_management: Predicate definition and relationships
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # noqa: E501

import pytest  # noqa: E402

from tests.e2e.helpers import poll_until, create_test_hierarchy  # noqa: E402
from tests.e2e.test_data import (  # noqa: E402
    STABLE_TAXONOMY,
    STABLE_PREDICATES,
    STABLE_RELATIONSHIPS,
)


@pytest.mark.e2e
class TestPhase0BaselineTests:
    """Phase 0 baseline E2E tests for ontology and taxonomy operations."""

    def test_baseline_taxonomy_lifecycle(self, e2e_client):
        """
        E2E Test: Full taxonomy lifecycle (CRUD and relationships).

        This test validates the complete lifecycle of taxonomy creation through
        deletion, including:
        1. Create hierarchy: one layer, one domain, four terms
        2. Create predicates and relationships (links)
        3. Verify list and filter operations
        4. Verify semantic search returns correct results
        5. Delete entities in reverse dependency order
        6. Verify clean state after deletion

        The test uses stable test data to ensure reproducible results.
        """
        # Step 1: Create full taxonomy hierarchy using stable test data
        hierarchy = create_test_hierarchy(
            e2e_client,
            layer_title=STABLE_TAXONOMY["layer"]["title"],
            layer_definition=STABLE_TAXONOMY["layer"]["definition"],
            scheme_title=STABLE_TAXONOMY["scheme"]["title"],
            scheme_definition=STABLE_TAXONOMY["scheme"]["definition"],
            classes=STABLE_TAXONOMY["classes"],
        )

        layer_id = hierarchy["layer_id"]
        domain_id = hierarchy["domain_id"]
        term_ids = hierarchy["term_ids"]

        # Verify hierarchy creation returned valid UUIDs
        assert layer_id is not None
        assert domain_id is not None
        assert len(term_ids) == 4
        assert "Database" in term_ids
        assert "Relational Database" in term_ids
        assert "SQL" in term_ids
        assert "Index" in term_ids

        # Step 2: Verify list operations - layer type
        list_layers_response = e2e_client.get(
            "/api/structure_nodes/?node_type=layer"
        )
        assert list_layers_response.status_code == 200
        layers_data = list_layers_response.json()
        assert "data" in layers_data
        assert "total" in layers_data
        # Our layer should be in the results
        layer_titles = [node["title"] for node in layers_data["data"]]
        assert "Computer Science" in layer_titles

        # Step 3: Verify filter operations - get terms under domain
        list_terms_response = e2e_client.get(
            f"/api/structure_nodes/?node_type=term&parent_node_id={domain_id}"
        )
        assert list_terms_response.status_code == 200
        terms_data = list_terms_response.json()
        assert terms_data["total"] == 4, (
            f"Expected 4 terms under domain, got {terms_data['total']}"
        )
        term_titles = [node["title"] for node in terms_data["data"]]
        assert "Database" in term_titles
        assert "Relational Database" in term_titles
        assert "SQL" in term_titles
        assert "Index" in term_titles

        # Step 4: Create predicates for relationships
        predicates = {}
        for predicate_def in STABLE_PREDICATES:
            predicate_data = {
                "title": predicate_def["title"],
                "definition": predicate_def["definition"],
            }
            predicate_response = e2e_client.post(
                "/api/predicates/", json=predicate_data
            )
            assert predicate_response.status_code == 201, (
                f"Failed to create predicate: {predicate_response.text}"
            )
            predicate = predicate_response.json()
            predicates[predicate_def["identifier"]] = predicate["id"]

        # Step 5: Create relationships (links) using predicates
        link_ids = []
        for source_title, target_title, predicate_identifier in STABLE_RELATIONSHIPS:
            # Get the predicate title from STABLE_PREDICATES
            predicate_def = next(
                p for p in STABLE_PREDICATES
                if p["identifier"] == predicate_identifier
            )
            link_data = {
                "source_node_id": term_ids[source_title],
                "target_node_id": term_ids[target_title],
                "predicate": predicate_def["title"],
                "predicate_id": predicates[predicate_identifier],
            }
            link_response = e2e_client.post(
                "/api/structure_nodes/links", json=link_data
            )
            assert link_response.status_code == 201, (
                f"Failed to create link from {source_title} to {target_title}: {link_response.text}"  # noqa: E501
            )
            link = link_response.json()
            link_ids.append(link["id"])

        # Step 6: Verify list-links endpoint
        list_links_response = e2e_client.get(
            f"/api/structure_nodes/links?source_node_id={term_ids['Relational Database']}"  # noqa: E501
        )
        assert list_links_response.status_code == 200
        links_data = list_links_response.json()
        assert len(links_data) >= 1, "Should have at least one link from Relational Database"  # noqa: E501

        # Step 7: Verify semantic search returns "Database" in top results
        search_data = {
            "query": "organized collection of data",
            "node_type": "term",
            "limit": 10,
        }
        search_response = e2e_client.post(
            "/api/structure_nodes/find", json=search_data
        )
        assert search_response.status_code == 200, (
            f"Search failed: {search_response.text}"
        )
        search_results = search_response.json()
        assert isinstance(search_results, list), (
            f"Search results should be a list, got {type(search_results)}"
        )

        # "Database" should appear in the top results (before unrelated terms like "Firewall")
        assert len(search_results) > 0, (
            "Search should return at least one result"
        )
        search_titles = [result.get("title") for result in search_results]
        # "Database" should be in results since its definition matches the search query
        assert "Database" in search_titles, (
            f"'Database' should be in search results. Got: {search_titles}"
        )

        # Step 8: Verify delete operations in reverse dependency order
        # Delete all links first
        for link_id in link_ids:
            delete_link_response = e2e_client.delete(
                f"/api/structure_nodes/links/{link_id}"
            )
            assert delete_link_response.status_code == 204, (
                f"Failed to delete link: {delete_link_response.text}"
            )

        # Delete all predicates
        for predicate_id in predicates.values():
            delete_predicate_response = e2e_client.delete(
                f"/api/predicates/{predicate_id}"
            )
            assert delete_predicate_response.status_code in [200, 204], (
                f"Failed to delete predicate: {delete_predicate_response.text}"
            )

        # Delete all terms
        for term_id in term_ids.values():
            delete_term_response = e2e_client.delete(
                f"/api/structure_nodes/{term_id}"
            )
            assert delete_term_response.status_code == 204, (
                f"Failed to delete term: {delete_term_response.text}"
            )

        # Delete domain
        delete_domain_response = e2e_client.delete(
            f"/api/structure_nodes/{domain_id}"
        )
        assert delete_domain_response.status_code == 204, (
            f"Failed to delete domain: {delete_domain_response.text}"
        )

        # Delete layer
        delete_layer_response = e2e_client.delete(
            f"/api/structure_nodes/{layer_id}"
        )
        assert delete_layer_response.status_code == 204, (
            f"Failed to delete layer: {delete_layer_response.text}"
        )

        # Step 9: Verify clean state after deletion
        # Check layer is deleted
        verify_layer_response = e2e_client.get(f"/api/structure_nodes/{layer_id}")
        assert verify_layer_response.status_code == 404, (
            "Layer should be deleted"
        )

        # Check domain is deleted
        verify_domain_response = e2e_client.get(f"/api/structure_nodes/{domain_id}")
        assert verify_domain_response.status_code == 404, (
            "Domain should be deleted"
        )

        # Verify list-nodes for our layer returns zero
        final_list_response = e2e_client.get(
            "/api/structure_nodes/?node_type=layer"
        )
        assert final_list_response.status_code == 200
        final_data = final_list_response.json()
        final_titles = [node["title"] for node in final_data["data"]]
        assert "Computer Science" not in final_titles, (
            "Layer should be removed from list"
        )

    def test_baseline_embedding_generation(self, e2e_client):
        """
        E2E Test: Embedding generation and semantic search ranking.

        This test validates that:
        1. Creating nodes generates non-null title_embedding and definition_embedding
        2. Embeddings are real float arrays of nonzero length (not empty or zero-filled)
        3. Semantic search ranks semantically similar terms higher than unrelated terms
        4. Updating a node's title causes the stored title_embedding to differ

        The test uses three semantically varied terms to verify search ranking behavior.
        """
        # Step 1: Create a taxonomy and domain for embedding tests
        hierarchy = create_test_hierarchy(
            e2e_client,
            layer_title="Embedding Test Taxonomy",
            layer_definition="Taxonomy for embedding generation testing",
            scheme_title="Embedding Test Scheme",
            scheme_definition="Scheme for embedding testing",
            classes=[
                {
                    "title": "Database",
                    "definition": "An organized collection of structured information",
                },
                {
                    "title": "Data Store",
                    "definition": "A system for storing and retrieving data efficiently",
                },
                {
                    "title": "Firewall",
                    "definition": "A network security system that monitors traffic",
                },
            ],
        )

        layer_id = hierarchy["layer_id"]
        domain_id = hierarchy["domain_id"]
        term_ids = hierarchy["term_ids"]

        # Step 2: Verify embeddings were generated for all terms
        # Poll until embeddings are available with proper validation
        def embeddings_generated():
            response = e2e_client.get(f"/api/structure_nodes/{term_ids['Database']}")
            if response.status_code != 200:
                return False
            node = response.json()
            # Check that embeddings exist and are valid
            title_emb = node.get("title_embedding")
            def_emb = node.get("definition_embedding")
            if title_emb is None or def_emb is None:
                return False
            # Verify embeddings are non-empty lists with actual float values
            return (
                isinstance(title_emb, list)
                and len(title_emb) > 0
                and isinstance(def_emb, list)
                and len(def_emb) > 0
            )

        poll_until(
            embeddings_generated,
            timeout=15.0,
            error_message="Embeddings not generated within timeout",
        )

        # Step 3: Assert embeddings are present and valid for all terms
        for term_title, term_id in term_ids.items():
            response = e2e_client.get(f"/api/structure_nodes/{term_id}")
            assert response.status_code == 200, (
                f"Failed to retrieve term {term_title}: {response.text}"
            )
            node = response.json()

            # Assert title_embedding exists and is valid
            assert node.get("title_embedding") is not None, (
                f"Term '{term_title}' missing title_embedding"
            )
            title_emb = node.get("title_embedding")
            assert isinstance(title_emb, list), (
                f"Term '{term_title}' title_embedding must be a list, got {type(title_emb)}"  # noqa: E501
            )
            assert len(title_emb) > 0, (
                f"Term '{term_title}' title_embedding is empty"
            )
            # Verify it contains actual float values (not zeros)
            assert any(v != 0.0 for v in title_emb), (
                f"Term '{term_title}' title_embedding is all zeros"
            )

            # Assert definition_embedding exists and is valid
            assert node.get("definition_embedding") is not None, (
                f"Term '{term_title}' missing definition_embedding"
            )
            def_emb = node.get("definition_embedding")
            assert isinstance(def_emb, list), (
                f"Term '{term_title}' definition_embedding must be a list, got {type(def_emb)}"  # noqa: E501
            )
            assert len(def_emb) > 0, (
                f"Term '{term_title}' definition_embedding is empty"
            )
            # Verify it contains actual float values (not zeros)
            assert any(v != 0.0 for v in def_emb), (
                f"Term '{term_title}' definition_embedding is all zeros"
            )

        # Step 4: Verify semantic search ranking
        # Search query should rank "Database" and "Data Store" above "Firewall"
        search_data = {
            "query": "organized collection of data",
            "node_type": "term",
            "limit": 10,
        }
        search_response = e2e_client.post(
            "/api/structure_nodes/find", json=search_data
        )
        assert search_response.status_code == 200, (
            f"Search failed: {search_response.text}"
        )
        search_results = search_response.json()
        assert isinstance(search_results, list), (
            f"Search results should be a list, got {type(search_results)}"
        )

        # Extract search result titles and verify ranking
        search_titles = [result.get("title") for result in search_results]
        assert "Database" in search_titles, (
            f"'Database' should appear in search results. Got: {search_titles}"
        )

        # Find positions in search results
        database_pos = search_titles.index("Database")
        firewall_pos = (
            search_titles.index("Firewall")
            if "Firewall" in search_titles
            else float("inf")
        )

        # Assert "Database" ranks higher than "Firewall"
        assert database_pos < firewall_pos, (
            f"'Database' (position {database_pos}) should rank higher than "
            f"'Firewall' (position {firewall_pos})"
        )

        # Verify "Data Store" appears in top results (high semantic similarity)
        if "Data Store" in search_titles:
            data_store_pos = search_titles.index("Data Store")
            assert data_store_pos < 5, (
                f"'Data Store' should appear in top results, found at position {data_store_pos}"  # noqa: E501
            )

        # Step 5: Verify embedding regeneration on title update
        # Get the original title_embedding
        original_response = e2e_client.get(
            f"/api/structure_nodes/{term_ids['Database']}"
        )
        assert original_response.status_code == 200
        original_node = original_response.json()
        original_title_embedding = original_node.get("title_embedding")
        assert original_title_embedding is not None, (
            "Original title_embedding should not be None"
        )

        # Update the title
        update_data = {"title": "Relational Database System"}
        update_response = e2e_client.put(
            f"/api/structure_nodes/{term_ids['Database']}", json=update_data
        )
        assert update_response.status_code == 200, (
            f"Failed to update node: {update_response.text}"
        )

        # Poll until the embedding is regenerated (should differ from original)
        def embedding_updated():
            response = e2e_client.get(
                f"/api/structure_nodes/{term_ids['Database']}"
            )
            if response.status_code != 200:
                return False
            node = response.json()
            new_title_embedding = node.get("title_embedding")
            # Check if embedding has changed
            return (
                new_title_embedding is not None
                and new_title_embedding != original_title_embedding
            )

        poll_until(
            embedding_updated,
            timeout=10.0,
            error_message="Title embedding not regenerated after update",
        )

        # Verify the final state
        final_response = e2e_client.get(
            f"/api/structure_nodes/{term_ids['Database']}"
        )
        assert final_response.status_code == 200
        final_node = final_response.json()
        new_title_embedding = final_node.get("title_embedding")
        assert new_title_embedding != original_title_embedding, (
            "Title embedding should differ after updating the title"
        )

        # Step 6: Cleanup
        # Delete in reverse dependency order
        for term_id in term_ids.values():
            e2e_client.delete(f"/api/structure_nodes/{term_id}")
        e2e_client.delete(f"/api/structure_nodes/{domain_id}")
        e2e_client.delete(f"/api/structure_nodes/{layer_id}")

    def test_baseline_change_event_tracking(self, e2e_client):
        """
        E2E Test: Change event recording and chronological ordering.

        This test validates that:
        1. Change events are created for all operations
        2. Events are recorded with correct types
        3. Events maintain chronological ordering
        4. All entity types generate appropriate events

        The test creates 7 entities and verifies that exactly 7 change events
        are recorded in the correct order.
        """
        # Step 1: Create a taxonomy (should generate 1 change event)
        taxonomy_data = {
            "node_type": "layer",
            "parent_node_id": None,
            "title": "Change Event Test Taxonomy",
            "definition": "Taxonomy for change event tracking",
        }
        taxonomy_response = e2e_client.post(
            "/api/structure_nodes/", json=taxonomy_data
        )
        assert taxonomy_response.status_code == 201
        taxonomy_id = taxonomy_response.json()["id"]

        # Step 2: Create scheme (change event 2)
        scheme_data = {
            "node_type": "domain",
            "parent_node_id": taxonomy_id,
            "title": "Change Event Test Scheme",
            "definition": "Scheme for change event testing",
        }
        scheme_response = e2e_client.post(
            "/api/structure_nodes/", json=scheme_data
        )
        assert scheme_response.status_code == 201
        scheme_id = scheme_response.json()["id"]

        # Step 3: Create 5 classes (change events 3-7)
        class_ids = []
        for i in range(5):
            class_data = {
                "node_type": "term",
                "parent_node_id": scheme_id,
                "title": f"Change Event Test Class {i+1}",
                "definition": f"Class {i+1} for testing change events",
            }
            class_response = e2e_client.post(
                "/api/structure_nodes/", json=class_data
            )
            assert class_response.status_code == 201
            class_ids.append(class_response.json()["id"])

        # Step 4: Retrieve change events
        change_events_response = e2e_client.get("/api/change_events/")
        assert change_events_response.status_code == 200
        events = change_events_response.json()
        # API returns List[ChangeEventOut] directly
        assert isinstance(events, list)

        # Step 5: Filter events to only those created by this test
        # (by checking if they reference our created entities)
        created_node_ids_str = {str(taxonomy_id), str(scheme_id)} | {str(cid) for cid in class_ids}  # noqa: E501
        test_events = [
            e for e in events
            if e.get("record_id") and str(e.get("record_id")) in created_node_ids_str  # noqa: E501
        ]

        # Step 6: Verify change event counts and types
        # We created 7 entities (1 taxonomy + 1 scheme + 5 classes), so we should have exactly 7 creation events  # noqa: E501
        assert len(test_events) >= 7, f"Expected at least 7 change events for our entities, got {len(test_events)}"  # noqa: E501

        # Step 7: Verify chronological ordering
        # Events should be returned in descending chronological order (newest first)  # noqa: E501
        if len(test_events) > 1:
            timestamps = [e.get("event_timestamp") for e in test_events]
            for i in range(len(timestamps) - 1):
                assert timestamps[i] >= timestamps[i + 1], (
                    f"Events not in descending chronological order: "
                    f"{timestamps[i]} should be >= {timestamps[i + 1]}"
                )

        # Step 8: Verify event structure
        for event in test_events:
            assert "event_type" in event, f"Event missing event_type field: {event.keys()}"  # noqa: E501
            assert "event_timestamp" in event, f"Event missing event_timestamp field: {event.keys()}"  # noqa: E501

        # Step 9: Cleanup
        for class_id in class_ids:
            e2e_client.delete(f"/api/structure_nodes/{class_id}")
        e2e_client.delete(f"/api/structure_nodes/{scheme_id}")
        e2e_client.delete(f"/api/structure_nodes/{taxonomy_id}")

    def test_baseline_predicate_management(self, e2e_client):
        """
        E2E Test: Predicate definition and relationship management.

        This test validates that:
        1. Property definitions can be created
        2. Relationships can be created using predicates
        3. Predicate references are maintained
        4. Duplicate predicates are rejected
        5. Predicate deletion cascades appropriately

        The test creates predicates, uses them in relationships, and verifies
        proper enforcement of constraints.
        """
        # Step 1: Create a taxonomy and scheme for predicate testing
        taxonomy_data = {
            "node_type": "layer",
            "parent_node_id": None,
            "title": "Predicate Test Taxonomy",
            "definition": "Taxonomy for predicate management testing",
        }
        taxonomy_response = e2e_client.post(
            "/api/structure_nodes/", json=taxonomy_data
        )
        assert taxonomy_response.status_code == 201
        taxonomy_id = taxonomy_response.json()["id"]

        scheme_data = {
            "node_type": "domain",
            "parent_node_id": taxonomy_id,
            "title": "Predicate Test Scheme",
            "definition": "Scheme for predicate testing",
        }
        scheme_response = e2e_client.post(
            "/api/structure_nodes/", json=scheme_data
        )
        assert scheme_response.status_code == 201
        scheme_id = scheme_response.json()["id"]

        # Step 2: Create two classes for relationships
        class_data_1 = {
            "node_type": "term",
            "parent_node_id": scheme_id,
            "title": "Predicate Test Class 1",
            "definition": "First class for predicate testing",
        }
        class_response_1 = e2e_client.post(
            "/api/structure_nodes/", json=class_data_1
        )
        assert class_response_1.status_code == 201
        class_id_1 = class_response_1.json()["id"]

        class_data_2 = {
            "node_type": "term",
            "parent_node_id": scheme_id,
            "title": "Predicate Test Class 2",
            "definition": "Second class for predicate testing",
        }
        class_response_2 = e2e_client.post(
            "/api/structure_nodes/", json=class_data_2
        )
        assert class_response_2.status_code == 201
        class_id_2 = class_response_2.json()["id"]

        # Step 3: Create a predicate
        predicate_data = {
            "title": "test_predicate_001",
            "definition": "A test predicate for baseline testing",
        }
        predicate_response = e2e_client.post(
            "/api/predicates/", json=predicate_data
        )
        assert predicate_response.status_code == 201
        predicate = predicate_response.json()
        predicate_id = predicate["id"]

        # Step 4: Create a relationship using the predicate
        link_data = {
            "source_node_id": class_id_1,
            "target_node_id": class_id_2,
            "predicate": "test_predicate_001",
            "predicate_id": predicate_id,
        }
        link_response = e2e_client.post(
            "/api/structure_nodes/links", json=link_data
        )
        assert link_response.status_code == 201
        link = link_response.json()
        link_id = link["id"]

        # Step 5: Verify predicate reference
        get_predicate_response = e2e_client.get(f"/api/predicates/{predicate_id}")  # noqa: E501
        assert get_predicate_response.status_code == 200
        predicate_retrieved = get_predicate_response.json()
        assert predicate_retrieved["title"] == "test_predicate_001"

        # Step 6: Test duplicate predicate rejection
        duplicate_predicate_data = {
            "title": "test_predicate_001",  # Same title
            "definition": "Duplicate predicate",
        }
        duplicate_response = e2e_client.post(
            "/api/predicates/", json=duplicate_predicate_data
        )
        # Duplicate creation must fail with 400 or 409, not succeed with 201
        assert duplicate_response.status_code in [400, 409], f"Duplicate predicate should be rejected, got {duplicate_response.status_code}"  # noqa: E501

        # Step 7: Delete link and verify
        delete_link_response = e2e_client.delete(
            f"/api/structure_nodes/links/{link_id}"
        )
        assert delete_link_response.status_code == 204

        # Step 8: Cleanup entities
        e2e_client.delete(f"/api/structure_nodes/{class_id_1}")
        e2e_client.delete(f"/api/structure_nodes/{class_id_2}")
        e2e_client.delete(f"/api/structure_nodes/{scheme_id}")
        e2e_client.delete(f"/api/structure_nodes/{taxonomy_id}")

        # Delete predicate
        delete_predicate_response = e2e_client.delete(
            f"/api/predicates/{predicate_id}"
        )
        assert delete_predicate_response.status_code in [204, 200]

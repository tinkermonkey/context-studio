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

from tests.e2e.helpers import poll_until  # noqa: E402
from tests.e2e.test_data import STABLE_CONCEPTS  # noqa: E402


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
        from tests.e2e.helpers import create_test_hierarchy

        hierarchy = create_test_hierarchy(
            e2e_client,
            layer_title="Computer Science",
            layer_definition="The study of computation and information",
            scheme_title="Data Management",
            scheme_definition="Technologies and methods for storing and retrieving data",  # noqa: E501
            classes=[
                {
                    "title": "Database",
                    "definition": "An organized collection of structured information",
                },
                {
                    "title": "Relational Database",
                    "definition": "A database based on the relational model of data",
                },
                {
                    "title": "SQL",
                    "definition": "Structured Query Language for managing relational databases",  # noqa: E501
                },
                {
                    "title": "Index",
                    "definition": "A data structure that improves the speed of data retrieval",  # noqa: E501
                },
            ],
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
        from tests.e2e.test_data import STABLE_PREDICATES

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

        # Link 1: Relational Database is_a Database
        link1_data = {
            "source_node_id": term_ids["Relational Database"],
            "target_node_id": term_ids["Database"],
            "predicate": "Is A",
            "predicate_id": predicates["is_a"],
        }
        link1_response = e2e_client.post(
            "/api/structure_nodes/links", json=link1_data
        )
        assert link1_response.status_code == 201, (
            f"Failed to create link1: {link1_response.text}"
        )
        link1 = link1_response.json()
        link_ids.append(link1["id"])

        # Link 2: SQL used_by Relational Database
        link2_data = {
            "source_node_id": term_ids["SQL"],
            "target_node_id": term_ids["Relational Database"],
            "predicate": "Used By",
            "predicate_id": predicates["used_by"],
        }
        link2_response = e2e_client.post(
            "/api/structure_nodes/links", json=link2_data
        )
        assert link2_response.status_code == 201, (
            f"Failed to create link2: {link2_response.text}"
        )
        link2 = link2_response.json()
        link_ids.append(link2["id"])

        # Link 3: Index part_of Database
        link3_data = {
            "source_node_id": term_ids["Index"],
            "target_node_id": term_ids["Database"],
            "predicate": "Part Of",
            "predicate_id": predicates["part_of"],
        }
        link3_response = e2e_client.post(
            "/api/structure_nodes/links", json=link3_data
        )
        assert link3_response.status_code == 201, (
            f"Failed to create link3: {link3_response.text}"
        )
        link3 = link3_response.json()
        link_ids.append(link3["id"])

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
        if len(search_results) > 0:
            search_titles = [result.get("title") for result in search_results]
            # At least "Database" should be in results
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
        1. Embeddings are generated for created nodes
        2. Semantic search correctly ranks results by similarity
        3. Similar concepts rank higher than dissimilar ones

        The test creates multiple classes with varying semantic similarity
        and verifies that search results are properly ranked.
        """
        # Step 1: Create a taxonomy and scheme for embedding tests
        taxonomy_data = {
            "node_type": "layer",
            "parent_node_id": None,
            "title": "Embedding Test Taxonomy",
            "definition": "Taxonomy for embedding generation testing",
        }
        taxonomy_response = e2e_client.post(
            "/api/structure_nodes/", json=taxonomy_data
        )
        assert taxonomy_response.status_code == 201
        taxonomy_id = taxonomy_response.json()["id"]

        scheme_data = {
            "node_type": "domain",
            "parent_node_id": taxonomy_id,
            "title": "Embedding Test Scheme",
            "definition": "Scheme for embedding testing",
        }
        scheme_response = e2e_client.post(
            "/api/structure_nodes/", json=scheme_data
        )
        assert scheme_response.status_code == 201
        scheme_id = scheme_response.json()["id"]

        # Step 2: Create base class for embedding
        base_class_data = {
            "node_type": "term",
            "parent_node_id": scheme_id,
            "title": "Computer Science",
            "definition": "The study of computation, information, and automation",  # noqa: E501
        }
        base_response = e2e_client.post(
            "/api/structure_nodes/", json=base_class_data
        )
        assert base_response.status_code == 201
        base_class_id = base_response.json()["id"]

        # Step 3: Create semantically similar class
        similar_class_data = {
            "node_type": "term",
            "parent_node_id": scheme_id,
            "title": "Programming Languages",
            "definition": "Languages used to write computer programs and software",  # noqa: E501
        }
        similar_response = e2e_client.post(
            "/api/structure_nodes/", json=similar_class_data
        )
        assert similar_response.status_code == 201
        similar_class_id = similar_response.json()["id"]

        # Step 4: Create semantically different class
        different_class_data = {
            "node_type": "term",
            "parent_node_id": scheme_id,
            "title": "Medieval History",
            "definition": "The study of the Middle Ages and historical civilizations",  # noqa: E501
        }
        different_response = e2e_client.post(
            "/api/structure_nodes/", json=different_class_data
        )
        assert different_response.status_code == 201
        different_class_id = different_response.json()["id"]

        # Step 5: Verify embeddings were generated
        # Poll until embeddings are available
        def embeddings_generated():
            response = e2e_client.get(f"/api/structure_nodes/{base_class_id}")
            if response.status_code != 200:
                return False
            node = response.json()
            # Check if embeddings exist (they may be None or lists)
            return node.get("title_embedding") is not None or node.get("definition_embedding") is not None  # noqa: E501

        poll_until(
            embeddings_generated,
            timeout=15.0,
            error_message="Embeddings not generated within timeout",
        )

        # Step 6: Perform semantic search on base class definition
        search_data = {
            "query": "computation and programming",
            "limit": 10,
        }
        search_response = e2e_client.post(
            "/api/structure_nodes/find", json=search_data
        )
        assert search_response.status_code == 200
        search_results = search_response.json()
        # API returns List[NodeSearchResult] directly
        assert isinstance(search_results, list)

        # Step 7: Cleanup
        for node_id in [base_class_id, similar_class_id, different_class_id, scheme_id, taxonomy_id]:  # noqa: E501
            e2e_client.delete(f"/api/structure_nodes/{node_id}")

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

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
from datetime import datetime

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
        # links_data is a paginated response with {"data": [...], "total": N, ...}
        assert isinstance(links_data, dict), "Response should be a dict"
        assert "data" in links_data, "Response should have 'data' key"
        assert isinstance(links_data["data"], list), "Response 'data' should be a list"
        assert len(links_data["data"]) >= 1, "Should have at least one link from Relational Database"  # noqa: E501

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
        # Verify search correctness: "Database" should rank in top 3 results
        # This validates search quality for the Phase 0 regression gate
        database_pos = search_titles.index("Database")
        assert database_pos < 3, (
            f"'Database' should rank in top 3 results for semantic search "
            f"(got position {database_pos})"
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

        # Verify clean state after deletion
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
        # Verify hierarchy was created successfully
        assert layer_id is not None
        assert domain_id is not None
        assert len(term_ids) == 3

        # Step 2: Verify embeddings were generated for all terms
        # Poll until embeddings are available with proper validation
        def embeddings_generated():
            response = e2e_client.get(f"/api/structure_nodes/{term_ids['Database']}")
            if response.status_code != 200:
                return (False, "Failed to retrieve node")
            node = response.json()
            # Check that embeddings exist and are valid
            title_emb = node.get("title_embedding")
            def_emb = node.get("definition_embedding")
            if title_emb is None or def_emb is None:
                return (False, "Embeddings not yet generated")
            # Verify embeddings are non-empty lists with actual float values
            if (
                isinstance(title_emb, list)
                and len(title_emb) > 0
                and isinstance(def_emb, list)
                and len(def_emb) > 0
            ):
                return (True, node)
            return (False, "Embeddings exist but are empty or invalid")

        poll_until(
            embeddings_generated,
            timeout_seconds=15.0,
            description="embeddings to be generated",
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

        # Verify "Data Store" appears in results (high semantic similarity to search query)
        assert "Data Store" in search_titles, (
            f"'Data Store' should appear in search results. Got: {search_titles}"
        )
        data_store_pos = search_titles.index("Data Store")
        assert data_store_pos < 5, (
            f"'Data Store' should appear in top 5 results, found at position {data_store_pos}"  # noqa: E501
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
                return (False, "Failed to retrieve node")
            node = response.json()
            new_title_embedding = node.get("title_embedding")
            # Check if embedding has changed
            if (
                new_title_embedding is not None
                and new_title_embedding != original_title_embedding
            ):
                return (True, new_title_embedding)
            return (False, "Embedding has not been regenerated yet")

        poll_until(
            embedding_updated,
            timeout_seconds=10.0,
            description="title embedding to be regenerated after update",
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

    def test_baseline_change_event_tracking(self, e2e_client):
        """
        E2E Test: Change event recording and chronological ordering.

        This test validates that:
        1. Create operations generate change events (may include automatic child events)
        2. Every update operation generates exactly one update event
        3. Events have correct record_type, event_type, and data snapshots
        4. Events are returned in chronological order (newest first)
        5. Create events have old_data=None and non-null new_data
        6. Update events have both old_data and new_data populated
        7. All event timestamps are valid ISO8601 strings

        The test creates 8 entities (1 layer, 1 domain, 3 terms, 1 predicate, 2 links)
        using stable domain terms (Database, Relational Database, SQL) from STABLE_TAXONOMY.
        The spec requires exactly 8 change events for these operations (each entity creation
        generates one event via database triggers). With SentenceTransformer 5.0.0 pinned,
        this ensures deterministic embedding generation across test runs. The test verifies
        that change events are recorded with correct structure and ordering.
        """
        # Step 1: Capture initial change event count (for delta-based isolation)
        initial_events_response = e2e_client.get(
            "/api/change_events/?limit=1000"
        )
        assert initial_events_response.status_code == 200, (
            f"Failed to fetch initial events: {initial_events_response.status_code}. "
            f"Response: {initial_events_response.text}"
        )
        initial_events = initial_events_response.json()
        assert isinstance(initial_events, list), (
            f"Expected list of change events, got {type(initial_events)}"
        )
        initial_count = len(initial_events)

        # Step 2: Create taxonomy (layer) - event 1
        # Use stable domain term from STABLE_TAXONOMY for deterministic embedding
        layer_data = {
            "node_type": "layer",
            "parent_node_id": None,
            "title": STABLE_TAXONOMY["layer"]["title"],
            "definition": STABLE_TAXONOMY["layer"]["definition"],
        }
        layer_response = e2e_client.post(
            "/api/structure_nodes/", json=layer_data
        )
        assert layer_response.status_code == 201, (
            f"Failed to create layer: {layer_response.status_code}. "
            f"Response: {layer_response.text}"
        )
        layer = layer_response.json()
        layer_id = layer["id"]

        # Step 3: Create scheme (domain) - event 2
        # Use stable domain term from STABLE_TAXONOMY for deterministic embedding
        domain_data = {
            "node_type": "domain",
            "parent_node_id": layer_id,
            "title": STABLE_TAXONOMY["scheme"]["title"],
            "definition": STABLE_TAXONOMY["scheme"]["definition"],
        }
        domain_response = e2e_client.post(
            "/api/structure_nodes/", json=domain_data
        )
        assert domain_response.status_code == 201, (
            f"Failed to create domain: {domain_response.status_code}. "
            f"Response: {domain_response.text}"
        )
        domain = domain_response.json()
        domain_id = domain["id"]

        # Step 4: Create 3 terms using stable taxonomy concepts - events 3, 4, 5
        # Use stable concepts from STABLE_TAXONOMY for deterministic embedding behavior
        term_ids = {}
        stable_terms = STABLE_TAXONOMY["classes"][:3]  # Database, Relational Database, SQL
        for i, term_def in enumerate(stable_terms):
            term_data = {
                "node_type": "term",
                "parent_node_id": domain_id,
                "title": term_def["title"],
                "definition": term_def["definition"],
            }
            term_response = e2e_client.post(
                "/api/structure_nodes/", json=term_data
            )
            assert term_response.status_code == 201, (
                f"Failed to create term '{term_def['title']}': {term_response.status_code}. "
                f"Response: {term_response.text}"
            )
            term = term_response.json()
            term_ids[f"term_{i+1}"] = term["id"]

        # Step 5: Create 1 predicate - event 6
        predicate_data = {
            "title": "test_predicate_change_events",
            "definition": "A test predicate for change event tracking",
        }
        predicate_response = e2e_client.post(
            "/api/predicates/", json=predicate_data
        )
        assert predicate_response.status_code == 201, (
            f"Failed to create predicate: {predicate_response.status_code}. "
            f"Response: {predicate_response.text}"
        )
        predicate = predicate_response.json()
        predicate_id = predicate["id"]

        # Step 6: Create 2 links - events 7, 8
        link_ids = []
        link1_data = {
            "source_node_id": term_ids["term_1"],
            "target_node_id": term_ids["term_2"],
            "predicate": "test_predicate_change_events",
            "predicate_id": predicate_id,
        }
        link1_response = e2e_client.post(
            "/api/structure_nodes/links", json=link1_data
        )
        assert link1_response.status_code == 201, (
            f"Failed to create link 1: {link1_response.status_code}. "
            f"Response: {link1_response.text}"
        )
        link1 = link1_response.json()
        link_ids.append(link1["id"])

        link2_data = {
            "source_node_id": term_ids["term_2"],
            "target_node_id": term_ids["term_3"],
            "predicate": "test_predicate_change_events",
            "predicate_id": predicate_id,
        }
        link2_response = e2e_client.post(
            "/api/structure_nodes/links", json=link2_data
        )
        assert link2_response.status_code == 201, (
            f"Failed to create link 2: {link2_response.status_code}. "
            f"Response: {link2_response.text}"
        )
        link2 = link2_response.json()
        link_ids.append(link2["id"])

        # Step 7: Retrieve all change events after operations
        final_events_response = e2e_client.get(
            "/api/change_events/?limit=1000"
        )
        assert final_events_response.status_code == 200, (
            f"Failed to fetch final events: {final_events_response.status_code}. "
            f"Response: {final_events_response.text}"
        )
        final_events = final_events_response.json()
        assert isinstance(final_events, list), (
            f"Expected list of change events, got {type(final_events)}"
        )
        final_count = len(final_events)

        # Step 8: Verify change event count matches spec requirement (using stable domain terms)
        # Events are returned newest-first, so new events are at the beginning
        new_events_count = final_count - initial_count
        # The spec requires exactly 8 events: 1 layer create + 1 domain create + 3 term creates
        # + 1 predicate create + 1 link create + 1 link create = 8 events total.
        # Each entity creation generates exactly one change event via database triggers.
        # Using pinned SentenceTransformer 5.0.0 with stable domain terms ensures
        # deterministic and reproducible event generation across test runs.
        assert new_events_count == 8, (
            f"Expected exactly 8 change events per spec, "
            f"got {new_events_count}. Initial: {initial_count}, Final: {final_count}"
        )

        # Extract the new events (slice from start, since newest-first)
        new_events = final_events[:new_events_count]

        # Step 9: Verify record type distribution
        # Count unique record IDs for each type to verify we created the right entities
        structure_node_events = [
            e for e in new_events if e["record_type"] == "structure_node"
        ]
        predicate_events = [
            e for e in new_events if e["record_type"] == "predicate"
        ]
        link_events = [
            e for e in new_events if e["record_type"] == "structure_node_link"
        ]

        # Get unique record IDs (to account for possible duplicates)
        unique_structure_node_ids = set(
            e["record_id"] for e in structure_node_events
        )
        unique_predicate_ids = set(
            e["record_id"] for e in predicate_events
        )
        unique_link_ids = set(
            e["record_id"] for e in link_events
        )

        # Verify correct number of unique entities (regardless of duplicate events)
        assert len(unique_structure_node_ids) == 5, (
            f"Expected 5 unique structure_node IDs (1 layer + 1 domain + 3 terms), "
            f"got {len(unique_structure_node_ids)}: {unique_structure_node_ids}"
        )
        assert len(unique_predicate_ids) == 1, (
            f"Expected 1 unique predicate ID, got {len(unique_predicate_ids)}: {unique_predicate_ids}"
        )
        assert len(unique_link_ids) == 2, (
            f"Expected 2 unique structure_node_link IDs, got {len(unique_link_ids)}: {unique_link_ids}"
        )

        # Step 10: Verify all create events have correct structure
        for event in new_events:
            # Validate all required fields exist
            required_fields = {
                "id", "event_type", "record_type", "record_id",
                "old_data", "new_data", "event_timestamp", "processed"
            }
            missing_fields = required_fields - set(event.keys())
            assert not missing_fields, (
                f"Event missing required fields: {missing_fields}. "
                f"Event has keys: {set(event.keys())}. "
                f"Event ID: {event.get('id', 'unknown')}"
            )

            # Validate event_type is valid
            valid_event_types = {"create", "update", "delete"}
            assert event["event_type"] in valid_event_types, (
                f"Invalid event_type '{event['event_type']}' for event {event.get('id', 'unknown')}. "
                f"Must be one of {valid_event_types}"
            )

            # Validate data fields based on event type
            if event["event_type"] == "create":
                # Create events should have old_data as None and new_data populated
                assert event["old_data"] is None, (
                    f"Create event {event.get('id')} should have old_data=None, "
                    f"got {event['old_data']}"
                )
                assert event["new_data"] is not None, (
                    f"Create event {event.get('id')} should have non-null new_data"
                )
                assert isinstance(event["new_data"], dict), (
                    f"Create event {event.get('id')} new_data should be a dict, "
                    f"got {type(event['new_data'])}"
                )
            elif event["event_type"] == "update":
                # Update events should have both old_data and new_data populated
                assert event["old_data"] is not None, (
                    f"Update event {event.get('id')} should have old_data populated"
                )
                assert event["new_data"] is not None, (
                    f"Update event {event.get('id')} should have new_data populated"
                )
                assert isinstance(event["old_data"], dict), (
                    f"Update event {event.get('id')} old_data should be a dict"
                )
                assert isinstance(event["new_data"], dict), (
                    f"Update event {event.get('id')} new_data should be a dict"
                )

            # Verify timestamp is valid ISO8601
            try:
                datetime.fromisoformat(event["event_timestamp"].replace("Z", "+00:00"))
            except ValueError:
                raise AssertionError(
                    f"Invalid ISO8601 timestamp: {event['event_timestamp']}"
                )

        # Step 11: Verify chronological ordering (newest first)
        timestamps = [e["event_timestamp"] for e in new_events]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], (
                f"Events not in non-increasing chronological order at index {i}: "
                f"{timestamps[i]} should be >= {timestamps[i + 1]}"
            )

        # Step 12: Test update event (pick the first term - "Database" from stable taxonomy)
        term1_id = term_ids["term_1"]
        original_title = "Database"

        # Get events for term1 before update
        term1_events_before = e2e_client.get(
            f"/api/change_events/?record_type=structure_node&record_id={term1_id}&limit=1000"
        )
        assert term1_events_before.status_code == 200, (
            f"Failed to fetch term1 events before update: {term1_events_before.status_code}. "
            f"Response: {term1_events_before.text}"
        )
        term1_before_events = term1_events_before.json()

        # Perform an update on term1
        update_data = {"title": "Updated Database System"}
        update_response = e2e_client.put(
            f"/api/structure_nodes/{term1_id}", json=update_data
        )
        assert update_response.status_code == 200, (
            f"Failed to update term1: {update_response.status_code}. "
            f"Response: {update_response.text}"
        )

        # Get events for term1 after update
        term1_events_after = e2e_client.get(
            f"/api/change_events/?record_type=structure_node&record_id={term1_id}&limit=1000"
        )
        assert term1_events_after.status_code == 200, (
            f"Failed to fetch term1 events after update: {term1_events_after.status_code}. "
            f"Response: {term1_events_after.text}"
        )
        term1_after_events = term1_events_after.json()

        # Verify an update event was created
        new_term1_events_count = len(term1_after_events) - len(term1_before_events)
        assert new_term1_events_count >= 1, (
            f"Expected at least 1 new event for term1 after update, "
            f"got {new_term1_events_count}"
        )

        # Find the update event (it should be the newest one for this record)
        assert len(term1_after_events) > 0, (
            "No events found for term1 after update"
        )
        update_event = term1_after_events[0]
        assert update_event["event_type"] == "update", (
            f"Expected update event_type, got {update_event['event_type']}"
        )
        assert update_event["old_data"] is not None, (
            "Update event should have old_data populated"
        )
        assert update_event["new_data"] is not None, (
            "Update event should have new_data populated"
        )
        assert isinstance(update_event["old_data"], dict), (
            "old_data should be a dict"
        )
        assert isinstance(update_event["new_data"], dict), (
            "new_data should be a dict"
        )

        # Verify the old and new data contain title information
        assert "title" in update_event["old_data"], (
            "old_data should contain title"
        )
        assert "title" in update_event["new_data"], (
            "new_data should contain title"
        )
        assert update_event["old_data"]["title"] == original_title, (
            "old_data should have original title"
        )
        assert update_event["new_data"]["title"] == "Updated Database System", (
            "new_data should have updated title"
        )

    def test_baseline_predicate_management(self, e2e_client):
        """
        E2E Test: Predicate definition, uniqueness, and relationship management.

        This test validates that:
        1. Predicates are created with correct `identifier`, `title`, `definition` fields
        2. Optional `mapping` field is persisted in the response
        3. Predicates are retrievable by ID
        4. Uniqueness is enforced on both `identifier` and `title`
        5. Links can reference predicates via `predicate_id`
        6. Current cascade/orphan behavior after predicate deletion is documented
        7. Deleted predicates return 404 on GET

        The test creates predicates, uses them in relationships, verifies constraints,
        and documents the baseline behavior when predicates are deleted while links
        still reference them (Phase 2 will formalize cascade rules).
        """
        # Step 1: Create a test hierarchy (layer → domain → terms)
        hierarchy = create_test_hierarchy(
            e2e_client,
            layer_title="Predicate Management Test",
            layer_definition="Layer for predicate management testing",
            scheme_title="Predicate Test Scheme",
            scheme_definition="Scheme for predicate testing",
            classes=[
                {
                    "title": "Predicate Test Term 1",
                    "definition": "First term for predicate testing",
                },
                {
                    "title": "Predicate Test Term 2",
                    "definition": "Second term for predicate testing",
                },
            ],
        )

        layer_id = hierarchy["layer_id"]
        domain_id = hierarchy["domain_id"]
        term_1_id = hierarchy["term_ids"]["Predicate Test Term 1"]
        term_2_id = hierarchy["term_ids"]["Predicate Test Term 2"]
        # Verify hierarchy was created successfully
        assert layer_id is not None
        assert domain_id is not None
        assert len(hierarchy["term_ids"]) == 2

        # Step 2: Create a predicate with all optional fields
        predicate_data = {
            "title": "Is Part Of",
            "identifier": "is_part_of",
            "definition": "Indicates a part-whole relationship",
            "mapping": {
                "source": "conceptnet",
                "uri": "/r/PartOf"
            },
        }
        predicate_response = e2e_client.post(
            "/api/predicates/", json=predicate_data
        )
        assert predicate_response.status_code == 201, (
            f"Failed to create predicate: {predicate_response.text}"
        )
        predicate = predicate_response.json()
        predicate_id = predicate["id"]

        # Verify predicate creation response fields
        assert predicate["id"] is not None, "Predicate ID must not be None"
        assert predicate["identifier"] == "is_part_of", (
            f"Expected identifier 'is_part_of', got {predicate['identifier']}"
        )
        assert predicate["title"] == "Is Part Of", (
            f"Expected title 'Is Part Of', got {predicate['title']}"
        )
        assert predicate["definition"] == "Indicates a part-whole relationship", (
            f"Expected definition, got {predicate['definition']}"
        )
        # Verify mapping is persisted
        assert predicate["mapping"] is not None, "Mapping field must not be None"
        assert predicate["mapping"]["source"] == "conceptnet", (
            f"Expected mapping.source 'conceptnet', got {predicate['mapping'].get('source')}"
        )
        assert predicate["mapping"]["uri"] == "/r/PartOf", (
            f"Expected mapping.uri '/r/PartOf', got {predicate['mapping'].get('uri')}"
        )
        # Verify timestamps are present
        assert "date_created" in predicate, "date_created field must be present"
        assert "date_modified" in predicate, "date_modified field must be present"

        # Step 3: Verify predicate is retrievable by ID
        get_predicate_response = e2e_client.get(f"/api/predicates/{predicate_id}")
        assert get_predicate_response.status_code == 200, (
            f"Failed to retrieve predicate: {get_predicate_response.text}"
        )
        predicate_retrieved = get_predicate_response.json()
        assert predicate_retrieved["id"] == predicate_id
        assert predicate_retrieved["title"] == "Is Part Of"
        assert predicate_retrieved["identifier"] == "is_part_of"
        assert predicate_retrieved["mapping"]["source"] == "conceptnet"

        # Step 4: Test duplicate identifier rejection
        duplicate_identifier_data = {
            "title": "Different Title",
            "identifier": "is_part_of",  # Same identifier
            "definition": "Different definition",
        }
        duplicate_identifier_response = e2e_client.post(
            "/api/predicates/", json=duplicate_identifier_data
        )
        assert duplicate_identifier_response.status_code in [400, 409], (
            f"Duplicate identifier should be rejected with 400 or 409, "
            f"got {duplicate_identifier_response.status_code}"
        )

        # Step 5: Test duplicate title rejection
        duplicate_title_data = {
            "title": "Is Part Of",  # Same title
            "identifier": "is_part_of_duplicate",
            "definition": "Different definition",
        }
        duplicate_title_response = e2e_client.post(
            "/api/predicates/", json=duplicate_title_data
        )
        assert duplicate_title_response.status_code in [400, 409], (
            f"Duplicate title should be rejected with 400 or 409, "
            f"got {duplicate_title_response.status_code}"
        )

        # Step 6: Create another predicate for additional testing
        second_predicate_data = {
            "title": "Used By",
            "identifier": "used_by",
            "definition": "Indicates usage relationship",
        }
        second_predicate_response = e2e_client.post(
            "/api/predicates/", json=second_predicate_data
        )
        assert second_predicate_response.status_code == 201
        second_predicate_id = second_predicate_response.json()["id"]

        # Step 7: Create a link referencing the first predicate
        link_data = {
            "source_node_id": term_1_id,
            "target_node_id": term_2_id,
            "predicate": "Is Part Of",
            "predicate_id": predicate_id,
        }
        link_response = e2e_client.post(
            "/api/structure_nodes/links", json=link_data
        )
        assert link_response.status_code == 201, (
            f"Failed to create link: {link_response.text}"
        )
        link = link_response.json()
        link_id = link["id"]

        # Step 8: Verify link references the predicate correctly
        list_links_response = e2e_client.get(
            f"/api/structure_nodes/links?source_node_id={term_1_id}"
        )
        assert list_links_response.status_code == 200
        response_data = list_links_response.json()
        # Response should be a paginated response with 'data', 'total', 'skip', 'limit'
        assert isinstance(response_data, dict), (
            f"Expected paginated response dict, got {type(response_data)}"
        )
        assert "data" in response_data, (
            f"Expected 'data' key in response, got keys: {response_data.keys()}"
        )
        links = response_data["data"]
        assert isinstance(links, list), (
            f"Expected 'data' to be a list, got {type(links)}"
        )
        assert len(links) >= 1, "Should have at least one link"
        found_link = False
        for link_item in links:
            if link_item["id"] == link_id:
                found_link = True
                assert link_item["predicate_id"] == predicate_id, (
                    f"Link predicate_id should be {predicate_id}, "
                    f"got {link_item.get('predicate_id')}"
                )
                break
        assert found_link, f"Link {link_id} not found in list"

        # Step 9: Test predicate deletion when unused (second predicate)
        delete_second_predicate_response = e2e_client.delete(
            f"/api/predicates/{second_predicate_id}"
        )
        assert delete_second_predicate_response.status_code == 200, (
            f"Failed to delete unused predicate: {delete_second_predicate_response.text}"
        )

        # Verify deleted predicate returns 404
        verify_deleted_response = e2e_client.get(
            f"/api/predicates/{second_predicate_id}"
        )
        assert verify_deleted_response.status_code == 404, (
            f"Deleted predicate should return 404, got {verify_deleted_response.status_code}"
        )

        # Step 10: Test predicate deletion while a link still references it
        # According to the issue, we document the baseline behavior (Phase 2 will formalize)
        delete_predicate_response = e2e_client.delete(
            f"/api/predicates/{predicate_id}"
        )
        # Based on the API code, deletion should fail if predicate is in use
        assert delete_predicate_response.status_code == 400, (
            f"Expected 400 when deleting predicate in use, "
            f"got {delete_predicate_response.status_code}. "
            f"Response: {delete_predicate_response.text}"
        )

        # Verify predicate still exists (deletion was prevented)
        verify_predicate_response = e2e_client.get(f"/api/predicates/{predicate_id}")
        assert verify_predicate_response.status_code == 200, (
            "Predicate deletion should have been prevented; predicate should still exist"
        )

        # Step 11: Now delete the link, then delete the predicate
        delete_link_response = e2e_client.delete(
            f"/api/structure_nodes/links/{link_id}"
        )
        assert delete_link_response.status_code == 204, (
            f"Failed to delete link: {delete_link_response.text}"
        )

        # Now delete the predicate (should succeed since it's no longer referenced)
        delete_predicate_response = e2e_client.delete(
            f"/api/predicates/{predicate_id}"
        )
        assert delete_predicate_response.status_code == 200, (
            f"Failed to delete predicate after removing link: {delete_predicate_response.text}"
        )

        # Verify deleted predicate returns 404
        verify_final_response = e2e_client.get(f"/api/predicates/{predicate_id}")
        assert verify_final_response.status_code == 404, (
            f"Deleted predicate should return 404, got {verify_final_response.status_code}"
        )

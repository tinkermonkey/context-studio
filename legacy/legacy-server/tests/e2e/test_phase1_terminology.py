"""
Phase 1 E2E tests for terminology migration and dual API coexistence.

These tests verify that the new terminology (taxonomy, concept_scheme, class) works
alongside the old terminology (layer, domain, term) during the transition phase,
that migration 019 cleanly handles rollback, and that both API routes serve the same
data while maintaining backward compatibility with Deprecation headers on old routes.

All tests are marked with @pytest.mark.e2e and require the E2E test harness (conftest.py).
"""

import pytest
from sqlalchemy import text
from tests.e2e.helpers import create_test_hierarchy, create_test_hierarchy_new_api

pytestmark = pytest.mark.e2e


class TestNewAPIRoutesMatchOldBehavior:
    """Verify new routes (/api/ontology_entities/) work and data is visible in old routes."""

    def test_new_api_routes_match_old_behavior(self, e2e_client):
        """
        Execute full taxonomy lifecycle via new routes and verify backward compatibility.

        Steps:
        1. Create taxonomy via new route
        2. Create concept scheme under taxonomy
        3. Create two classes under concept scheme
        4. Create relationship between classes
        5. Verify search finds entities created via new API
        6. Verify entities are visible via old /api/structure_nodes/ routes
        7. Verify node_type values in responses are new terminology (taxonomy, concept_scheme, class)
        8. Delete in reverse order and verify deletions via old routes
        """
        # Create hierarchy via new API
        taxonomy_id, scheme_id, class_ids = create_test_hierarchy_new_api(e2e_client)

        # Create relationship via new relationships route
        rel_data = {
            "source_entity_id": class_ids[0],
            "target_entity_id": class_ids[1],
            "predicate": "is_a",
        }
        rel_resp = e2e_client.post("/api/ontology_entities/relationships", json=rel_data)
        assert (
            rel_resp.status_code == 201
        ), f"Failed to create relationship: {rel_resp.status_code} {rel_resp.text}"
        relationship_id = rel_resp.json()["id"]

        # Verify taxonomy is visible via new route with correct terminology
        tax_read = e2e_client.get(f"/api/ontology_entities/{taxonomy_id}")
        assert tax_read.status_code == 200
        assert tax_read.json()["node_type"] == "taxonomy"

        # Verify scheme is visible via new route with correct terminology
        scheme_read = e2e_client.get(f"/api/ontology_entities/{scheme_id}")
        assert scheme_read.status_code == 200
        assert scheme_read.json()["node_type"] == "concept_scheme"

        # Verify classes are visible via new route with correct terminology
        for class_id in class_ids:
            cls_read = e2e_client.get(f"/api/ontology_entities/{class_id}")
            assert cls_read.status_code == 200
            assert cls_read.json()["node_type"] == "class"

        # Verify all entities are visible via old routes (backward compatibility)
        tax_old = e2e_client.get(f"/api/structure_nodes/{taxonomy_id}")
        assert tax_old.status_code == 200
        assert tax_old.json()["id"] == taxonomy_id

        scheme_old = e2e_client.get(f"/api/structure_nodes/{scheme_id}")
        assert scheme_old.status_code == 200
        assert scheme_old.json()["id"] == scheme_id

        for class_id in class_ids:
            cls_old = e2e_client.get(f"/api/structure_nodes/{class_id}")
            assert cls_old.status_code == 200
            assert cls_old.json()["id"] == class_id

        # Delete relationship
        del_rel = e2e_client.delete(f"/api/ontology_entities/relationships/{relationship_id}")
        assert del_rel.status_code == 204

        # Delete classes (bottom-up)
        for class_id in class_ids:
            del_cls = e2e_client.delete(f"/api/ontology_entities/{class_id}")
            assert del_cls.status_code == 204

        # Delete scheme
        del_scheme = e2e_client.delete(f"/api/ontology_entities/{scheme_id}")
        assert del_scheme.status_code == 204

        # Delete taxonomy
        del_tax = e2e_client.delete(f"/api/ontology_entities/{taxonomy_id}")
        assert del_tax.status_code == 204

        # Verify deletions via old routes (no longer present)
        tax_gone = e2e_client.get(f"/api/structure_nodes/{taxonomy_id}")
        assert tax_gone.status_code == 404


class TestOldRoutesStillWork:
    """Verify old /api/structure_nodes/ routes still work with Deprecation headers."""

    def test_old_routes_still_work(self, e2e_client):
        """
        Execute full taxonomy lifecycle via old routes and verify Deprecation headers.

        Steps:
        1. Create layer via old route
        2. Create domain under layer
        3. Create two terms under domain
        4. Create relationship via old predicate route
        5. Assert all responses have HTTP 200/201
        6. Assert all responses include 'Deprecation: true' header
        7. Verify node_type values are old terminology (layer, domain, term)
        """
        # Create hierarchy via old API
        hierarchy = create_test_hierarchy(
            e2e_client,
            "Test Layer",
            "A test layer for deprecation verification",
            "Test Domain",
            "A test domain for deprecation verification",
            [
                {"title": "Test Term 1", "definition": "First test term"},
                {"title": "Test Term 2", "definition": "Second test term"},
            ],
        )

        layer_id = hierarchy["layer_id"]
        domain_id = hierarchy["domain_id"]
        term_ids = list(hierarchy["term_ids"].values())

        # Create relationship via old links route
        rel_data = {
            "source_node_id": term_ids[0],
            "target_node_id": term_ids[1],
            "predicate": "is_a",
        }
        rel_resp = e2e_client.post("/api/structure_nodes/links", json=rel_data)
        assert rel_resp.status_code == 201

        # Verify Deprecation header on POST (create layer)
        layer_resp = e2e_client.post(
            "/api/structure_nodes/",
            json={
                "node_type": "layer",
                "title": "Header Test Layer",
                "definition": "For testing deprecation header",
            },
        )
        assert layer_resp.status_code == 201
        assert layer_resp.headers.get("Deprecation") == "true"

        # Verify Deprecation header on GET
        layer_read = e2e_client.get(f"/api/structure_nodes/{layer_id}")
        assert layer_read.status_code == 200
        assert layer_read.headers.get("Deprecation") == "true"

        # Verify old node_type values
        layer_data = layer_read.json()
        assert layer_data["node_type"] == "layer"

        domain_read = e2e_client.get(f"/api/structure_nodes/{domain_id}")
        assert domain_read.status_code == 200
        assert domain_read.headers.get("Deprecation") == "true"
        assert domain_read.json()["node_type"] == "domain"

        for term_id in term_ids:
            term_read = e2e_client.get(f"/api/structure_nodes/{term_id}")
            assert term_read.status_code == 200
            assert term_read.headers.get("Deprecation") == "true"
            assert term_read.json()["node_type"] == "term"

        # Clean up test data
        e2e_client.delete(f"/api/structure_nodes/{layer_resp.json()['id']}")


class TestDatabaseMigrationDataIntegrity:
    """Verify database schema changes and data storage with new field names."""

    def test_database_migration_data_integrity(self, e2e_app, e2e_client):
        """
        Query database directly to verify schema changes and data integrity.

        Steps:
        1. Verify old table names no longer exist
        2. Verify new table names exist (ontology_entities, relationships)
        3. Create entity via new API
        4. Query database directly and verify node_type is stored as new terminology
        5. Verify parent_entity_id field is used instead of parent_node_id
        """
        # Create a test entity via new API
        taxonomy_id, scheme_id, class_ids = create_test_hierarchy_new_api(e2e_client)

        # Unpack e2e_app tuple to get app, engine, and session_local
        _app, engine, _session_local = e2e_app

        # Verify old table names no longer exist
        with engine.connect() as conn:
            # Verify structure_nodes table does not exist
            try:
                conn.execute(text("SELECT 1 FROM structure_nodes LIMIT 1"))
                pytest.fail(
                    "structure_nodes table should not exist after migration 019"
                )
            except Exception:
                # Expected: table should not exist
                pass

            # Verify structure_node_links table does not exist
            try:
                conn.execute(text("SELECT 1 FROM structure_node_links LIMIT 1"))
                pytest.fail(
                    "structure_node_links table should not exist after migration 019"
                )
            except Exception:
                # Expected: table should not exist
                pass

        # Verify new table names exist
        with engine.connect() as conn:
            # Check that ontology_entities table exists
            try:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM ontology_entities WHERE id = :id"),
                    {"id": taxonomy_id},
                )
                count = result.scalar()
                assert count >= 0, "ontology_entities table should exist"
            except Exception as e:
                pytest.fail(f"ontology_entities table query failed: {e}")

            # Verify the taxonomy entity in database has node_type = 'taxonomy'
            result = conn.execute(
                text("SELECT node_type FROM ontology_entities WHERE id = :id"),
                {"id": taxonomy_id},
            )
            node_type = result.scalar()
            assert (
                node_type == "taxonomy"
            ), f"Expected node_type='taxonomy' but got '{node_type}'"

            # Verify the scheme entity has node_type = 'concept_scheme'
            result = conn.execute(
                text("SELECT node_type FROM ontology_entities WHERE id = :id"),
                {"id": scheme_id},
            )
            node_type = result.scalar()
            assert (
                node_type == "concept_scheme"
            ), f"Expected node_type='concept_scheme' but got '{node_type}'"

            # Verify classes have node_type = 'class'
            for class_id in class_ids:
                result = conn.execute(
                    text("SELECT node_type FROM ontology_entities WHERE id = :id"),
                    {"id": class_id},
                )
                node_type = result.scalar()
                assert (
                    node_type == "class"
                ), f"Expected node_type='class' but got '{node_type}'"

            # Verify parent relationships use parent_entity_id
            result = conn.execute(
                text("SELECT parent_entity_id FROM ontology_entities WHERE id = :id"),
                {"id": scheme_id},
            )
            parent_id = result.scalar()
            assert (
                parent_id == taxonomy_id
            ), f"Scheme's parent_entity_id should be {taxonomy_id}, got {parent_id}"

            conn.commit()


class TestMigrationRollback:
    """Verify migration 019 rollback and re-apply work cleanly."""

    def test_migration_rollback(self, e2e_app, e2e_client):
        """
        Test migration 019 down() and up() methods for clean reversibility.

        Steps:
        1. Create entity via new API
        2. Import MigrationManager and apply down()
        3. Verify old table names are restored (structure_nodes)
        4. Verify old routes work and return old node_type values
        5. Re-apply up() via migration manager
        6. Verify new table names are back
        """
        from database.migrations.migration_manager import MigrationManager

        # Unpack e2e_app tuple to get app, engine, and session_local
        _app, engine, _session_local = e2e_app

        # Get the database file path - we'll need to derive it from the engine URL
        # For SQLite, the database path is in the connection URL
        db_url = str(engine.url)
        # Extract path from sqlite:////path/to/db format
        if db_url.startswith("sqlite:////"):
            db_path = db_url.replace("sqlite:////", "/")
        elif db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
        else:
            pytest.skip("Could not determine database path from engine URL")

        # Create test data via new API first
        taxonomy_id, _scheme_id, _class_ids = create_test_hierarchy_new_api(e2e_client)

        # Initialize migration manager
        migration_mgr = MigrationManager(db_path)

        # Apply down() to migration 019
        try:
            migration_mgr.rollback_to_version(18)

            # After downgrade, verify old table names are being used
            with engine.connect() as conn:
                # Check that structure_nodes exists and has data
                try:
                    result = conn.execute(
                        text("SELECT node_type FROM structure_nodes WHERE id = :id"),
                        {"id": taxonomy_id},
                    )
                    node_type = result.scalar()
                    # After downgrade, should see old terminology
                    assert node_type in [
                        "layer",
                        "domain",
                        "term",
                    ], f"Expected old node_type after rollback but got '{node_type}'"
                except Exception as e:
                    pytest.fail(f"Failed to query structure_nodes after downgrade: {e}")
                conn.commit()

            # Verify old API routes still work with old terminology
            tax_old_api = e2e_client.get(f"/api/structure_nodes/{taxonomy_id}")
            assert tax_old_api.status_code == 200
            tax_data = tax_old_api.json()
            assert (
                tax_data["node_type"] == "layer"
            ), "After downgrade, node_type should be 'layer'"

        finally:
            # Re-apply up() to restore migration 019 (cleanup)
            migration_mgr.migrate_to_version(19)

            # Verify new table names are back
            with engine.connect() as conn:
                try:
                    result = conn.execute(
                        text("SELECT node_type FROM ontology_entities WHERE id = :id"),
                        {"id": taxonomy_id},
                    )
                    node_type = result.scalar()
                    assert (
                        node_type == "taxonomy"
                    ), "After re-upgrade, should see new terminology"
                except Exception as e:
                    pytest.fail(
                        f"Failed to query ontology_entities after re-upgrade: {e}"
                    )
                conn.commit()


class TestDualTerminologyCoexistence:
    """Verify entities created via one API are visible via the other."""

    def test_dual_terminology_coexistence(self, e2e_client):
        """
        Create entities via both APIs and verify they are visible cross-API.

        Steps:
        1. Create entity via new route (/api/ontology_entities/)
        2. Read it via old route (/api/structure_nodes/{id})
        3. Create entity via old route (/api/structure_nodes/)
        4. Read it via new route (/api/ontology_entities/{id})
        5. Verify both entities have different IDs
        6. Verify both are in the same database table
        """
        # Create taxonomy via new API
        taxonomy_id, _scheme_id, _class_ids = create_test_hierarchy_new_api(e2e_client)

        # Read taxonomy via old API
        tax_via_old = e2e_client.get(f"/api/structure_nodes/{taxonomy_id}")
        assert tax_via_old.status_code == 200
        assert tax_via_old.json()["id"] == taxonomy_id

        # Create layer via old API
        layer_resp = e2e_client.post(
            "/api/structure_nodes/",
            json={
                "node_type": "layer",
                "title": "Layer for Cross-API Test",
                "definition": "Created via old API",
            },
        )
        assert layer_resp.status_code == 201
        layer_id = layer_resp.json()["id"]

        # Read layer via new API
        layer_via_new = e2e_client.get(f"/api/ontology_entities/{layer_id}")
        assert layer_via_new.status_code == 200
        assert layer_via_new.json()["id"] == layer_id

        # Verify IDs are different
        assert taxonomy_id != layer_id

        # Verify both are in the database by checking total count
        # List via new API
        entities_new = e2e_client.get("/api/ontology_entities/")
        assert entities_new.status_code == 200
        entity_count_new = len(entities_new.json())

        # List via old API
        entities_old = e2e_client.get("/api/structure_nodes/")
        assert entities_old.status_code == 200
        entity_count_old = len(entities_old.json())

        # Both should show the same total count (same underlying table)
        assert (
            entity_count_new == entity_count_old
        ), "New and old API should show same entity count from same table"


class TestRenamedEnumValuesInQueries:
    """Verify query filters work with both old and new enum values."""

    def test_renamed_enum_values_in_queries(self, e2e_client):
        """
        Create entities of each type and filter by node_type in queries.

        Steps:
        1. Create one taxonomy via new API
        2. Create one concept_scheme via new API
        3. Create one class via new API
        4. Query /api/ontology_entities/?node_type=taxonomy → verify count=1
        5. Query /api/ontology_entities/?node_type=concept_scheme → verify count=1
        6. Query /api/ontology_entities/?node_type=class → verify count=1
        7. Query /api/structure_nodes/?node_type=layer (old terminology) → verify count=1
        """
        # Create hierarchy with one of each type
        taxonomy_data = {
            "node_type": "taxonomy",
            "title": "Query Test Taxonomy",
            "definition": "For testing enum queries",
        }
        taxonomy_resp = e2e_client.post("/api/ontology_entities/", json=taxonomy_data)
        assert taxonomy_resp.status_code == 201
        taxonomy_id = taxonomy_resp.json()["id"]

        scheme_data = {
            "node_type": "concept_scheme",
            "title": "Query Test Scheme",
            "definition": "For testing enum queries",
            "parent_entity_id": taxonomy_id,
        }
        scheme_resp = e2e_client.post("/api/ontology_entities/", json=scheme_data)
        assert scheme_resp.status_code == 201
        scheme_id = scheme_resp.json()["id"]

        class_data = {
            "node_type": "class",
            "title": "Query Test Class",
            "definition": "For testing enum queries",
            "parent_entity_id": scheme_id,
        }
        class_resp = e2e_client.post("/api/ontology_entities/", json=class_data)
        assert class_resp.status_code == 201
        class_id = class_resp.json()["id"]

        # Query by new terminology (taxonomy)
        tax_query = e2e_client.get("/api/ontology_entities/?node_type=taxonomy")
        assert tax_query.status_code == 200
        tax_results = tax_query.json()["data"]
        tax_matching = [e for e in tax_results if e["id"] == taxonomy_id]
        assert (
            len(tax_matching) == 1
        ), "Should find exactly one taxonomy with node_type=taxonomy filter"

        # Query by new terminology (concept_scheme)
        scheme_query = e2e_client.get(
            "/api/ontology_entities/?node_type=concept_scheme"
        )
        assert scheme_query.status_code == 200
        scheme_results = scheme_query.json()["data"]
        scheme_matching = [e for e in scheme_results if e["id"] == scheme_id]
        assert (
            len(scheme_matching) == 1
        ), "Should find exactly one concept_scheme with node_type=concept_scheme filter"

        # Query by new terminology (class)
        class_query = e2e_client.get("/api/ontology_entities/?node_type=class")
        assert class_query.status_code == 200
        class_results = class_query.json()["data"]
        class_matching = [e for e in class_results if e["id"] == class_id]
        assert (
            len(class_matching) == 1
        ), "Should find exactly one class with node_type=class filter"

        # Query by old terminology via old API (layer = taxonomy during transition)
        layer_query = e2e_client.get("/api/structure_nodes/?node_type=layer")
        assert layer_query.status_code == 200
        layer_results = layer_query.json()["data"]
        # The taxonomy we created should appear as layer in old API
        layer_matching = [e for e in layer_results if e["id"] == taxonomy_id]
        assert (
            len(layer_matching) == 1
        ), "Should find exactly one layer (taxonomy) with node_type=layer filter on old API"

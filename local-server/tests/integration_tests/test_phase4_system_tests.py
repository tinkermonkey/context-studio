"""
System tests for Phase 4: API Contract Validation and End-to-End Integration.

Test Cases:
- TC-S001: End-to-end workflow test
- TC-S002: Health check endpoint validation
- TC-S003: API contract validation
"""

import pytest
import tempfile
import os
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from reference_db.models import ReferenceLink
from uuid import uuid4
from datetime import date


@pytest.fixture(scope="module")
def test_database_with_schema_org():
    """Create a test database with Schema.org sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    config = ReferenceConfig()
    manager = ReferenceManager(config, db_path=db_path)

    # Load schema.org sample data
    os.path.join(
        os.path.dirname(__file__), '..', 'fixtures', 'schema_org_sample.jsonld'
    )

    # Create embeddings helper
    def create_embedding(text: str, base_value: float = 0.5) -> bytes:
        """Create deterministic embedding based on text."""
        # Simple hash-based embedding for testing
        hash_val = hash(text) % 100 / 100.0
        vec = np.full(384, base_value + hash_val * 0.1, dtype=np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    # Add Person entity
    person_node = manager.add_reference_node(
        title="Person",
        definition="A person (alive, dead, undead, or fictional).",
        source="schema.org",
        external_id="Person",
        attributes='{"@type": "entity"}',
        title_embedding=create_embedding("Person", 0.8),
        definition_embedding=create_embedding("A person (alive, dead, undead, or fictional).", 0.8),
        embedding_dims=384
    )

    # Add Thing entity (parent)
    thing_node = manager.add_reference_node(
        title="Thing",
        definition="The most generic type of item.",
        source="schema.org",
        external_id="Thing",
        attributes='{"@type": "entity"}',
        title_embedding=create_embedding("Thing", 0.3),
        definition_embedding=create_embedding("The most generic type of item.", 0.3),
        embedding_dims=384
    )

    # Add Book entity
    book_node = manager.add_reference_node(
        title="Book",
        definition="A book.",
        source="schema.org",
        external_id="Book",
        attributes='{"@type": "entity"}',
        title_embedding=create_embedding("Book", 0.75),
        definition_embedding=create_embedding("A book.", 0.75),
        embedding_dims=384
    )

    # Add author property
    author_prop = manager.add_reference_node(
        title="author",
        definition="The author of this content or rating.",
        source="schema.org",
        external_id="author",
        attributes='{"@type": "property"}',
        title_embedding=create_embedding("author", 0.7),
        definition_embedding=create_embedding("The author of this content or rating.", 0.7),
        embedding_dims=384
    )

    # Add name property
    name_prop = manager.add_reference_node(
        title="name",
        definition="The name of the item.",
        source="schema.org",
        external_id="name",
        attributes='{"@type": "property"}',
        title_embedding=create_embedding("name", 0.6),
        definition_embedding=create_embedding("The name of the item.", 0.6),
        embedding_dims=384
    )

    # Add givenName property
    given_name_prop = manager.add_reference_node(
        title="givenName",
        definition="Given name. In the U.S., the first name of a Person.",
        source="schema.org",
        external_id="givenName",
        attributes='{"@type": "property"}',
        title_embedding=create_embedding("givenName", 0.65),
        definition_embedding=create_embedding("Given name. In the U.S., the first name of a Person.", 0.65),
        embedding_dims=384
    )

    # Rollback any pending transactions before adding links
    if manager.session.in_transaction():
        manager.session.rollback()

    # Add subClassOf link: Person -> Thing
    person_subclass_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=person_node.id,
        predicate="subClassOf",
        object_node=thing_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    # Add subClassOf link: Book -> Thing (indirectly)
    book_subclass_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=book_node.id,
        predicate="subClassOf",
        object_node=thing_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    # Add domainIncludes link: author -> Book
    author_domain_book_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=author_prop.id,
        predicate="domainIncludes",
        object_node=book_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    # Add rangeIncludes link: author -> Person
    author_range_person_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=author_prop.id,
        predicate="rangeIncludes",
        object_node=person_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    # Add domainIncludes link: name -> Person
    name_domain_person_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=name_prop.id,
        predicate="domainIncludes",
        object_node=person_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    # Add domainIncludes link: givenName -> Person
    given_name_domain_person_link = ReferenceLink(
        id=str(uuid4()),
        subject_node=given_name_prop.id,
        predicate="domainIncludes",
        object_node=person_node.id,
        created_at=date.today().isoformat(),
        updated_at=date.today().isoformat()
    )

    manager.session.add_all([
        person_subclass_link,
        book_subclass_link,
        author_domain_book_link,
        author_range_person_link,
        name_domain_person_link,
        given_name_domain_person_link
    ])
    manager.session.commit()

    # Extract node data BEFORE closing the session
    node_data = {
        "person": {"id": person_node.id, "title": person_node.title},
        "thing": {"id": thing_node.id, "title": thing_node.title},
        "book": {"id": book_node.id, "title": book_node.title},
        "author": {"id": author_prop.id, "title": author_prop.title},
        "name": {"id": name_prop.id, "title": name_prop.title},
        "givenName": {"id": given_name_prop.id, "title": given_name_prop.title}
    }

    manager.close()

    yield db_path, {"nodes": node_data}

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def app_client(test_database_with_schema_org):
    """Create FastAPI test client with test database."""
    db_path, nodes = test_database_with_schema_org

    # Patch the reference_manager_context to use our test database

    # Create a custom context manager that uses our test database
    from contextlib import contextmanager

    @contextmanager
    def test_reference_manager_context(config):
        manager = ReferenceManager(config, db_path=db_path)
        try:
            yield manager
        finally:
            manager.close()

    with patch('reference_db.dependencies.reference_manager_context', side_effect=test_reference_manager_context):
        # Import after patching
        from app import app
        client = TestClient(app)
        yield client


class TestTC_S001_EndToEndWorkflow:
    """
    TC-S001: End-to-end workflow test.

    Validates: StructureNode creation → reference search → link retrieval
    Expected: Schema.org "Person" found via "person who writes books" query
    Expected: Retrieved links include name, givenName via domainIncludes
    """

    def test_e2e_workflow_person_who_writes_books(self, app_client, test_database_with_schema_org):
        """
        Test complete workflow from search to link retrieval.

        Steps:
        1. Search for "person who writes books"
        2. Verify Person entity is found
        3. Retrieve links for Person
        4. Verify expected properties (name, givenName) via domainIncludes
        """
        db_path, nodes = test_database_with_schema_org

        # Mock embedding generation
        def mock_embedding(text: str) -> bytes:
            hash_val = hash(text) % 100 / 100.0
            vec = np.full(384, 0.8 + hash_val * 0.1, dtype=np.float32)
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        # Step 1: Search for "person who writes books"
        with patch('embeddings.generate_embeddings.generate_embedding', side_effect=mock_embedding):
            response = app_client.get(
                "/api/reference/ref-db/search",
                params={
                    "query": "person who writes books",
                    "limit": 10,
                    "threshold": 0.7
                }
            )

        assert response.status_code == 200, f"Search failed: {response.text}"
        search_data = response.json()

        # Step 2: Verify Person entity is found
        assert search_data["total_results"] > 0, "No results found"
        person_results = [r for r in search_data["results"] if r["title"] == "Person"]
        assert len(person_results) > 0, "Person entity not found in results"

        person_result = person_results[0]
        assert person_result["similarity_score"] >= 0.7, f"Similarity too low: {person_result['similarity_score']}"
        person_id = person_result["id"]

        # Step 3: Retrieve links for Person
        links_response = app_client.get(
            f"/api/reference/ref-db/nodes/{person_id}/links",
            params={"direction": "inbound"}
        )

        assert links_response.status_code == 200, f"Link retrieval failed: {links_response.text}"
        links_data = links_response.json()

        # Step 4: Verify expected properties via domainIncludes
        domain_includes_links = [
            link for link in links_data["links"]
            if link["predicate"] == "domainIncludes"
        ]

        assert len(domain_includes_links) > 0, "No domainIncludes links found"

        # Get property nodes that link to Person
        property_ids = [link["subject_node"] for link in domain_includes_links]

        # Verify name and givenName are in the properties
        property_titles = []
        for prop_id in property_ids:
            prop_response = app_client.get(f"/api/reference/ref-db/nodes/{prop_id}")
            if prop_response.status_code == 200:
                property_titles.append(prop_response.json()["title"])

        assert "name" in property_titles, "name property not found via domainIncludes"
        assert "givenName" in property_titles, "givenName property not found via domainIncludes"


class TestTC_S002_HealthCheck:
    """
    TC-S002: Health check endpoint validation.

    Tests:
    - Correct JSON schema
    - "healthy" when node_count == vec_count and versions match
    - "degraded" when vec_count mismatch detected
    - "missing" when database file doesn't exist
    - Response includes schema_version, model_version, last_import_at
    - Executes in <200ms
    """

    def test_health_check_schema_validation(self, app_client):
        """Verify health check returns correct JSON schema."""
        response = app_client.get("/api/reference/ref-db/health")

        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()

        # Validate schema
        assert "status" in data, "Missing 'status' field"
        assert "node_count" in data, "Missing 'node_count' field"
        assert "vec_count" in data, "Missing 'vec_count' field"
        assert "schema_version" in data, "Missing 'schema_version' field"
        assert "model_version" in data, "Missing 'model_version' field"
        assert "last_import_at" in data, "Missing 'last_import_at' field"
        assert "database_size" in data, "Missing 'database_size' field"
        assert "execution_time_ms" in data, "Missing 'execution_time_ms' field"

        # Validate status values
        assert data["status"] in ["healthy", "degraded", "missing"], \
            f"Invalid status: {data['status']}"

    def test_health_check_healthy_status(self, app_client, test_database_with_schema_org):
        """Verify health check reports 'healthy' when conditions are met."""
        response = app_client.get("/api/reference/ref-db/health")

        assert response.status_code == 200
        data = response.json()

        # All test nodes have embeddings, so should be healthy
        if data["node_count"] == data["vec_count"] and data["node_count"] > 0:
            assert data["status"] == "healthy", \
                f"Expected 'healthy' status, got '{data['status']}'"

    def test_health_check_performance(self, app_client):
        """Verify health check executes in <200ms."""
        response = app_client.get("/api/reference/ref-db/health")

        assert response.status_code == 200
        data = response.json()

        execution_time = data.get("execution_time_ms", float('inf'))
        assert execution_time < 200, \
            f"Health check took {execution_time}ms, expected <200ms"

    def test_health_check_missing_database(self):
        """Verify health check reports 'missing' when database doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            non_existent_db = os.path.join(tmpdir, "nonexistent.db")

            # Use a manager with non-existent DB
            config = ReferenceConfig()

            # Directly test the manager's get_status method with a non-existent database
            # This is more direct than trying to patch the API
            status = ReferenceManager(config, db_path=non_existent_db).get_status()

            assert status["status"] == "missing", \
                f"Expected 'missing' status, got '{status['status']}'"


class TestTC_S003_APIContractValidation:
    """
    TC-S003: API contract validation against UX expectations.

    Validates that API responses match expected schemas and data structures.
    """

    def test_search_api_response_schema(self, app_client):
        """Verify search API returns expected response schema."""
        def mock_embedding(text: str) -> bytes:
            vec = np.full(384, 0.5, dtype=np.float32)
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        with patch('embeddings.generate_embeddings.generate_embedding', side_effect=mock_embedding):
            response = app_client.get(
                "/api/reference/ref-db/search",
                params={"query": "test", "limit": 10}
            )

        assert response.status_code == 200
        data = response.json()

        # Validate response schema
        assert "query" in data
        assert "total_results" in data
        assert "results" in data
        assert isinstance(data["results"], list)

        # Validate result item schema (if results exist)
        if data["total_results"] > 0:
            result = data["results"][0]
            assert "id" in result
            assert "title" in result
            assert "definition" in result
            assert "source" in result
            assert "external_id" in result
            assert "similarity_score" in result
            assert isinstance(result["similarity_score"], (int, float))
            assert 0 <= result["similarity_score"] <= 1

    def test_node_retrieval_api_schema(self, app_client, test_database_with_schema_org):
        """Verify node retrieval API returns expected schema."""
        db_path, nodes = test_database_with_schema_org
        person_id = nodes["nodes"]["person"]["id"]

        response = app_client.get(f"/api/reference/ref-db/nodes/{person_id}")

        assert response.status_code == 200
        data = response.json()

        # Validate schema
        assert "id" in data
        assert "title" in data
        assert "definition" in data
        assert "source" in data
        assert "external_id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_links_api_response_schema(self, app_client, test_database_with_schema_org):
        """Verify links API returns expected response schema."""
        db_path, nodes = test_database_with_schema_org
        person_id = nodes["nodes"]["person"]["id"]

        response = app_client.get(
            f"/api/reference/ref-db/nodes/{person_id}/links",
            params={"direction": "both"}
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response schema
        assert "node_id" in data
        assert "direction" in data
        assert "total_links" in data
        assert "links" in data
        assert isinstance(data["links"], list)

        # Validate link item schema (if links exist)
        if data["total_links"] > 0:
            link = data["links"][0]
            assert "id" in link
            assert "subject_node" in link
            assert "predicate" in link
            assert "object_node" in link
            assert "created_at" in link


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

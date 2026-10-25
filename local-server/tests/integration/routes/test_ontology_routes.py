"""
Integration tests for Ontology API routes.

Tests verify the ontology management workflow with:
- Real SQLite database (local.db)
- OntologyRepository backed by actual persistence
- EmbeddingService for semantic embeddings
- HTTP routes via TestClient
- End-to-end request/response validation

These tests exercise the complete stack: routes → domain service → adapters → database.
"""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.web.ontology_routes import router
from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        yield db_url


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory for the temporary database."""
    engine = create_engine(temp_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def repository(session_factory):
    """Create a real SQLiteOntologyRepository with actual persistence."""
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def embedding_service():
    """Create embedding service for semantic search."""
    return FakeEmbeddingService()


@pytest.fixture
def event_publisher():
    """Create event publisher."""
    return InProcessEventPublisher()


@pytest.fixture
def ontology_service(repository, embedding_service, event_publisher):
    """Create OntologyService with real adapters."""
    return OntologyService(
        repository=repository,
        embedding_service=embedding_service,
        event_publisher=event_publisher,
    )


@pytest.fixture
def client(ontology_service):
    """Create a TestClient with real ontology service."""
    app = FastAPI()
    app.include_router(router)
    app.state.ontology_service = ontology_service

    return TestClient(app)


class TestTaxonomyCRUD:
    """Integration tests for taxonomy CRUD operations."""

    def test_create_taxonomy_returns_201(self, client):
        """POST /api/taxonomies returns 201 with valid request."""
        response = client.post(
            "/api/taxonomies",
            json={"title": "Test Taxonomy", "description": "A test taxonomy"},
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_taxonomy_response_structure(self, client):
        """POST /api/taxonomies response has correct structure."""
        response = client.post(
            "/api/taxonomies",
            json={"title": "Test Taxonomy", "description": "A test taxonomy"},
        )
        body = response.json()

        assert "id" in body
        assert body["title"] == "Test Taxonomy"
        assert body["description"] == "A test taxonomy"
        assert "created_at" in body
        assert body["version"] == 1

    def test_list_taxonomies_returns_200(self, client):
        """GET /api/taxonomies returns 200 with list response."""
        # Create a taxonomy first
        client.post("/api/taxonomies", json={"title": "List Test Taxonomy"})

        response = client.get("/api/taxonomies")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert len(body["items"]) > 0

    def test_get_taxonomy_returns_200(self, client):
        """GET /api/taxonomies/{id} returns 200 with taxonomy."""
        create_response = client.post("/api/taxonomies", json={"title": "Get Test Taxonomy"})
        taxonomy_id = create_response.json()["id"]

        response = client.get(f"/api/taxonomies/{taxonomy_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == taxonomy_id
        assert body["title"] == "Get Test Taxonomy"

    def test_get_nonexistent_taxonomy_returns_404(self, client):
        """GET /api/taxonomies/{id} returns 404 for nonexistent taxonomy."""
        response = client.get(f"/api/taxonomies/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_taxonomy_returns_200(self, client):
        """PUT /api/taxonomies/{id} returns 200 with updated taxonomy."""
        create_response = client.post("/api/taxonomies", json={"title": "Update Test Taxonomy"})
        taxonomy_id = create_response.json()["id"]

        response = client.put(
            f"/api/taxonomies/{taxonomy_id}",
            json={"title": "Updated Title", "description": "Updated description"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Title"
        assert body["version"] == 2

    def test_delete_taxonomy_returns_204(self, client):
        """DELETE /api/taxonomies/{id} returns 204."""
        create_response = client.post("/api/taxonomies", json={"title": "Delete Test Taxonomy"})
        taxonomy_id = create_response.json()["id"]

        response = client.delete(f"/api/taxonomies/{taxonomy_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        response = client.get(f"/api/taxonomies/{taxonomy_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_duplicate_taxonomy_fails(self, client):
        """POST /api/taxonomies with duplicate title returns 409."""
        client.post("/api/taxonomies", json={"title": "Duplicate Title"})

        response = client.post("/api/taxonomies", json={"title": "Duplicate Title"})
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_taxonomy_with_empty_title_fails(self, client):
        """POST /api/taxonomies with empty title returns 422 (validation error)."""
        response = client.post("/api/taxonomies", json={"title": ""})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestConceptSchemeCRUD:
    """Integration tests for concept scheme CRUD operations."""

    def test_create_concept_scheme_returns_201(self, client):
        """POST /api/taxonomies/{id}/schemes returns 201."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Test Scheme", "description": "A test scheme"},
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_concept_scheme_response_structure(self, client):
        """POST /api/taxonomies/{id}/schemes response has correct structure."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        body = response.json()

        assert "id" in body
        assert body["title"] == "Test Scheme"
        assert body["taxonomy_id"] == taxonomy_id

    def test_list_concept_schemes_returns_200(self, client):
        """GET /api/schemes returns 200 with list response."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"})

        response = client.get("/api/schemes")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert len(body["items"]) > 0

    def test_get_concept_scheme_returns_200(self, client):
        """GET /api/schemes/{id} returns 200 with scheme."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Get Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        response = client.get(f"/api/schemes/{scheme_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == scheme_id

    def test_update_concept_scheme_returns_200(self, client):
        """PUT /api/schemes/{id} returns 200 with updated scheme."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Update Test Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        response = client.put(f"/api/schemes/{scheme_id}", json={"title": "Updated Scheme Title"})
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Scheme Title"

    def test_delete_concept_scheme_returns_204(self, client):
        """DELETE /api/schemes/{id} returns 204."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Delete Test Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        response = client.delete(f"/api/schemes/{scheme_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestClassCRUD:
    """Integration tests for class CRUD operations."""

    def test_create_class_returns_201(self, client):
        """POST /api/schemes/{id}/classes returns 201."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        response = client.post(f"/api/schemes/{scheme_id}/classes", json={"title": "Test Class"})
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_class_response_structure(self, client):
        """POST /api/schemes/{id}/classes response has correct structure."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        response = client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Test Class", "description": "A test class"},
        )
        body = response.json()

        assert "id" in body
        assert body["title"] == "Test Class"
        assert body["concept_scheme_id"] == scheme_id

    def test_list_classes_returns_200(self, client):
        """GET /api/classes returns 200 with list response."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        client.post(f"/api/schemes/{scheme_id}/classes", json={"title": "Test Class"})

        response = client.get("/api/classes")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert len(body["items"]) > 0

    def test_get_class_returns_200(self, client):
        """GET /api/classes/{id} returns 200 with class."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Get Test Class"}
        )
        class_id = class_response.json()["id"]

        response = client.get(f"/api/classes/{class_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == class_id

    def test_update_class_returns_200(self, client):
        """PUT /api/classes/{id} returns 200 with updated class."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Update Test Class"}
        )
        class_id = class_response.json()["id"]

        response = client.put(f"/api/classes/{class_id}", json={"title": "Updated Class Title"})
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Class Title"

    def test_delete_class_returns_204(self, client):
        """DELETE /api/classes/{id} returns 204."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Delete Test Class"}
        )
        class_id = class_response.json()["id"]

        response = client.delete(f"/api/classes/{class_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_move_class_returns_200(self, client):
        """POST /api/classes/{id}/move returns 200 and moves class to new scheme."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme1_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme 1"}
        )
        scheme1_id = scheme1_response.json()["id"]

        scheme2_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme 2"}
        )
        scheme2_id = scheme2_response.json()["id"]

        class_response = client.post(
            f"/api/schemes/{scheme1_id}/classes", json={"title": "Move Test Class"}
        )
        class_id = class_response.json()["id"]

        response = client.post(
            f"/api/classes/{class_id}/move", json={"target_scheme_id": scheme2_id}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["concept_scheme_id"] == scheme2_id


class TestRelationshipCRUD:
    """Integration tests for relationship CRUD operations."""

    def test_create_relationship_returns_201(self, client):
        """POST /api/relationships returns 201."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 2"}
        )
        class2_id = class2_response.json()["id"]

        response = client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "relationship_type": "related_to",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_list_relationships_returns_200(self, client):
        """GET /api/relationships returns 200 with list response."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 2"}
        )
        class2_id = class2_response.json()["id"]

        client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "relationship_type": "related_to",
            },
        )

        response = client.get("/api/relationships")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body

    def test_get_relationship_returns_200(self, client):
        """GET /api/relationships/{id} returns 200 with relationship."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 2"}
        )
        class2_id = class2_response.json()["id"]

        rel_response = client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "relationship_type": "related_to",
            },
        )
        relationship_id = rel_response.json()["id"]

        response = client.get(f"/api/relationships/{relationship_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == relationship_id
        assert body["source_id"] == class1_id
        assert body["target_id"] == class2_id

    def test_delete_relationship_returns_204(self, client):
        """DELETE /api/relationships/{id} returns 204."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 2"}
        )
        class2_id = class2_response.json()["id"]

        rel_response = client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "relationship_type": "related_to",
            },
        )
        relationship_id = rel_response.json()["id"]

        response = client.delete(f"/api/relationships/{relationship_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestPropertyDefinitionCRUD:
    """Integration tests for property definition CRUD operations."""

    def test_create_property_definition_returns_201(self, client):
        """POST /api/properties returns 201."""
        response = client.post(
            "/api/properties",
            json={
                "identifier": "test_property",
                "title": "Test Property",
                "description": "A test property definition",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "id" in body

    def test_create_property_definition_response_structure(self, client):
        """POST /api/properties response has correct structure."""
        response = client.post(
            "/api/properties",
            json={
                "identifier": "test_prop_2",
                "title": "Test Property 2",
                "description": "Another test property",
            },
        )
        body = response.json()

        assert "id" in body
        assert body["identifier"] == "test_prop_2"
        assert body["title"] == "Test Property 2"
        assert body["description"] == "Another test property"

    def test_list_properties_returns_200(self, client):
        """GET /api/properties returns 200 with list response."""
        client.post("/api/properties", json={"identifier": "prop1", "title": "Property 1"})
        client.post("/api/properties", json={"identifier": "prop2", "title": "Property 2"})

        response = client.get("/api/properties")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert len(body["items"]) >= 2

    def test_get_property_definition_returns_200(self, client):
        """GET /api/properties/{id} returns 200 with property definition."""
        create_response = client.post(
            "/api/properties",
            json={"identifier": "get_test_prop", "title": "Get Test Property"},
        )
        property_id = create_response.json()["id"]

        response = client.get(f"/api/properties/{property_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == property_id
        assert body["identifier"] == "get_test_prop"

    def test_update_property_definition_returns_200(self, client):
        """PUT /api/properties/{id} returns 200 with updated property definition."""
        create_response = client.post(
            "/api/properties",
            json={"identifier": "update_prop", "title": "Update Test Property"},
        )
        property_id = create_response.json()["id"]

        response = client.put(
            f"/api/properties/{property_id}",
            json={
                "identifier": "update_prop",
                "title": "Updated Property Title",
                "description": "Updated description",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Property Title"
        assert body["description"] == "Updated description"

    def test_canonical_predicate_round_trips_through_create_get_update(self, client):
        """canonical_predicate is accepted on create, returned on get, and editable."""
        create_response = client.post(
            "/api/properties",
            json={
                "identifier": "canon_prop",
                "title": "Canon Test Property",
                "canonical_predicate": "navigates-to",
            },
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        property_id = create_response.json()["id"]
        assert create_response.json()["canonical_predicate"] == "navigates-to"

        # Present on GET.
        get_response = client.get(f"/api/properties/{property_id}")
        assert get_response.json()["canonical_predicate"] == "navigates-to"

        # Editable via PUT.
        update_response = client.put(
            f"/api/properties/{property_id}",
            json={"canonical_predicate": "flows-to"},
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["canonical_predicate"] == "flows-to"

        # Omitting the field on a subsequent update leaves it unchanged (the
        # model_fields_set flag pattern), while an explicit null clears it.
        untouched = client.put(
            f"/api/properties/{property_id}",
            json={"title": "Canon Test Property v2"},
        )
        assert untouched.json()["canonical_predicate"] == "flows-to"
        cleared = client.put(
            f"/api/properties/{property_id}",
            json={"canonical_predicate": None},
        )
        assert cleared.json()["canonical_predicate"] is None

    def test_delete_property_definition_returns_204(self, client):
        """DELETE /api/properties/{id} returns 204."""
        create_response = client.post(
            "/api/properties",
            json={"identifier": "delete_prop", "title": "Delete Test Property"},
        )
        property_id = create_response.json()["id"]

        response = client.delete(f"/api/properties/{property_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestAutoCreatePropertyDefinition:
    """Integration tests for auto-creation of property definitions during relationship creation."""

    def test_create_relationship_auto_creates_property_definition(self, client):
        """Create relationship auto-creates property definition if not present."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 2"}
        )
        class2_id = class2_response.json()["id"]

        response = client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "relationship_type": "auto_created_type",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        rel_data = response.json()
        assert "property_definition_id" in rel_data

        # Verify property definition was created with derived title
        prop_id = rel_data["property_definition_id"]
        prop_response = client.get(f"/api/properties/{prop_id}")
        assert prop_response.status_code == status.HTTP_200_OK
        prop_data = prop_response.json()
        assert prop_data["identifier"] == "auto_created_type"
        # Verify title is derived correctly: snake_case becomes Title Case
        assert prop_data["title"] == "Auto Created Type"

    def test_create_relationship_with_existing_property_definition_reuses_it(self, client):
        """Create relationship reuses existing property definition instead of creating new one."""
        # Create a property definition explicitly
        prop_response = client.post(
            "/api/properties",
            json={
                "identifier": "existing_relationship",
                "title": "Existing Relationship Type",
                "description": "A pre-existing property definition",
            },
        )
        assert prop_response.status_code == status.HTTP_201_CREATED
        property_id = prop_response.json()["id"]

        # Create taxonomies and classes for relationships
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 2"}
        )
        class2_id = class2_response.json()["id"]

        # Create relationship with the same identifier
        response = client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "relationship_type": "existing_relationship",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        rel_data = response.json()

        # Verify the relationship uses the existing property definition
        assert rel_data["property_definition_id"] == property_id

    def test_create_multiple_relationships_with_same_type_is_idempotent(self, client):
        """Multiple relationships with same type use the same property definition."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        # Create 4 classes
        class_ids = []
        for i in range(4):
            resp = client.post(f"/api/schemes/{scheme_id}/classes", json={"title": f"Class {i+1}"})
            class_ids.append(resp.json()["id"])

        # Create first relationship
        rel1_response = client.post(
            "/api/relationships",
            json={
                "source_id": class_ids[0],
                "target_id": class_ids[1],
                "relationship_type": "idempotent_type",
            },
        )
        assert rel1_response.status_code == status.HTTP_201_CREATED
        property_id_1 = rel1_response.json()["property_definition_id"]

        # Create second relationship with same type
        rel2_response = client.post(
            "/api/relationships",
            json={
                "source_id": class_ids[2],
                "target_id": class_ids[3],
                "relationship_type": "idempotent_type",
            },
        )
        assert rel2_response.status_code == status.HTTP_201_CREATED
        property_id_2 = rel2_response.json()["property_definition_id"]

        # Both relationships should use the same property definition
        assert property_id_1 == property_id_2

        # Verify only one property definition was created
        props_response = client.get("/api/properties")
        matching_props = [
            p for p in props_response.json()["items"] if p["identifier"] == "idempotent_type"
        ]
        assert len(matching_props) == 1
        assert matching_props[0]["id"] == property_id_1

    def test_create_relationship_derives_title_correctly_from_snake_case(self, client):
        """Property definition title is correctly derived from snake_case identifier."""
        tax_response = client.post("/api/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 2"}
        )
        class2_id = class2_response.json()["id"]

        # Test various snake_case transformations
        test_cases = [
            ("simple_type", "Simple Type"),
            ("complex_relationship_type", "Complex Relationship Type"),
            ("a_b_c", "A B C"),
        ]

        for identifier, expected_title in test_cases:
            response = client.post(
                "/api/relationships",
                json={
                    "source_id": class1_id,
                    "target_id": class2_id,
                    "relationship_type": identifier,
                },
            )
            assert response.status_code == status.HTTP_201_CREATED
            prop_id = response.json()["property_definition_id"]

            prop_response = client.get(f"/api/properties/{prop_id}")
            assert prop_response.status_code == status.HTTP_200_OK
            prop_data = prop_response.json()
            assert prop_data["title"] == expected_title


class TestIndividualCRUD:
    """Integration tests for individual CRUD operations."""

    @pytest.fixture
    def individual_test_class(self, client):
        """Create a taxonomy, scheme, and class for individual tests."""
        tax_response = client.post("/api/taxonomies", json={"title": "Individual Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Individual Test Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        class_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Individual Test Class"}
        )
        class_id = class_response.json()["id"]

        return {
            "taxonomy_id": taxonomy_id,
            "scheme_id": scheme_id,
            "class_id": class_id,
        }

    def test_create_individual_returns_201(self, client, individual_test_class):
        """POST /api/individuals returns 201 with valid request."""
        response = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Test Individual",
                "description": "A test individual",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_individual_response_structure(self, client, individual_test_class):
        """POST /api/individuals response has correct structure."""
        response = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Test Individual",
                "description": "A test individual",
            },
        )
        body = response.json()

        assert "id" in body
        assert body["title"] == "Test Individual"
        assert body["description"] == "A test individual"
        assert "class_ids" in body
        assert individual_test_class["class_id"] in body["class_ids"]
        assert "created_at" in body
        assert body["version"] == 1

    def test_create_individual_with_multiple_classes(self, client, individual_test_class):
        """POST /api/individuals with multiple classes."""
        # Create a second class
        class2_response = client.post(
            f"/api/schemes/{individual_test_class['scheme_id']}/classes",
            json={"title": "Second Class"},
        )
        class2_id = class2_response.json()["id"]

        response = client.post(
            "/api/individuals",
            json={
                "class_ids": [individual_test_class["class_id"], class2_id],
                "title": "Multi-Class Individual",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert len(body["class_ids"]) == 2
        assert body["class_ids"][0] == individual_test_class["class_id"]
        assert body["class_ids"][1] == class2_id

    def test_create_individual_with_duplicate_title_same_class_fails(
        self, client, individual_test_class
    ):
        """POST /api/individuals with duplicate title in same class returns 409."""
        # Create first individual
        response1 = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Duplicate Title Individual",
            },
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Try to create second individual with same title in same class
        response2 = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Duplicate Title Individual",
            },
        )
        assert response2.status_code == status.HTTP_409_CONFLICT

    def test_create_individual_without_class_fails(self, client):
        """POST /api/individuals without class_ids returns 422."""
        response = client.post(
            "/api/individuals", json={"class_ids": [], "title": "Test Individual"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_individual_with_nonexistent_class_fails(self, client):
        """POST /api/individuals with nonexistent class returns 404."""
        response = client.post(
            "/api/individuals",
            json={"class_ids": str(uuid4()), "title": "Test Individual"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_individuals_returns_200(self, client, individual_test_class):
        """GET /api/individuals returns 200 with list response."""
        client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Individual 1",
            },
        )

        response = client.get("/api/individuals")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] > 0

    def test_list_individuals_filter_by_class(self, client, individual_test_class):
        """GET /api/individuals?class_id=X filters by class."""
        client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Individual 1",
            },
        )

        response = client.get(f"/api/individuals?class_id={individual_test_class['class_id']}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] > 0
        # All returned individuals should have this class
        for item in body["items"]:
            assert individual_test_class["class_id"] in item["class_ids"]

    def test_get_individual_returns_200(self, client, individual_test_class):
        """GET /api/individuals/{id} returns 200 with individual."""
        create_response = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Get Test Individual",
            },
        )
        individual_id = create_response.json()["id"]

        response = client.get(f"/api/individuals/{individual_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == individual_id
        assert body["title"] == "Get Test Individual"

    def test_get_nonexistent_individual_returns_404(self, client):
        """GET /api/individuals/{id} returns 404 for nonexistent individual."""
        response = client.get(f"/api/individuals/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_individual_returns_200(self, client, individual_test_class):
        """PUT /api/individuals/{id} returns 200 with updated individual."""
        create_response = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Update Test Individual",
            },
        )
        individual_id = create_response.json()["id"]

        response = client.put(
            f"/api/individuals/{individual_id}",
            json={"title": "Updated Title", "description": "Updated description"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Title"
        assert body["version"] == 2

    def test_delete_individual_returns_204(self, client, individual_test_class):
        """DELETE /api/individuals/{id} returns 204."""
        create_response = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Delete Test Individual",
            },
        )
        individual_id = create_response.json()["id"]

        response = client.delete(f"/api/individuals/{individual_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        response = client.get(f"/api/individuals/{individual_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_add_parent_class_to_individual(self, client, individual_test_class):
        """POST /api/individuals/{id}/classes adds a parent class."""
        individual_response = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Add Class Test",
            },
        )
        individual_id = individual_response.json()["id"]

        # Create a second class
        class2_response = client.post(
            f"/api/schemes/{individual_test_class['scheme_id']}/classes",
            json={"title": "Second Class"},
        )
        class2_id = class2_response.json()["id"]

        response = client.post(
            f"/api/individuals/{individual_id}/classes", json={"class_id": class2_id}
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert len(body["class_ids"]) == 2
        assert class2_id in body["class_ids"]

    def test_remove_parent_class_from_individual(self, client, individual_test_class):
        """DELETE /api/individuals/{id}/classes/{class_id} removes a parent class."""
        # Create individual with two classes
        class2_response = client.post(
            f"/api/schemes/{individual_test_class['scheme_id']}/classes",
            json={"title": "Second Class"},
        )
        class2_id = class2_response.json()["id"]

        individual_response = client.post(
            "/api/individuals",
            json={
                "class_ids": [individual_test_class["class_id"], class2_id],
                "title": "Remove Class Test",
            },
        )
        individual_id = individual_response.json()["id"]

        response = client.delete(f"/api/individuals/{individual_id}/classes/{class2_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify class was removed
        get_response = client.get(f"/api/individuals/{individual_id}")
        body = get_response.json()
        assert len(body["class_ids"]) == 1
        assert individual_test_class["class_id"] in body["class_ids"]

    def test_remove_last_parent_class_fails(self, client, individual_test_class):
        """DELETE /api/individuals/{id}/classes/{class_id} fails if only class."""
        individual_response = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Single Class Individual",
            },
        )
        individual_id = individual_response.json()["id"]

        response = client.delete(
            f"/api/individuals/{individual_id}/classes/{individual_test_class['class_id']}"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reorder_individual_classes(self, client, individual_test_class):
        """PUT /api/individuals/{id}/classes reorders class list."""
        # Create individual with two classes
        class2_response = client.post(
            f"/api/schemes/{individual_test_class['scheme_id']}/classes",
            json={"title": "Second Class"},
        )
        class2_id = class2_response.json()["id"]

        individual_response = client.post(
            "/api/individuals",
            json={
                "class_ids": [individual_test_class["class_id"], class2_id],
                "title": "Reorder Test",
            },
        )
        individual_id = individual_response.json()["id"]

        response = client.put(
            f"/api/individuals/{individual_id}/classes",
            json={"class_ids": [class2_id, individual_test_class["class_id"]]},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["class_ids"][0] == class2_id
        assert body["class_ids"][1] == individual_test_class["class_id"]

    def test_get_individual_inherited_properties(self, client, individual_test_class):
        """GET /api/individuals/{id}/inherited-properties returns properties."""
        individual_response = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Properties Test",
            },
        )
        individual_id = individual_response.json()["id"]

        response = client.get(f"/api/individuals/{individual_id}/inherited-properties")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert isinstance(body["items"], list)

    def test_round_trip_individual_operations(self, client, individual_test_class):
        """Round-trip test: create → add class → reorder → get properties → delete."""
        # Create individual
        individual_response = client.post(
            "/api/individuals",
            json={
                "class_ids": individual_test_class["class_id"],
                "title": "Round Trip Test",
            },
        )
        assert individual_response.status_code == status.HTTP_201_CREATED
        individual_id = individual_response.json()["id"]

        # Add a second class
        class2_response = client.post(
            f"/api/schemes/{individual_test_class['scheme_id']}/classes",
            json={"title": "Second Class for Round Trip"},
        )
        class2_id = class2_response.json()["id"]

        add_class_response = client.post(
            f"/api/individuals/{individual_id}/classes", json={"class_id": class2_id}
        )
        assert add_class_response.status_code == status.HTTP_201_CREATED

        # Reorder classes
        reorder_response = client.put(
            f"/api/individuals/{individual_id}/classes",
            json={"class_ids": [class2_id, individual_test_class["class_id"]]},
        )
        assert reorder_response.status_code == status.HTTP_200_OK

        # Get inherited properties
        properties_response = client.get(f"/api/individuals/{individual_id}/inherited-properties")
        assert properties_response.status_code == status.HTTP_200_OK

        # Delete individual
        delete_response = client.delete(f"/api/individuals/{individual_id}")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        get_response = client.get(f"/api/individuals/{individual_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND


class TestAttributeDefinitionCRUD:
    """Integration tests for attribute definition CRUD operations."""

    @pytest.fixture
    def class_fixture(self, client):
        """Create a class for attribute definition tests."""
        tax_response = client.post("/api/taxonomies", json={"title": "Attribute Test Taxonomy"})
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Attribute Test Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        class_response = client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Attribute Test Class"}
        )
        class_id = class_response.json()["id"]

        return {
            "class_id": class_id,
            "taxonomy_id": taxonomy_id,
            "scheme_id": scheme_id,
        }

    def test_create_attribute_definition_returns_201(self, client, class_fixture):
        """POST /api/classes/{class_id}/attribute-definitions returns 201."""
        response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "test_attr",
                "title": "Test Attribute",
                "datatype": "string",
                "description": "A test attribute",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "id" in body
        assert body["class_id"] == class_fixture["class_id"]
        assert body["identifier"] == "test_attr"
        assert body["title"] == "Test Attribute"
        assert body["datatype"] == "string"

    def test_create_attribute_definition_with_nonexistent_class_returns_404(self, client):
        """POST /api/classes/{invalid_id}/attribute-definitions returns 404."""
        response = client.post(
            "/api/classes/invalid-class-id/attribute-definitions",
            json={
                "identifier": "test_attr",
                "title": "Test Attribute",
                "datatype": "string",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_attribute_definition_with_all_fields(self, client, class_fixture):
        """Create attribute with all optional fields."""
        response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "full_attr",
                "title": "Full Attribute",
                "datatype": "integer",
                "description": "Full attribute with all fields",
                "is_required": True,
                "allowed_values": ["1", "2", "3"],
                "default_value": "1",
                "sort_order": 5,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["is_required"] is True
        assert body["allowed_values"] == ["1", "2", "3"]
        assert body["default_value"] == "1"
        assert body["sort_order"] == 5

    def test_create_duplicate_attribute_identifier_in_class_fails(self, client, class_fixture):
        """Creating duplicate identifier in same class fails."""
        # Create first attribute
        client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "dup_attr",
                "title": "First Attribute",
                "datatype": "string",
            },
        )

        # Try to create duplicate
        response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "dup_attr",
                "title": "Second Attribute",
                "datatype": "string",
            },
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_attribute_definition_with_empty_title_fails(self, client, class_fixture):
        """Create attribute with empty title fails."""
        response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "empty_title",
                "title": "",
                "datatype": "string",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_attribute_definition_with_empty_datatype_fails(self, client, class_fixture):
        """Create attribute with empty datatype fails."""
        response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "empty_datatype",
                "title": "Test",
                "datatype": "",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_class_attribute_definitions_returns_200(self, client, class_fixture):
        """GET /api/classes/{class_id}/attribute-definitions returns 200."""
        # Create multiple attributes
        client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={"identifier": "attr1", "title": "Attribute 1", "datatype": "string"},
        )
        client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={"identifier": "attr2", "title": "Attribute 2", "datatype": "integer"},
        )

        response = client.get(f"/api/classes/{class_fixture['class_id']}/attribute-definitions")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert len(body["items"]) >= 2

    def test_list_class_attribute_definitions_for_nonexistent_class_returns_404(self, client):
        """GET /api/classes/{invalid_id}/attribute-definitions returns 404."""
        response = client.get("/api/classes/invalid-class-id/attribute-definitions")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_class_attribute_definitions_pagination(self, client, class_fixture):
        """List attribute definitions with pagination."""
        # Create 3 attributes
        for i in range(3):
            client.post(
                f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
                json={
                    "identifier": f"attr_{i}",
                    "title": f"Attribute {i}",
                    "datatype": "string",
                },
            )

        response = client.get(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            params={"limit": 2, "offset": 0},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 0

    def test_get_attribute_definition_returns_200(self, client, class_fixture):
        """GET /api/attribute-definitions/{id} returns 200."""
        create_response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "get_test",
                "title": "Get Test Attribute",
                "datatype": "string",
            },
        )
        attr_id = create_response.json()["id"]

        response = client.get(f"/api/attribute-definitions/{attr_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == attr_id
        assert body["identifier"] == "get_test"
        assert body["title"] == "Get Test Attribute"
        assert body["datatype"] == "string"

    def test_get_nonexistent_attribute_definition_returns_404(self, client):
        """GET /api/attribute-definitions/{invalid_id} returns 404."""
        response = client.get("/api/attribute-definitions/invalid-attr-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_attribute_definition_returns_200(self, client, class_fixture):
        """PUT /api/attribute-definitions/{id} returns 200."""
        create_response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "update_test",
                "title": "Update Test",
                "datatype": "string",
            },
        )
        attr_id = create_response.json()["id"]

        response = client.put(
            f"/api/attribute-definitions/{attr_id}",
            json={
                "title": "Updated Title",
                "description": "Updated description",
                "is_required": True,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Title"
        assert body["description"] == "Updated description"
        assert body["is_required"] is True

    def test_update_attribute_definition_partial(self, client, class_fixture):
        """Partial update only changes specified fields."""
        create_response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "partial_test",
                "title": "Original Title",
                "datatype": "string",
                "description": "Original description",
                "is_required": False,
            },
        )
        attr_id = create_response.json()["id"]

        # Update only title
        response = client.put(
            f"/api/attribute-definitions/{attr_id}",
            json={"title": "New Title"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "New Title"
        assert body["description"] == "Original description"
        assert body["is_required"] is False

    def test_update_attribute_definition_datatype(self, client, class_fixture):
        """Update datatype field."""
        create_response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "datatype_test",
                "title": "Datatype Test",
                "datatype": "string",
            },
        )
        attr_id = create_response.json()["id"]

        response = client.put(
            f"/api/attribute-definitions/{attr_id}",
            json={"datatype": "integer"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["datatype"] == "integer"

    def test_update_attribute_definition_allowed_values(self, client, class_fixture):
        """Update allowed_values field."""
        create_response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "enum_test",
                "title": "Enum Test",
                "datatype": "string",
                "allowed_values": ["a", "b"],
            },
        )
        attr_id = create_response.json()["id"]

        response = client.put(
            f"/api/attribute-definitions/{attr_id}",
            json={"allowed_values": ["x", "y", "z"]},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["allowed_values"] == ["x", "y", "z"]

    def test_update_nonexistent_attribute_definition_returns_404(self, client):
        """PUT /api/attribute-definitions/{invalid_id} returns 404."""
        response = client.put(
            "/api/attribute-definitions/invalid-attr-id",
            json={"title": "Updated Title"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_attribute_definition_returns_204(self, client, class_fixture):
        """DELETE /api/attribute-definitions/{id} returns 204."""
        create_response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "delete_test",
                "title": "Delete Test",
                "datatype": "string",
            },
        )
        attr_id = create_response.json()["id"]

        response = client.delete(f"/api/attribute-definitions/{attr_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        get_response = client.get(f"/api/attribute-definitions/{attr_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_attribute_definition_returns_404(self, client):
        """DELETE /api/attribute-definitions/{invalid_id} returns 404."""
        response = client.delete("/api/attribute-definitions/invalid-attr-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_attribute_definition_version_increments_on_update(self, client, class_fixture):
        """Version number increments on update."""
        create_response = client.post(
            f"/api/classes/{class_fixture['class_id']}/attribute-definitions",
            json={
                "identifier": "version_test",
                "title": "Version Test",
                "datatype": "string",
            },
        )
        attr_id = create_response.json()["id"]
        initial_version = create_response.json()["version"]

        # Update
        update_response = client.put(
            f"/api/attribute-definitions/{attr_id}",
            json={"title": "Updated Title"},
        )
        assert update_response.json()["version"] == initial_version + 1


class TestListTotalsBeyondDefaultLimit:
    """List endpoints report the true total, not the default page size."""

    @pytest.fixture
    def large_ontology(self, ontology_service):
        """Seed more than 100 classes and individuals (the default page size)."""
        taxonomy = ontology_service.create_taxonomy(title="Large Taxonomy")
        scheme = ontology_service.create_scheme(taxonomy_id=taxonomy.id, title="Large Scheme")
        classes = [
            ontology_service.create_class(concept_scheme_id=scheme.id, title=f"Class {i}")
            for i in range(120)
        ]
        for i in range(130):
            ontology_service.create_individual(classes[0].id, title=f"Individual {i}")
        ontology_service.create_individual(classes[1].id, title="Other Individual")
        return {"scheme_id": scheme.id, "first_class_id": classes[0].id}

    def test_classes_total_is_true_count(self, client, large_ontology):
        """GET /api/classes total counts every class, not just the first page."""
        response = client.get("/api/classes")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 100
        assert data["total"] == 120

    def test_classes_limit_5000_returns_all(self, client, large_ontology):
        """GET /api/classes?limit=5000 is accepted and returns every class."""
        response = client.get("/api/classes?limit=5000")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 120
        assert data["total"] == 120
        assert data["limit"] == 5000

    def test_classes_total_filtered_by_parent_class(self, client, ontology_service):
        """GET /api/classes?parent_class_id=X total counts only that parent's subclasses."""
        taxonomy = ontology_service.create_taxonomy(title="Parent Filter Taxonomy")
        scheme = ontology_service.create_scheme(taxonomy_id=taxonomy.id, title="Parent Scheme")
        parent = ontology_service.create_class(concept_scheme_id=scheme.id, title="Parent")
        for i in range(3):
            ontology_service.create_class(
                concept_scheme_id=scheme.id, title=f"Child {i}", parent_class_id=parent.id
            )
        ontology_service.create_class(concept_scheme_id=scheme.id, title="Unrelated")

        response = client.get(f"/api/classes?parent_class_id={parent.id}&limit=2")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3

    def test_individuals_total_is_true_count(self, client, large_ontology):
        """GET /api/individuals total counts every individual, not just the first page."""
        response = client.get("/api/individuals")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 100
        assert data["total"] == 131

    def test_individuals_offset_pages_past_first_100(self, client, large_ontology):
        """GET /api/individuals with offset returns rows beyond the first 100."""
        response = client.get("/api/individuals?limit=100&offset=100")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 31
        assert data["total"] == 131

    def test_individuals_total_filtered_by_class(self, client, large_ontology):
        """GET /api/individuals?class_id=X total counts only that class's individuals."""
        response = client.get(
            f"/api/individuals?class_id={large_ontology['first_class_id']}&limit=5000"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 130
        assert data["total"] == 130

    @pytest.mark.parametrize(
        "path",
        [
            "/api/taxonomies",
            "/api/schemes",
            "/api/classes",
            "/api/relationships",
            "/api/properties",
            "/api/individuals",
        ],
    )
    def test_list_endpoints_accept_limit_5000(self, client, path):
        """List endpoints accept limit=5000 and reject values above it."""
        assert client.get(f"{path}?limit=5000").status_code == status.HTTP_200_OK
        assert client.get(f"{path}?limit=5001").status_code == 422


def _create_scheme(client, title="Scheme"):
    """Create a taxonomy and a concept scheme in it; return the scheme id."""
    tax = client.post("/api/taxonomies", json={"title": f"Tax {uuid4().hex[:6]}"}).json()
    scheme = client.post(f"/api/taxonomies/{tax['id']}/schemes", json={"title": title}).json()
    return scheme["id"]


def _create_class(client, scheme_id, title, identifier=None):
    body = {"title": title}
    if identifier:
        body["identifier"] = identifier
    response = client.post(f"/api/schemes/{scheme_id}/classes", json=body)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


class TestClassListQueryParams:
    """GET /api/classes q / ids / sort_by filters, with total honoring every filter."""

    @pytest.fixture
    def classes(self, client):
        scheme_id = _create_scheme(client)
        other_scheme_id = _create_scheme(client, "Other")
        created = {
            "alpha": _create_class(client, scheme_id, "Alpha Widget", "alpha_widget"),
            "beta": _create_class(client, scheme_id, "Beta Widget", "beta_widget"),
            "gamma": _create_class(client, scheme_id, "Gamma 100%", "gizmo"),
            "delta": _create_class(client, other_scheme_id, "Delta Widget", "delta_widget"),
        }
        return scheme_id, created

    def test_q_matches_title_case_insensitively_and_total_counts_all_matches(
        self, client, classes
    ):
        response = client.get("/api/classes", params={"q": "WIDGET", "limit": 2})
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert len(body["items"]) == 2
        assert body["total"] == 3

    def test_q_matches_identifier(self, client, classes):
        body = client.get("/api/classes", params={"q": "gizmo"}).json()
        assert [c["title"] for c in body["items"]] == ["Gamma 100%"]
        assert body["total"] == 1

    def test_q_wildcards_match_literally(self, client, classes):
        assert client.get("/api/classes", params={"q": "100%"}).json()["total"] == 1
        assert client.get("/api/classes", params={"q": "_"}).json()["total"] == 3
        assert client.get("/api/classes", params={"q": "%"}).json()["total"] == 1

    def test_empty_q_is_no_filter(self, client, classes):
        assert client.get("/api/classes", params={"q": ""}).json()["total"] == 4

    def test_q_combined_with_scheme_filter(self, client, classes):
        scheme_id, _ = classes
        body = client.get(
            "/api/classes", params={"q": "widget", "concept_scheme_id": scheme_id}
        ).json()
        assert body["total"] == 2
        assert {c["title"] for c in body["items"]} == {"Alpha Widget", "Beta Widget"}

    def test_ids_restricts_results_and_total(self, client, classes):
        _, created = classes
        ids = [created["alpha"]["id"], created["delta"]["id"]]
        body = client.get("/api/classes", params={"ids": ids}).json()
        assert {c["id"] for c in body["items"]} == set(ids)
        assert body["total"] == 2

    def test_ids_combined_with_q(self, client, classes):
        _, created = classes
        ids = [created["alpha"]["id"], created["gamma"]["id"]]
        body = client.get("/api/classes", params={"ids": ids, "q": "widget"}).json()
        assert [c["id"] for c in body["items"]] == [created["alpha"]["id"]]
        assert body["total"] == 1

    def test_too_many_ids_is_rejected(self, client, classes):
        response = client.get("/api/classes", params={"ids": [str(uuid4()) for _ in range(501)]})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_sort_by_title_both_directions(self, client, classes):
        asc = client.get("/api/classes", params={"sort_by": "title"}).json()["items"]
        desc = client.get(
            "/api/classes", params={"sort_by": "title", "sort_order": "desc"}
        ).json()["items"]
        titles = ["Alpha Widget", "Beta Widget", "Delta Widget", "Gamma 100%"]
        assert [c["title"] for c in asc] == titles
        assert [c["title"] for c in desc] == list(reversed(titles))

    def test_offset_pages_through_sorted_results(self, client, classes):
        page = client.get(
            "/api/classes", params={"sort_by": "title", "limit": 2, "offset": 2}
        ).json()
        assert [c["title"] for c in page["items"]] == ["Delta Widget", "Gamma 100%"]
        assert page["total"] == 4

    def test_invalid_sort_by_is_rejected(self, client, classes):
        response = client.get("/api/classes", params={"sort_by": "description"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestIndividualListQueryParams:
    """GET /api/individuals q / ids / sort_by filters, with total honoring every filter."""

    @pytest.fixture
    def individuals(self, client):
        scheme_id = _create_scheme(client)
        person = _create_class(client, scheme_id, "Person")
        place = _create_class(client, scheme_id, "Place")
        created = {}
        for title, cls in [
            ("Ada Lovelace", person),
            ("Alan Turing", person),
            ("London", place),
        ]:
            response = client.post(
                "/api/individuals", json={"title": title, "class_ids": [cls["id"]]}
            )
            assert response.status_code == status.HTTP_201_CREATED, response.text
            created[title] = response.json()
        return person, created

    def test_q_filters_and_total_counts_all_matches(self, client, individuals):
        body = client.get("/api/individuals", params={"q": "a", "limit": 1}).json()
        assert body["total"] == 2
        assert len(body["items"]) == 1

    def test_q_is_case_insensitive_with_null_identifier(self, client, individuals):
        body = client.get("/api/individuals", params={"q": "LONDON"}).json()
        assert [i["title"] for i in body["items"]] == ["London"]
        assert body["total"] == 1

    def test_q_combined_with_class_filter(self, client, individuals):
        person, _ = individuals
        body = client.get("/api/individuals", params={"q": "tur", "class_id": person["id"]}).json()
        assert [i["title"] for i in body["items"]] == ["Alan Turing"]
        assert body["total"] == 1

    def test_ids_restricts_results_and_total(self, client, individuals):
        _, created = individuals
        ids = [created["London"]["id"]]
        body = client.get("/api/individuals", params={"ids": ids}).json()
        assert [i["id"] for i in body["items"]] == ids
        assert body["total"] == 1

    def test_sort_by_title_desc(self, client, individuals):
        body = client.get(
            "/api/individuals", params={"sort_by": "title", "sort_order": "desc"}
        ).json()
        assert [i["title"] for i in body["items"]] == ["London", "Alan Turing", "Ada Lovelace"]

    def test_invalid_sort_order_is_rejected(self, client, individuals):
        response = client.get("/api/individuals", params={"sort_order": "sideways"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestPropertyListQueryParams:
    """GET /api/properties q (title or identifier) and ids filters."""

    @pytest.fixture
    def properties(self, client):
        created = {}
        for identifier, title in [
            ("works_for", "Works For"),
            ("lives_in", "Lives In"),
            ("knows", "Knows"),
        ]:
            response = client.post(
                "/api/properties", json={"identifier": identifier, "title": title}
            )
            assert response.status_code == status.HTTP_201_CREATED, response.text
            created[identifier] = response.json()
        return created

    def test_q_matches_identifier_and_total(self, client, properties):
        body = client.get("/api/properties", params={"q": "_for"}).json()
        assert [p["identifier"] for p in body["items"]] == ["works_for"]
        assert body["total"] == 1

    def test_ids_restricts_results_and_total(self, client, properties):
        ids = [properties["knows"]["id"], properties["lives_in"]["id"]]
        body = client.get("/api/properties", params={"ids": ids, "limit": 1}).json()
        assert len(body["items"]) == 1
        assert body["total"] == 2


class TestRelationshipListQueryParams:
    """GET /api/relationships q matches source title, target title, or predicate."""

    @pytest.fixture
    def relationships(self, client):
        scheme_id = _create_scheme(client)
        car = _create_class(client, scheme_id, "Car")
        wheel = _create_class(client, scheme_id, "Wheel")
        road = _create_class(client, scheme_id, "Road")
        created = []
        for source, target, rel_type in [
            (car, wheel, "has_part"),
            (car, road, "drives_on"),
            (wheel, road, "touches"),
        ]:
            response = client.post(
                "/api/relationships",
                json={
                    "source_id": source["id"],
                    "target_id": target["id"],
                    "relationship_type": rel_type,
                },
            )
            assert response.status_code == status.HTTP_201_CREATED, response.text
            created.append(response.json())
        return created

    def test_q_matches_source_title(self, client, relationships):
        body = client.get("/api/relationships", params={"q": "car"}).json()
        assert body["total"] == 2

    def test_q_matches_target_title_without_duplicates(self, client, relationships):
        # "Road" is the target of two relationships; "Wheel" is both a source and a target.
        assert client.get("/api/relationships", params={"q": "road"}).json()["total"] == 2
        body = client.get("/api/relationships", params={"q": "wheel"}).json()
        assert body["total"] == 2
        assert len({r["id"] for r in body["items"]}) == 2

    def test_q_matches_property_identifier_and_title(self, client, relationships):
        assert client.get("/api/relationships", params={"q": "has_part"}).json()["total"] == 1
        assert client.get("/api/relationships", params={"q": "Drives On"}).json()["total"] == 1

    def test_total_under_q_with_small_limit(self, client, relationships):
        body = client.get("/api/relationships", params={"q": "a", "limit": 1}).json()
        # "Car" matches two; "Road" (target of the third) matches too.
        assert body["total"] == 3
        assert len(body["items"]) == 1


class TestTaxonomyAndSchemeQueryMatchesIdentifier:
    """GET /api/taxonomies and /api/schemes q also match the identifier."""

    def test_taxonomy_q_matches_identifier(self, client):
        client.post("/api/taxonomies", json={"title": "Vehicles", "identifier": "tx_auto"})
        client.post("/api/taxonomies", json={"title": "Plants"})
        body = client.get("/api/taxonomies", params={"q": "TX_AUTO"}).json()
        assert [t["title"] for t in body["items"]] == ["Vehicles"]
        assert body["total"] == 1

    def test_scheme_q_matches_identifier(self, client):
        tax = client.post("/api/taxonomies", json={"title": "T"}).json()
        client.post(
            f"/api/taxonomies/{tax['id']}/schemes",
            json={"title": "Engines", "identifier": "sc_motor"},
        )
        client.post(f"/api/taxonomies/{tax['id']}/schemes", json={"title": "Tyres"})
        body = client.get("/api/schemes", params={"q": "motor"}).json()
        assert [s["title"] for s in body["items"]] == ["Engines"]
        assert body["total"] == 1

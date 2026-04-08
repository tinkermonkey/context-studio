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

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from domain.ontology.services import OntologyService
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.in_process import InProcessEventPublisher
from adapters.web.ontology_routes import router


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
    return SentenceTransformerEmbedding(model_name="all-MiniLM-L12-v2")


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
        response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy",
            "description": "A test taxonomy"
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_taxonomy_response_structure(self, client):
        """POST /api/taxonomies response has correct structure."""
        response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy",
            "description": "A test taxonomy"
        })
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
        create_response = client.post("/api/taxonomies", json={
            "title": "Get Test Taxonomy"
        })
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
        create_response = client.post("/api/taxonomies", json={
            "title": "Update Test Taxonomy"
        })
        taxonomy_id = create_response.json()["id"]

        response = client.put(f"/api/taxonomies/{taxonomy_id}", json={
            "title": "Updated Title",
            "description": "Updated description"
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Title"
        assert body["version"] == 2

    def test_delete_taxonomy_returns_204(self, client):
        """DELETE /api/taxonomies/{id} returns 204."""
        create_response = client.post("/api/taxonomies", json={
            "title": "Delete Test Taxonomy"
        })
        taxonomy_id = create_response.json()["id"]

        response = client.delete(f"/api/taxonomies/{taxonomy_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        response = client.get(f"/api/taxonomies/{taxonomy_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_duplicate_taxonomy_fails(self, client):
        """POST /api/taxonomies with duplicate title returns 409."""
        client.post("/api/taxonomies", json={"title": "Duplicate Title"})

        response = client.post("/api/taxonomies", json={
            "title": "Duplicate Title"
        })
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_taxonomy_with_empty_title_fails(self, client):
        """POST /api/taxonomies with empty title returns 400."""
        response = client.post("/api/taxonomies", json={
            "title": ""
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestConceptSchemeCRUD:
    """Integration tests for concept scheme CRUD operations."""

    def test_create_concept_scheme_returns_201(self, client):
        """POST /api/taxonomies/{id}/schemes returns 201."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme",
            "description": "A test scheme"
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_concept_scheme_response_structure(self, client):
        """POST /api/taxonomies/{id}/schemes response has correct structure."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        body = response.json()

        assert "id" in body
        assert body["title"] == "Test Scheme"
        assert body["taxonomy_id"] == taxonomy_id

    def test_list_concept_schemes_returns_200(self, client):
        """GET /api/schemes returns 200 with list response."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })

        response = client.get("/api/schemes")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert len(body["items"]) > 0

    def test_get_concept_scheme_returns_200(self, client):
        """GET /api/schemes/{id} returns 200 with scheme."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Get Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        response = client.get(f"/api/schemes/{scheme_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == scheme_id

    def test_update_concept_scheme_returns_200(self, client):
        """PUT /api/schemes/{id} returns 200 with updated scheme."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Update Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        response = client.put(f"/api/schemes/{scheme_id}", json={
            "title": "Updated Scheme Title"
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Scheme Title"

    def test_delete_concept_scheme_returns_204(self, client):
        """DELETE /api/schemes/{id} returns 204."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Delete Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        response = client.delete(f"/api/schemes/{scheme_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestClassCRUD:
    """Integration tests for class CRUD operations."""

    def test_create_class_returns_201(self, client):
        """POST /api/schemes/{id}/classes returns 201."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Test Class"
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_class_response_structure(self, client):
        """POST /api/schemes/{id}/classes response has correct structure."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Test Class",
            "description": "A test class"
        })
        body = response.json()

        assert "id" in body
        assert body["title"] == "Test Class"
        assert body["concept_scheme_id"] == scheme_id

    def test_list_classes_returns_200(self, client):
        """GET /api/classes returns 200 with list response."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Test Class"
        })

        response = client.get("/api/classes")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert len(body["items"]) > 0

    def test_get_class_returns_200(self, client):
        """GET /api/classes/{id} returns 200 with class."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Get Test Class"
        })
        class_id = class_response.json()["id"]

        response = client.get(f"/api/classes/{class_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == class_id

    def test_update_class_returns_200(self, client):
        """PUT /api/classes/{id} returns 200 with updated class."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Update Test Class"
        })
        class_id = class_response.json()["id"]

        response = client.put(f"/api/classes/{class_id}", json={
            "title": "Updated Class Title"
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Class Title"

    def test_delete_class_returns_204(self, client):
        """DELETE /api/classes/{id} returns 204."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Delete Test Class"
        })
        class_id = class_response.json()["id"]

        response = client.delete(f"/api/classes/{class_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_move_class_returns_200(self, client):
        """POST /api/classes/{id}/move returns 200 and moves class to new scheme."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme1_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme 1"
        })
        scheme1_id = scheme1_response.json()["id"]

        scheme2_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme 2"
        })
        scheme2_id = scheme2_response.json()["id"]

        class_response = client.post(f"/api/schemes/{scheme1_id}/classes", json={
            "title": "Move Test Class"
        })
        class_id = class_response.json()["id"]

        response = client.post(f"/api/classes/{class_id}/move", json={
            "target_scheme_id": scheme2_id
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["concept_scheme_id"] == scheme2_id


class TestRelationshipCRUD:
    """Integration tests for relationship CRUD operations."""

    def test_create_relationship_returns_201(self, client):
        """POST /api/relationships returns 201."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Class 1"
        })
        class1_id = class1_response.json()["id"]

        class2_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Class 2"
        })
        class2_id = class2_response.json()["id"]

        response = client.post("/api/relationships", json={
            "source_id": class1_id,
            "target_id": class2_id,
            "relationship_type": "related_to"
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_list_relationships_returns_200(self, client):
        """GET /api/relationships returns 200 with list response."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Class 1"
        })
        class1_id = class1_response.json()["id"]

        class2_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Class 2"
        })
        class2_id = class2_response.json()["id"]

        client.post("/api/relationships", json={
            "source_id": class1_id,
            "target_id": class2_id,
            "relationship_type": "related_to"
        })

        response = client.get("/api/relationships")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body

    def test_get_relationship_returns_200(self, client):
        """GET /api/relationships/{id} returns 200 with relationship."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Class 1"
        })
        class1_id = class1_response.json()["id"]

        class2_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Class 2"
        })
        class2_id = class2_response.json()["id"]

        rel_response = client.post("/api/relationships", json={
            "source_id": class1_id,
            "target_id": class2_id,
            "relationship_type": "related_to"
        })
        relationship_id = rel_response.json()["id"]

        response = client.get(f"/api/relationships/{relationship_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == relationship_id
        assert body["source_id"] == class1_id
        assert body["target_id"] == class2_id

    def test_delete_relationship_returns_204(self, client):
        """DELETE /api/relationships/{id} returns 204."""
        tax_response = client.post("/api/taxonomies", json={
            "title": "Test Taxonomy"
        })
        taxonomy_id = tax_response.json()["id"]

        scheme_response = client.post(f"/api/taxonomies/{taxonomy_id}/schemes", json={
            "title": "Test Scheme"
        })
        scheme_id = scheme_response.json()["id"]

        class1_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Class 1"
        })
        class1_id = class1_response.json()["id"]

        class2_response = client.post(f"/api/schemes/{scheme_id}/classes", json={
            "title": "Class 2"
        })
        class2_id = class2_response.json()["id"]

        rel_response = client.post("/api/relationships", json={
            "source_id": class1_id,
            "target_id": class2_id,
            "relationship_type": "related_to"
        })
        relationship_id = rel_response.json()["id"]

        response = client.delete(f"/api/relationships/{relationship_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestPropertyDefinitionCRUD:
    """Integration tests for property definition CRUD operations."""

    def test_create_property_definition_returns_201(self, client):
        """POST /api/properties returns 201."""
        response = client.post("/api/properties", json={
            "identifier": "test_property",
            "title": "Test Property",
            "description": "A test property definition"
        })
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "id" in body

    def test_create_property_definition_response_structure(self, client):
        """POST /api/properties response has correct structure."""
        response = client.post("/api/properties", json={
            "identifier": "test_prop_2",
            "title": "Test Property 2",
            "description": "Another test property"
        })
        body = response.json()

        assert "id" in body
        assert body["identifier"] == "test_prop_2"
        assert body["title"] == "Test Property 2"
        assert body["description"] == "Another test property"

    def test_list_properties_returns_200(self, client):
        """GET /api/properties returns 200 with list response."""
        client.post("/api/properties", json={
            "identifier": "prop1",
            "title": "Property 1"
        })
        client.post("/api/properties", json={
            "identifier": "prop2",
            "title": "Property 2"
        })

        response = client.get("/api/properties")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert len(body["items"]) >= 2

    def test_get_property_definition_returns_200(self, client):
        """GET /api/properties/{id} returns 200 with property definition."""
        create_response = client.post("/api/properties", json={
            "identifier": "get_test_prop",
            "title": "Get Test Property"
        })
        property_id = create_response.json()["id"]

        response = client.get(f"/api/properties/{property_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == property_id
        assert body["identifier"] == "get_test_prop"

    def test_update_property_definition_returns_200(self, client):
        """PUT /api/properties/{id} returns 200 with updated property definition."""
        create_response = client.post("/api/properties", json={
            "identifier": "update_prop",
            "title": "Update Test Property"
        })
        property_id = create_response.json()["id"]

        response = client.put(f"/api/properties/{property_id}", json={
            "identifier": "update_prop",
            "title": "Updated Property Title",
            "description": "Updated description"
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Property Title"
        assert body["description"] == "Updated description"

    def test_delete_property_definition_returns_204(self, client):
        """DELETE /api/properties/{id} returns 204."""
        create_response = client.post("/api/properties", json={
            "identifier": "delete_prop",
            "title": "Delete Test Property"
        })
        property_id = create_response.json()["id"]

        response = client.delete(f"/api/properties/{property_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

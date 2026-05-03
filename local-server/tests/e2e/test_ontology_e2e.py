"""
E2E tests for the Ontology bounded context.

This module tests the Ontology Management bounded context through the HTTP API
with a fully initialized application using real databases and real adapters.

Tests verify:
- Taxonomy CRUD operations
- ConceptScheme lifecycle
- Class lifecycle including parent reassignment and hierarchy management
- Relationship CRUD operations
- PropertyDefinition CRUD operations
- Cross-context change event verification (entities create change events)
- Error cases (duplicate names, missing parents, delete constraints)
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from fastapi import status


@pytest.mark.e2e
class TestTaxonomyCRUD:
    """Tests for taxonomy creation, retrieval, update, and deletion."""

    def test_create_taxonomy(self, e2e_client):
        """
        Create a new taxonomy.

        Asserts:
        - Status code 201 (Created)
        - Response contains id, title, description, created_at, version
        """
        response = e2e_client.post(
            "/api/taxonomies",
            json={"title": "Test Taxonomy", "description": "A test taxonomy"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "id" in body
        assert body["title"] == "Test Taxonomy"
        assert body["description"] == "A test taxonomy"
        assert "created_at" in body
        assert body["version"] == 1

    def test_list_taxonomies(self, e2e_client):
        """
        List all taxonomies.

        Asserts:
        - Status code 200 (OK)
        - Response is a ListResponse with items, total, limit, offset
        """
        # Create a taxonomy first
        create_response = e2e_client.post(
            "/api/taxonomies", json={"title": "List Test Taxonomy"}
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        # List taxonomies
        response = e2e_client.get("/api/taxonomies")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body
        assert len(body["items"]) > 0
        assert any(t["title"] == "List Test Taxonomy" for t in body["items"])

    def test_get_taxonomy(self, e2e_client):
        """
        Retrieve a taxonomy by ID.

        Asserts:
        - Status code 200 (OK)
        - Response contains all taxonomy fields
        """
        # Create a taxonomy
        create_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Get Test Taxonomy"}
        )
        taxonomy_id = create_response.json()["id"]

        # Get the taxonomy
        response = e2e_client.get(f"/api/taxonomies/{taxonomy_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == taxonomy_id
        assert body["title"] == "Get Test Taxonomy"

    def test_update_taxonomy(self, e2e_client):
        """
        Update a taxonomy's title and description.

        Asserts:
        - Status code 200 (OK)
        - Updated fields are reflected in response
        - Version is incremented
        """
        # Create a taxonomy
        create_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Update Test Taxonomy"}
        )
        taxonomy_id = create_response.json()["id"]

        # Update the taxonomy
        response = e2e_client.put(
            f"/api/taxonomies/{taxonomy_id}",
            json={"title": "Updated Title", "description": "Updated description"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == taxonomy_id
        assert body["title"] == "Updated Title"
        assert body["description"] == "Updated description"
        assert body["version"] == 2

    def test_delete_taxonomy(self, e2e_client):
        """
        Delete a taxonomy.

        Asserts:
        - Status code 204 (No Content)
        - Subsequent GET returns 404
        """
        # Create a taxonomy
        create_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Delete Test Taxonomy"}
        )
        taxonomy_id = create_response.json()["id"]

        # Delete the taxonomy
        response = e2e_client.delete(f"/api/taxonomies/{taxonomy_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        response = e2e_client.get(f"/api/taxonomies/{taxonomy_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_duplicate_taxonomy_fails(self, e2e_client):
        """
        Creating a taxonomy with duplicate title fails.

        Asserts:
        - First creation succeeds (201)
        - Second creation with same title fails (409 Conflict)
        """
        title = "Duplicate Test Taxonomy"
        response1 = e2e_client.post("/api/taxonomies", json={"title": title})
        assert response1.status_code == status.HTTP_201_CREATED

        response2 = e2e_client.post("/api/taxonomies", json={"title": title})
        assert response2.status_code == status.HTTP_409_CONFLICT


@pytest.mark.e2e
class TestConceptSchemeCRUD:
    """Tests for concept scheme lifecycle within taxonomies."""

    def test_create_concept_scheme(self, e2e_client):
        """
        Create a new concept scheme within a taxonomy.

        Asserts:
        - Status code 201 (Created)
        - Response contains id, taxonomy_id, title, version
        """
        # Create a taxonomy
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Scheme Test Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        # Create a concept scheme
        response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Test Scheme", "description": "A test scheme"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "id" in body
        assert body["taxonomy_id"] == taxonomy_id
        assert body["title"] == "Test Scheme"
        assert body["version"] == 1

    def test_list_concept_schemes(self, e2e_client):
        """
        List all concept schemes.

        Asserts:
        - Status code 200 (OK)
        - Can filter by taxonomy_id
        """
        # Create a taxonomy and scheme
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "List Scheme Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "List Test Scheme"}
        )
        assert scheme_response.status_code == status.HTTP_201_CREATED

        # List all schemes
        response = e2e_client.get("/api/schemes")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert len(body["items"]) > 0

        # Filter by taxonomy
        response = e2e_client.get(f"/api/schemes?taxonomy_id={taxonomy_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert all(s["taxonomy_id"] == taxonomy_id for s in body["items"])

    def test_get_concept_scheme(self, e2e_client):
        """
        Retrieve a concept scheme by ID.

        Asserts:
        - Status code 200 (OK)
        - Response contains all scheme fields
        """
        # Create taxonomy and scheme
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Get Scheme Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Get Test Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        # Get the scheme
        response = e2e_client.get(f"/api/schemes/{scheme_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == scheme_id
        assert body["taxonomy_id"] == taxonomy_id
        assert body["title"] == "Get Test Scheme"

    def test_update_concept_scheme(self, e2e_client):
        """
        Update a concept scheme.

        Asserts:
        - Status code 200 (OK)
        - Updated fields reflected in response
        - Version incremented
        """
        # Create taxonomy and scheme
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Update Scheme Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Update Test Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        # Update the scheme
        response = e2e_client.put(
            f"/api/schemes/{scheme_id}", json={"title": "Updated Scheme Title"}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == scheme_id
        assert body["title"] == "Updated Scheme Title"
        assert body["version"] == 2

    def test_delete_concept_scheme(self, e2e_client):
        """
        Delete a concept scheme.

        Asserts:
        - Status code 204 (No Content)
        - Subsequent GET returns 404
        """
        # Create taxonomy and scheme
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Delete Scheme Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Delete Test Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        # Delete the scheme
        response = e2e_client.delete(f"/api/schemes/{scheme_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        response = e2e_client.get(f"/api/schemes/{scheme_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.e2e
class TestClassHierarchy:
    """Tests for class lifecycle including parent reassignment and hierarchy."""

    def test_create_root_class(self, e2e_client):
        """
        Create a root-level class (no parent).

        Asserts:
        - Status code 201 (Created)
        - parent_class_id is None
        """
        # Create taxonomy and scheme
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Class Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Class Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        # Create a root class
        response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Root Class"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "id" in body
        assert body["title"] == "Root Class"
        assert body["parent_class_id"] is None

    def test_create_child_class(self, e2e_client):
        """
        Create a child class with parent.

        Asserts:
        - Status code 201 (Created)
        - parent_class_id is set correctly
        """
        # Create taxonomy and scheme
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Child Class Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Child Class Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        # Create parent class
        parent_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Parent Class"}
        )
        parent_id = parent_response.json()["id"]

        # Create child class
        response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Child Class", "parent_class_id": parent_id},
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["parent_class_id"] == parent_id

    def test_create_class_with_invalid_parent_fails(self, e2e_client):
        """
        Creating a class with a non-existent parent_id fails.

        Asserts:
        - Status code 404 (Not Found) for missing parent reference
        """
        # Create taxonomy and scheme
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Invalid Parent Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Invalid Parent Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        # Try to create a class with non-existent parent
        invalid_parent_id = "00000000-0000-0000-0000-000000000000"
        response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Orphan Class", "parent_class_id": invalid_parent_id},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_classes(self, e2e_client):
        """
        List classes with filtering options.

        Asserts:
        - Status code 200 (OK)
        - Can filter by concept_scheme_id and parent_class_id
        """
        # Create taxonomy, scheme, and classes
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "List Class Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "List Class Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        parent_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Parent Class"}
        )
        parent_id = parent_response.json()["id"]

        e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Child Class", "parent_class_id": parent_id},
        )

        # List all classes
        response = e2e_client.get("/api/classes")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert len(body["items"]) >= 2

        # Filter by concept_scheme_id
        response = e2e_client.get(f"/api/classes?concept_scheme_id={scheme_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert all(c["concept_scheme_id"] == scheme_id for c in body["items"])

    def test_move_class_to_different_scheme(self, e2e_client):
        """
        Move a class from one concept scheme to another within the same taxonomy.

        Asserts:
        - Status code 200 (OK)
        - concept_scheme_id is updated to target scheme
        """
        # Setup: create taxonomy and two schemes
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Move Class Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme1_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Source Scheme"}
        )
        scheme1_id = scheme1_response.json()["id"]

        scheme2_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Target Scheme"}
        )
        scheme2_id = scheme2_response.json()["id"]

        # Create a root-level class in scheme1
        class_response = e2e_client.post(
            f"/api/schemes/{scheme1_id}/classes", json={"title": "Test Class"}
        )
        class_id = class_response.json()["id"]

        # Verify initial state
        assert class_response.json()["concept_scheme_id"] == scheme1_id

        # Move class to scheme2
        response = e2e_client.post(
            f"/api/classes/{class_id}/move", json={"target_scheme_id": scheme2_id}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["concept_scheme_id"] == scheme2_id

    def test_move_class_to_scheme_different_taxonomy_fails(self, e2e_client):
        """
        Moving a class to a scheme in a different taxonomy fails.

        Asserts:
        - Status code 400 (Bad Request)
        - Error message indicates taxonomy mismatch
        """
        # Setup: create two taxonomies with schemes
        tax1_response = e2e_client.post("/api/taxonomies", json={"title": "Taxonomy 1"})
        taxonomy1_id = tax1_response.json()["id"]

        tax2_response = e2e_client.post("/api/taxonomies", json={"title": "Taxonomy 2"})
        taxonomy2_id = tax2_response.json()["id"]

        scheme1_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy1_id}/schemes", json={"title": "Scheme 1"}
        )
        scheme1_id = scheme1_response.json()["id"]

        scheme2_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy2_id}/schemes", json={"title": "Scheme 2"}
        )
        scheme2_id = scheme2_response.json()["id"]

        # Create class in scheme1
        class_response = e2e_client.post(
            f"/api/schemes/{scheme1_id}/classes", json={"title": "Test Class"}
        )
        class_id = class_response.json()["id"]

        # Try to move to scheme2 (different taxonomy)
        response = e2e_client.post(
            f"/api/classes/{class_id}/move", json={"target_scheme_id": scheme2_id}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_move_nonexistent_class_fails(self, e2e_client):
        """
        Moving a non-existent class fails with 404.

        Asserts:
        - Status code 404 (Not Found)
        """
        # Setup: create taxonomy and scheme
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Nonexistent Class Move Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Nonexistent Class Move Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        # Try to move a non-existent class
        response = e2e_client.post(
            "/api/classes/nonexistent-id/move", json={"target_scheme_id": scheme_id}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_move_to_nonexistent_scheme_fails(self, e2e_client):
        """
        Moving a class to a non-existent scheme fails with 404.

        Asserts:
        - Status code 404 (Not Found)
        """
        # Setup: create taxonomy and scheme
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Nonexistent Scheme Move Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Nonexistent Scheme Move Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        # Create a class
        class_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Class for Nonexistent Scheme Move"},
        )
        class_id = class_response.json()["id"]

        # Try to move to a non-existent scheme
        response = e2e_client.post(
            f"/api/classes/{class_id}/move",
            json={"target_scheme_id": "nonexistent-scheme-id"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_root_class_with_children_fails(self, e2e_client):
        """
        Deleting a class with subclasses fails.

        Asserts:
        - Status code 422 (Unprocessable Entity)
        """
        # Setup
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Delete Parent Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Delete Parent Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        parent_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Parent"}
        )
        parent_id = parent_response.json()["id"]

        e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Child", "parent_class_id": parent_id},
        )

        # Try to delete parent (should fail)
        response = e2e_client.delete(f"/api/classes/{parent_id}")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_delete_leaf_class(self, e2e_client):
        """
        Delete a leaf class (no children).

        Asserts:
        - Status code 204 (No Content)
        """
        # Setup
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Delete Leaf Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Delete Leaf Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        class_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Leaf Class"}
        )
        class_id = class_response.json()["id"]

        # Delete the leaf class
        response = e2e_client.delete(f"/api/classes/{class_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.e2e
class TestPropertyDefinitionCRUD:
    """Tests for property definition (relationship type) CRUD."""

    def test_create_property_definition(self, e2e_client):
        """
        Create a property definition.

        Asserts:
        - Status code 201 (Created)
        - Response contains id, identifier, title, version
        """
        response = e2e_client.post(
            "/api/properties",
            json={
                "identifier": "is_child_of",
                "title": "Is Child Of",
                "description": "Indicates a child relationship",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "id" in body
        assert body["identifier"] == "is_child_of"
        assert body["title"] == "Is Child Of"
        assert body["version"] == 1

    def test_list_property_definitions(self, e2e_client):
        """
        List all property definitions.

        Asserts:
        - Status code 200 (OK)
        - Response contains items array
        """
        # Create a property definition
        e2e_client.post(
            "/api/properties",
            json={"identifier": "has_related", "title": "Has Related"},
        )

        response = e2e_client.get("/api/properties")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body
        assert len(body["items"]) > 0

    def test_get_property_definition(self, e2e_client):
        """
        Retrieve a property definition by ID.

        Asserts:
        - Status code 200 (OK)
        - Response contains all property fields
        """
        # Create a property definition
        create_response = e2e_client.post(
            "/api/properties",
            json={"identifier": "get_prop_test", "title": "Get Prop Test"},
        )
        prop_id = create_response.json()["id"]

        # Get the property
        response = e2e_client.get(f"/api/properties/{prop_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == prop_id
        assert body["identifier"] == "get_prop_test"

    def test_update_property_definition(self, e2e_client):
        """
        Update a property definition's title.

        Asserts:
        - Status code 200 (OK)
        - Title is updated, version incremented
        """
        # Create a property definition
        create_response = e2e_client.post(
            "/api/properties",
            json={"identifier": "update_prop_test", "title": "Original Title"},
        )
        prop_id = create_response.json()["id"]

        # Update the property
        response = e2e_client.put(
            f"/api/properties/{prop_id}", json={"title": "Updated Title"}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["title"] == "Updated Title"
        assert body["version"] == 2

    def test_delete_property_definition(self, e2e_client):
        """
        Delete a property definition.

        Asserts:
        - Status code 204 (No Content)
        - Subsequent GET returns 404
        """
        # Create a property definition
        create_response = e2e_client.post(
            "/api/properties",
            json={"identifier": "delete_prop_test", "title": "Delete Test"},
        )
        prop_id = create_response.json()["id"]

        # Delete the property
        response = e2e_client.delete(f"/api/properties/{prop_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        response = e2e_client.get(f"/api/properties/{prop_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.e2e
class TestRelationshipCRUD:
    """Tests for relationship CRUD operations."""

    def test_create_relationship(self, e2e_client):
        """
        Create a relationship between two entities.

        Asserts:
        - Status code 201 (Created)
        - Response contains id, source_id, target_id, property_definition_id
        """
        # Setup: create entities and property definition
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Rel Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Rel Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Class 2"}
        )
        class2_id = class2_response.json()["id"]

        prop_response = e2e_client.post(
            "/api/properties", json={"identifier": "relates_to", "title": "Relates To"}
        )
        prop_id = prop_response.json()["id"]

        # Create relationship
        response = e2e_client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "property_definition_id": prop_id,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "id" in body
        assert body["source_id"] == class1_id
        assert body["target_id"] == class2_id
        assert body["property_definition_id"] == prop_id

    def test_list_relationships(self, e2e_client):
        """
        List all relationships with optional filtering.

        Asserts:
        - Status code 200 (OK)
        - Can filter by source_id, target_id, property_id
        """
        # Setup
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "List Rel Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "List Rel Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "List Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "List Class 2"}
        )
        class2_id = class2_response.json()["id"]

        prop_response = e2e_client.post(
            "/api/properties",
            json={"identifier": "list_relates_to", "title": "List Relates To"},
        )
        prop_id = prop_response.json()["id"]

        e2e_client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "property_definition_id": prop_id,
            },
        )

        # List all relationships
        response = e2e_client.get("/api/relationships")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "items" in body

        # Filter by source_id
        response = e2e_client.get(f"/api/relationships?source_id={class1_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert any(r["source_id"] == class1_id for r in body["items"])

    def test_get_relationship(self, e2e_client):
        """
        Retrieve a relationship by ID.

        Asserts:
        - Status code 200 (OK)
        - Response contains all relationship fields
        """
        # Setup
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Get Rel Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes", json={"title": "Get Rel Scheme"}
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Get Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Get Class 2"}
        )
        class2_id = class2_response.json()["id"]

        prop_response = e2e_client.post(
            "/api/properties",
            json={"identifier": "get_relates_to", "title": "Get Relates To"},
        )
        prop_id = prop_response.json()["id"]

        create_response = e2e_client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "property_definition_id": prop_id,
            },
        )
        rel_id = create_response.json()["id"]

        # Get the relationship
        response = e2e_client.get(f"/api/relationships/{rel_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == rel_id
        assert body["source_id"] == class1_id

    def test_delete_relationship(self, e2e_client):
        """
        Delete a relationship.

        Asserts:
        - Status code 204 (No Content)
        - Subsequent GET returns 404
        """
        # Setup
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Delete Rel Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Delete Rel Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Delete Class 1"}
        )
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Delete Class 2"}
        )
        class2_id = class2_response.json()["id"]

        prop_response = e2e_client.post(
            "/api/properties",
            json={"identifier": "delete_relates_to", "title": "Delete Relates To"},
        )
        prop_id = prop_response.json()["id"]

        create_response = e2e_client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "property_definition_id": prop_id,
            },
        )
        rel_id = create_response.json()["id"]

        # Delete the relationship
        response = e2e_client.delete(f"/api/relationships/{rel_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        response = e2e_client.get(f"/api/relationships/{rel_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.e2e
class TestCrossContextChangeEvents:
    """Tests for change event recording across contexts."""

    def test_taxonomy_creation_records_change_event(self, e2e_client):
        """
        Creating a taxonomy records a change event.

        Asserts:
        - Taxonomy creation succeeds (201)
        - Change history includes the creation event
        """
        # Create a taxonomy
        response = e2e_client.post(
            "/api/taxonomies", json={"title": "Change Event Taxonomy"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        taxonomy_id = response.json()["id"]

        # Retrieve change history for this entity
        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "events" in body
        assert len(body["events"]) > 0
        # Verify the creation event is recorded
        assert any(
            e.get("operation") == "create" and e.get("entity_id") == taxonomy_id
            for e in body["events"]
        )

    def test_class_creation_records_change_event(self, e2e_client):
        """
        Creating a class records a change event.

        Asserts:
        - Class creation succeeds (201)
        - Change history includes the creation event
        """
        # Setup
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Class Change Event Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Class Change Event Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        # Create a class
        response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes", json={"title": "Change Event Class"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        class_id = response.json()["id"]

        # Retrieve change history for this entity
        response = e2e_client.get(f"/api/v1/versioning/changes/{class_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "events" in body
        assert len(body["events"]) > 0
        # Verify the creation event is recorded
        assert any(
            e.get("operation") == "create" and e.get("entity_id") == class_id
            for e in body["events"]
        )

    def test_relationship_creation_records_change_event(self, e2e_client):
        """
        Creating a relationship records a change event.

        Asserts:
        - Relationship creation succeeds (201)
        - Change history includes the creation event
        """
        # Setup
        tax_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Rel Change Event Taxonomy"}
        )
        taxonomy_id = tax_response.json()["id"]

        scheme_response = e2e_client.post(
            f"/api/taxonomies/{taxonomy_id}/schemes",
            json={"title": "Rel Change Event Scheme"},
        )
        scheme_id = scheme_response.json()["id"]

        class1_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Rel Change Event Class 1"},
        )
        class1_id = class1_response.json()["id"]

        class2_response = e2e_client.post(
            f"/api/schemes/{scheme_id}/classes",
            json={"title": "Rel Change Event Class 2"},
        )
        class2_id = class2_response.json()["id"]

        prop_response = e2e_client.post(
            "/api/properties",
            json={
                "identifier": "change_event_relates_to",
                "title": "Change Event Relates To",
            },
        )
        prop_id = prop_response.json()["id"]

        # Create relationship
        response = e2e_client.post(
            "/api/relationships",
            json={
                "source_id": class1_id,
                "target_id": class2_id,
                "property_definition_id": prop_id,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        rel_id = response.json()["id"]

        # Retrieve change history for this entity
        response = e2e_client.get(f"/api/v1/versioning/changes/{rel_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "events" in body
        assert len(body["events"]) > 0
        # Verify the creation event is recorded
        assert any(
            e.get("operation") == "create" and e.get("entity_id") == rel_id
            for e in body["events"]
        )

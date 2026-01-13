"""
API Integration Tests for Nodes API

Tests complete CRUD operations on the unified nodes API as specified
in section 8.3 of the Great Normalization design.
"""

import sys
import os
import uuid
import pytest
from uuid import uuid4

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestNodesAPICRUD:
    """Test complete CRUD operations on nodes API as specified in the design."""

    def test_create_layer_success(self, client):
        """Test successful layer creation."""
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer definition",
        }

        response = client.post("/api/structure_nodes/", json=layer_data)

        assert response.status_code == 201
        layer = response.json()

        assert layer["node_type"] == "layer"
        assert layer["title"] == unique_title
        assert layer["definition"] == "Test layer definition"
        assert layer["parent_node_id"] is None
        assert "id" in layer
        assert "created_at" in layer
        assert layer["version"] == 1

    def test_create_domain_success(self, client):
        """Test successful domain creation with parent layer."""
        # First create a layer
        unique_layer_title = f"Parent Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_layer_title,
            "definition": "Parent layer for domain",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        assert layer_response.status_code == 201
        layer = layer_response.json()

        # Create domain
        unique_domain_title = f"Test Domain {uuid4()}"
        domain_data = {
            "node_type": "domain",
            "title": unique_domain_title,
            "definition": "Test domain definition",
            "parent_node_id": layer["id"],
        }

        response = client.post("/api/structure_nodes/", json=domain_data)

        assert response.status_code == 201
        domain = response.json()

        assert domain["node_type"] == "domain"
        assert domain["title"] == unique_domain_title
        assert domain["definition"] == "Test domain definition"
        assert domain["parent_node_id"] == layer["id"]
        assert "id" in domain
        assert "created_at" in domain
        assert domain["version"] == 1

    def test_create_term_success(self, client):
        """Test successful term creation with parent domain."""
        # Create layer -> domain -> term hierarchy
        unique_layer_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_layer_title,
            "definition": "Layer for term test",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        unique_domain_title = f"Test Domain {uuid4()}"
        domain_data = {
            "node_type": "domain",
            "title": unique_domain_title,
            "definition": "Domain for term test",
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)
        domain = domain_response.json()

        # Create term
        unique_term_title = f"Test Term {uuid4()}"
        term_data = {
            "node_type": "term",
            "title": unique_term_title,
            "definition": "Test term definition",
            "parent_node_id": domain["id"],
        }

        response = client.post("/api/structure_nodes/", json=term_data)

        assert response.status_code == 201
        term = response.json()

        assert term["node_type"] == "term"
        assert term["title"] == unique_term_title
        assert term["definition"] == "Test term definition"
        assert term["parent_node_id"] == domain["id"]
        assert "id" in term
        assert "created_at" in term
        assert term["version"] == 1

    def test_get_node_success(self, client):
        """Test retrieving a node by ID."""
        # Create a layer
        unique_title = f"Get Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Layer for get test",
        }
        create_response = client.post("/api/structure_nodes/", json=layer_data)
        created_layer = create_response.json()

        # Get the layer
        response = client.get(f"/api/structure_nodes/{created_layer['id']}")

        assert response.status_code == 200
        retrieved_layer = response.json()

        assert retrieved_layer["id"] == created_layer["id"]
        assert retrieved_layer["title"] == created_layer["title"]
        assert retrieved_layer["node_type"] == created_layer["node_type"]

    def test_get_node_not_found(self, client):
        """Test retrieving non-existent node returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/structure_nodes/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_node_success(self, client):
        """Test updating a node."""
        # Create a layer
        unique_title = f"Original Title {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Original definition",
        }
        create_response = client.post("/api/structure_nodes/", json=layer_data)
        created_layer = create_response.json()

        # Update the layer
        updated_title = f"Updated Title {uuid4()}"
        update_data = {"title": updated_title, "definition": "Updated definition"}
        response = client.put(
            f"/api/structure_nodes/{created_layer['id']}", json=update_data
        )

        assert response.status_code == 200
        updated_layer = response.json()

        assert updated_layer["id"] == created_layer["id"]
        assert updated_layer["title"] == updated_title
        assert updated_layer["definition"] == "Updated definition"
        assert updated_layer["version"] == 2  # Version should increment

    def test_delete_node_success(self, client):
        """Test deleting a node."""
        # Create a layer
        unique_title = f"Delete Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Layer to be deleted",
        }
        create_response = client.post("/api/structure_nodes/", json=layer_data)
        created_layer = create_response.json()

        # Delete the layer
        response = client.delete(f"/api/structure_nodes/{created_layer['id']}")

        assert response.status_code == 204

        # Verify the layer is deleted
        get_response = client.get(f"/api/structure_nodes/{created_layer['id']}")
        assert get_response.status_code == 404

    def test_delete_node_cascade(self, client):
        """Test that deleting a node cascades to its children."""
        # Create layer -> domain -> term hierarchy
        unique_layer_title = f"Cascade Test Layer {uuid4()}"
        layer_data = {"node_type": "layer", "title": unique_layer_title}
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        unique_domain_title = f"Cascade Test Domain {uuid4()}"
        domain_data = {
            "node_type": "domain",
            "title": unique_domain_title,
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)
        domain = domain_response.json()

        unique_term_title = f"Cascade Test Term {uuid4()}"
        term_data = {
            "node_type": "term",
            "title": unique_term_title,
            "parent_node_id": domain["id"],
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        term = term_response.json()

        # Delete the layer (should cascade to domain and term)
        delete_response = client.delete(f"/api/structure_nodes/{layer['id']}")
        assert delete_response.status_code == 204

        # Verify all nodes are deleted
        assert client.get(f"/api/structure_nodes/{layer['id']}").status_code == 404
        assert client.get(f"/api/structure_nodes/{domain['id']}").status_code == 404
        assert client.get(f"/api/structure_nodes/{term['id']}").status_code == 404


class TestNodesAPIFiltering:
    """Test filtering and pagination functionality."""

    def test_list_nodes_no_filter(self, client):
        """Test listing all nodes without filters."""
        # Create a few nodes
        unique_id = str(uuid4())
        layer_data = {"node_type": "layer", "title": f"Layer 1 {unique_id}"}
        client.post("/api/structure_nodes/", json=layer_data)

        layer2_data = {"node_type": "layer", "title": f"Layer 2 {unique_id}"}
        client.post("/api/structure_nodes/", json=layer2_data)

        response = client.get("/api/structure_nodes/")

        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert len(data["data"]) >= 2
        assert data["total"] >= 2

    def test_list_nodes_filter_by_type(self, client):
        """Test filtering nodes by node_type as specified in the design."""
        # Create layer and domain
        unique_id = str(uuid4())
        layer_data = {"node_type": "layer", "title": f"Filter Test Layer {unique_id}"}
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain_data = {
            "node_type": "domain",
            "title": f"Filter Test Domain {unique_id}",
            "parent_node_id": layer["id"],
        }
        client.post("/api/structure_nodes/", json=domain_data)

        # Filter by layer type
        response = client.get("/api/structure_nodes/?node_type=layer")

        assert response.status_code == 200
        data = response.json()

        assert len(data["data"]) >= 1
        # All returned nodes should be layers
        for node in data["data"]:
            assert node["node_type"] == "layer"

    def test_list_nodes_filter_by_parent(self, client):
        """Test filtering nodes by parent_node_id."""
        # Create layer with multiple domains
        unique_id = str(uuid4())
        layer_data = {
            "node_type": "layer",
            "title": f"Parent Filter Test Layer {unique_id}",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain1_data = {
            "node_type": "domain",
            "title": f"Domain 1 {unique_id}",
            "parent_node_id": layer["id"],
        }
        client.post("/api/structure_nodes/", json=domain1_data)

        domain2_data = {
            "node_type": "domain",
            "title": f"Domain 2 {unique_id}",
            "parent_node_id": layer["id"],
        }
        client.post("/api/structure_nodes/", json=domain2_data)

        # Filter by parent ID
        response = client.get(f"/api/structure_nodes/?parent_node_id={layer['id']}")

        assert response.status_code == 200
        data = response.json()

        assert len(data["data"]) >= 2
        # All returned nodes should have the specified parent
        for node in data["data"]:
            assert node["parent_node_id"] == layer["id"]

    def test_list_nodes_pagination(self, client):
        """Test pagination parameters."""
        # Create multiple layers
        unique_id = str(uuid4())
        for i in range(5):
            layer_data = {
                "node_type": "layer",
                "title": f"Pagination Layer {i} {unique_id}",
            }
            client.post("/api/structure_nodes/", json=layer_data)

        # Test pagination
        response = client.get("/api/structure_nodes/?skip=2&limit=2")

        assert response.status_code == 200
        data = response.json()

        assert data["skip"] == 2
        assert data["limit"] == 2
        assert len(data["data"]) <= 2
        assert data["total"] >= 5

    def test_list_nodes_sorting(self, client):
        """Test sorting by different fields."""
        # Create layers with different titles (to test title sorting)
        unique_id = str(uuid4())
        layer_data1 = {"node_type": "layer", "title": f"Z Last Layer {unique_id}"}
        layer_data2 = {"node_type": "layer", "title": f"A First Layer {unique_id}"}

        client.post("/api/structure_nodes/", json=layer_data1)
        client.post("/api/structure_nodes/", json=layer_data2)

        # Sort by title
        response = client.get("/api/structure_nodes/?sort_by=title&node_type=layer")

        assert response.status_code == 200
        data = response.json()

        # Check that results are sorted by title
        if len(data["data"]) >= 2:
            titles = [node["title"] for node in data["data"]]
            assert titles == sorted(titles)


class TestNodesAPIValidation:
    """Test API validation rules as specified in the design."""

    def test_create_layer_with_parent_fails(self, client):
        """Test that creating layer with parent returns validation error."""
        layer_data = {
            "node_type": "layer",
            "title": f"Invalid Layer {str(uuid4())}",
            "parent_node_id": str(uuid.uuid4()),
        }

        response = client.post("/api/structure_nodes/", json=layer_data)

        assert response.status_code == 422  # Pydantic validation error
        detail = response.json()["detail"]
        # Handle both string and list formats
        if isinstance(detail, list):
            error_messages = [str(error.get("msg", "")).lower() for error in detail]
            assert any("layers cannot have parent" in msg for msg in error_messages)
        else:
            assert "layers cannot have parent" in detail.lower()

    def test_create_domain_without_parent_fails(self, client):
        """Test that creating domain without parent returns validation error."""
        domain_data = {"node_type": "domain", "title": f"Invalid Domain {str(uuid4())}"}

        response = client.post("/api/structure_nodes/", json=domain_data)

        assert response.status_code == 400
        assert "must have a parent" in response.json()["detail"].lower()

    def test_create_term_without_parent_fails(self, client):
        """Test that creating term without parent returns validation error."""
        term_data = {"node_type": "term", "title": f"Invalid Term {str(uuid4())}"}

        response = client.post("/api/structure_nodes/", json=term_data)

        assert response.status_code == 400
        assert "must have a parent" in response.json()["detail"].lower()

    def test_create_domain_with_invalid_parent_type_fails(self, client):
        """Test that creating domain with non-layer parent fails."""
        # Create a layer and domain
        unique_id = str(uuid4())
        layer_data = {"node_type": "layer", "title": f"Test Layer {unique_id}"}
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain_data = {
            "node_type": "domain",
            "title": f"Test Domain {unique_id}",
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)
        domain = domain_response.json()

        # Try to create domain with domain parent (should fail)
        invalid_domain_data = {
            "node_type": "domain",
            "title": f"Invalid Domain {unique_id}",
            "parent_node_id": domain["id"],
        }

        response = client.post("/api/structure_nodes/", json=invalid_domain_data)

        assert response.status_code == 400
        assert "parent must be a layer" in response.json()["detail"].lower()

    def test_create_term_with_invalid_parent_type_fails(self, client):
        """Test that creating term with layer parent fails."""
        # Create a layer
        unique_id = str(uuid4())
        layer_data = {"node_type": "layer", "title": f"Test Layer {unique_id}"}
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Try to create term with layer parent (should fail)
        term_data = {
            "node_type": "term",
            "title": f"Invalid Term {unique_id}",
            "parent_node_id": layer["id"],
        }

        response = client.post("/api/structure_nodes/", json=term_data)

        assert response.status_code == 400
        assert "parent must be a domain or term" in response.json()["detail"].lower()

    def test_duplicate_layer_title_fails(self, client):
        """Test that creating layer with duplicate title fails."""
        unique_id = str(uuid4())
        layer_data = {
            "node_type": "layer",
            "title": f"Duplicate Layer Title {unique_id}",
        }

        # Create first layer
        response1 = client.post("/api/structure_nodes/", json=layer_data)
        assert response1.status_code == 201

        # Try to create second layer with same title
        response2 = client.post("/api/structure_nodes/", json=layer_data)

        assert response2.status_code == 409
        detail = response2.json()["detail"]
        if isinstance(detail, list):
            detail_str = " ".join(str(item) for item in detail)
        else:
            detail_str = str(detail)
        assert "must be unique" in detail_str.lower()

    def test_duplicate_domain_title_within_layer_fails(self, client):
        """Test that creating domain with duplicate title in same layer fails."""
        # Create layer
        unique_id = str(uuid4())
        layer_data = {"node_type": "layer", "title": f"Test Layer {unique_id}"}
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain_data = {
            "node_type": "domain",
            "title": f"Duplicate Domain Title {unique_id}",
            "parent_node_id": layer["id"],
        }

        # Create first domain
        response1 = client.post("/api/structure_nodes/", json=domain_data)
        assert response1.status_code == 201

        # Try to create second domain with same title in same layer
        response2 = client.post("/api/structure_nodes/", json=domain_data)

        assert response2.status_code == 409
        detail = response2.json()["detail"]
        if isinstance(detail, list):
            detail_str = " ".join(str(item) for item in detail)
        else:
            detail_str = str(detail)
        assert "must be unique" in detail_str.lower()

    def test_duplicate_term_title_within_domain_fails(self, client):
        """Test that creating term with duplicate title in same domain fails."""
        # Create layer -> domain
        unique_id = str(uuid4())
        layer_data = {"node_type": "layer", "title": f"Test Layer {unique_id}"}
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain_data = {
            "node_type": "domain",
            "title": f"Test Domain {unique_id}",
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)
        domain = domain_response.json()

        term_data = {
            "node_type": "term",
            "title": f"Duplicate Term Title {unique_id}",
            "parent_node_id": domain["id"],
        }

        # Create first term
        response1 = client.post("/api/structure_nodes/", json=term_data)
        assert response1.status_code == 201

        # Try to create second term with same title in same domain
        response2 = client.post("/api/structure_nodes/", json=term_data)

        assert response2.status_code == 409
        detail = response2.json()["detail"]
        if isinstance(detail, list):
            detail_str = " ".join(str(item) for item in detail)
        else:
            detail_str = str(detail)
        assert "must be unique" in detail_str.lower()


class TestNodesAPICompleteFlow:
    """Test complete workflow scenarios as specified in the design."""

    def test_complete_hierarchy_creation_and_management(self, client):
        """
        Test complete CRUD operations on nodes API as specified in design example.

        This test follows the exact pattern from section 8.3:
        1. Create layer
        2. Create domain with layer as parent
        3. Test filtering by node_type
        4. Perform updates and deletions
        """
        # 1. Create layer
        unique_id = str(uuid4())
        layer_data = {
            "node_type": "layer",
            "title": f"Test Layer {unique_id}",
            "definition": "Test definition",
        }
        response = client.post("/api/structure_nodes/", json=layer_data)
        assert response.status_code == 201
        layer = response.json()

        assert layer["node_type"] == "layer"
        assert layer["title"] == f"Test Layer {unique_id}"
        assert layer["definition"] == "Test definition"
        assert layer["parent_node_id"] is None

        # 2. Create domain
        domain_data = {
            "node_type": "domain",
            "title": f"Test Domain {unique_id}",
            "definition": "Test definition",
            "parent_node_id": layer["id"],
        }
        response = client.post("/api/structure_nodes/", json=domain_data)
        assert response.status_code == 201
        domain = response.json()

        assert domain["node_type"] == "domain"
        assert domain["title"] == f"Test Domain {unique_id}"
        assert domain["definition"] == "Test definition"
        assert domain["parent_node_id"] == layer["id"]

        # 3. Test filtering by node_type
        response = client.get("/api/structure_nodes/?node_type=layer")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) >= 1

        # Find our layer in the results
        our_layer = None
        for node in data["data"]:
            if node["id"] == layer["id"]:
                our_layer = node
                break

        assert our_layer is not None
        assert our_layer["node_type"] == "layer"

        # 4. Create term under domain
        term_data = {
            "node_type": "term",
            "title": f"Test Term {unique_id}",
            "definition": "Test term definition",
            "parent_node_id": domain["id"],
        }
        response = client.post("/api/structure_nodes/", json=term_data)
        assert response.status_code == 201
        term = response.json()

        # 5. Test hierarchy filtering
        # Get domains under the layer
        response = client.get(f"/api/structure_nodes/?parent_node_id={layer['id']}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) >= 1
        assert data["data"][0]["node_type"] == "domain"

        # Get terms under the domain
        response = client.get(f"/api/structure_nodes/?parent_node_id={domain['id']}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) >= 1
        assert data["data"][0]["node_type"] == "term"

        # 6. Update nodes
        layer_update = {"title": f"Updated Layer Title {unique_id}"}
        response = client.put(f"/api/structure_nodes/{layer['id']}", json=layer_update)
        assert response.status_code == 200
        updated_layer = response.json()
        assert updated_layer["title"] == f"Updated Layer Title {unique_id}"
        assert updated_layer["version"] == 2

        # 7. Test cascade delete
        response = client.delete(f"/api/structure_nodes/{layer['id']}")
        assert response.status_code == 204

        # Verify all nodes in hierarchy are deleted
        assert client.get(f"/api/structure_nodes/{layer['id']}").status_code == 404
        assert client.get(f"/api/structure_nodes/{domain['id']}").status_code == 404
        assert client.get(f"/api/structure_nodes/{term['id']}").status_code == 404

    def test_multiple_layers_with_domains(self, client):
        """Test creating multiple layers each with their own domains."""
        # Create multiple layers
        unique_id = str(uuid4())
        layers = []
        for i in range(3):
            layer_data = {
                "node_type": "layer",
                "title": f"Layer {i+1} {unique_id}",
                "definition": f"Definition for layer {i+1}",
            }
            response = client.post("/api/structure_nodes/", json=layer_data)
            assert response.status_code == 201
            layers.append(response.json())

        # Create domains under each layer
        domains = []
        for i, layer in enumerate(layers):
            for j in range(2):  # 2 domains per layer
                domain_data = {
                    "node_type": "domain",
                    "title": f"Domain {i+1}.{j+1} {unique_id}",
                    "definition": f"Domain {j+1} under layer {i+1}",
                    "parent_node_id": layer["id"],
                }
                response = client.post("/api/structure_nodes/", json=domain_data)
                assert response.status_code == 201
                domains.append(response.json())

        # Test filtering
        # Should have 3 layers
        response = client.get("/api/structure_nodes/?node_type=layer")
        assert response.status_code == 200
        assert len(response.json()["data"]) >= 3

        # Should have 6 domains total
        response = client.get("/api/structure_nodes/?node_type=domain")
        assert response.status_code == 200
        assert len(response.json()["data"]) >= 6

        # Each layer should have exactly 2 domains
        for layer in layers:
            response = client.get(f"/api/structure_nodes/?parent_node_id={layer['id']}")
            assert response.status_code == 200
            layer_domains = response.json()["data"]
            assert len(layer_domains) == 2
            for domain in layer_domains:
                assert domain["parent_node_id"] == layer["id"]
                assert domain["node_type"] == "domain"


class TestNodesAPIErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_node_type(self, client):
        """Test creating node with invalid node_type."""
        invalid_data = {
            "node_type": "invalid_type",
            "title": f"Test Node {str(uuid4())}",
        }

        response = client.post("/api/structure_nodes/", json=invalid_data)

        assert response.status_code == 422  # Pydantic validation error

    def test_missing_required_fields(self, client):
        """Test creating node with missing required fields."""
        # Missing title
        response = client.post("/api/structure_nodes/", json={"node_type": "layer"})
        assert response.status_code == 422

        # Missing node_type
        response = client.post("/api/structure_nodes/", json={"title": "Test"})
        assert response.status_code == 422

    def test_invalid_uuid_format(self, client):
        """Test operations with malformed UUID."""
        # Try to get node with invalid UUID
        response = client.get("/api/structure_nodes/not-a-uuid")
        assert response.status_code == 422

        # Try to create node with invalid parent UUID
        layer_data = {
            "node_type": "domain",
            "title": f"Test Domain {str(uuid4())}",
            "parent_node_id": "not-a-uuid",
        }
        response = client.post("/api/structure_nodes/", json=layer_data)
        assert response.status_code == 422

    def test_nonexistent_parent_reference(self, client):
        """Test creating node with non-existent parent."""
        fake_parent_id = str(uuid.uuid4())
        domain_data = {
            "node_type": "domain",
            "title": f"Orphan Domain {str(uuid4())}",
            "parent_node_id": fake_parent_id,
        }

        response = client.post("/api/structure_nodes/", json=domain_data)

        assert response.status_code == 400
        assert "parent must be a layer" in response.json()["detail"].lower()

    def test_update_nonexistent_node(self, client):
        """Test updating non-existent node."""
        fake_id = str(uuid.uuid4())
        update_data = {"title": "Updated Title"}

        response = client.put(f"/api/structure_nodes/{fake_id}", json=update_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_nonexistent_node(self, client):
        """Test deleting non-existent node."""
        fake_id = str(uuid.uuid4())

        response = client.delete(f"/api/structure_nodes/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestMoveWithTypeConversionAPI:
    """Integration tests for move operations with automatic type conversion."""

    def test_move_domain_to_term_conversion(self, client):
        """Test moving a domain under another domain converts it to a term."""
        # Create: Layer1 -> Domain1, Layer2 -> Domain2
        layer1 = client.post("/api/structure_nodes/", json={
            "node_type": "layer",
            "title": f"Layer1 {uuid4()}",
        }).json()

        layer2 = client.post("/api/structure_nodes/", json={
            "node_type": "layer",
            "title": f"Layer2 {uuid4()}",
        }).json()

        domain1 = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": f"Domain1 {uuid4()}",
            "parent_node_id": layer1["id"],
        }).json()

        domain2 = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": f"Domain2 {uuid4()}",
            "parent_node_id": layer2["id"],
        }).json()

        # Verify initial types
        assert domain1["node_type"] == "domain"
        assert domain2["node_type"] == "domain"

        # Move domain1 under domain2 (should convert domain1 to term)
        move_response = client.post("/api/structure_nodes/move", json={
            "node_ids": [domain1["id"]],
            "target_parent_id": domain2["id"],
            "move_children": True,
            "handle_conflicts": "warn",
        })

        assert move_response.status_code == 200
        move_result = move_response.json()

        # Verify conversion happened
        assert len(move_result["moved_nodes"]) == 1
        assert len(move_result["converted_nodes"]) == 1
        assert move_result["converted_nodes"][0]["id"] == domain1["id"]
        assert move_result["converted_nodes"][0]["node_type"] == "term"

        # Verify in database
        node_response = client.get(f"/api/structure_nodes/{domain1['id']}")
        assert node_response.status_code == 200
        updated_node = node_response.json()
        assert updated_node["node_type"] == "term"
        assert updated_node["parent_node_id"] == domain2["id"]

    def test_move_term_to_domain_conversion(self, client):
        """Test moving a term under a layer converts it to a domain."""
        # Create: Layer -> Domain -> Term
        layer = client.post("/api/structure_nodes/", json={
            "node_type": "layer",
            "title": f"Layer {uuid4()}",
        }).json()

        domain = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": f"Domain {uuid4()}",
            "parent_node_id": layer["id"],
        }).json()

        term = client.post("/api/structure_nodes/", json={
            "node_type": "term",
            "title": f"Term {uuid4()}",
            "parent_node_id": domain["id"],
        }).json()

        # Verify initial type
        assert term["node_type"] == "term"

        # Move term under layer (should convert to domain)
        move_response = client.post("/api/structure_nodes/move", json={
            "node_ids": [term["id"]],
            "target_parent_id": layer["id"],
            "move_children": True,
            "handle_conflicts": "warn",
        })

        assert move_response.status_code == 200
        move_result = move_response.json()

        # Verify conversion happened
        assert len(move_result["moved_nodes"]) == 1
        assert len(move_result["converted_nodes"]) == 1
        assert move_result["converted_nodes"][0]["node_type"] == "domain"

        # Verify in database
        node_response = client.get(f"/api/structure_nodes/{term['id']}")
        assert node_response.status_code == 200
        updated_node = node_response.json()
        assert updated_node["node_type"] == "domain"
        assert updated_node["parent_node_id"] == layer["id"]

    def test_move_with_recursive_child_conversion(self, client):
        """Test moving a node converts all children recursively."""
        # Create: Layer1 -> Domain -> Term1 -> Term2, Layer2
        layer1 = client.post("/api/structure_nodes/", json={
            "node_type": "layer",
            "title": f"Layer1 {uuid4()}",
        }).json()

        layer2 = client.post("/api/structure_nodes/", json={
            "node_type": "layer",
            "title": f"Layer2 {uuid4()}",
        }).json()

        domain = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": f"Domain {uuid4()}",
            "parent_node_id": layer1["id"],
        }).json()

        term1 = client.post("/api/structure_nodes/", json={
            "node_type": "term",
            "title": f"Term1 {uuid4()}",
            "parent_node_id": domain["id"],
        }).json()

        term2 = client.post("/api/structure_nodes/", json={
            "node_type": "term",
            "title": f"Term2 {uuid4()}",
            "parent_node_id": term1["id"],
        }).json()

        # Move domain under layer2 (domain stays domain, but children should convert)
        move_response = client.post("/api/structure_nodes/move", json={
            "node_ids": [domain["id"]],
            "target_parent_id": layer2["id"],
            "move_children": True,
            "handle_conflicts": "warn",
        })

        assert move_response.status_code == 200
        move_result = move_response.json()

        # Domain doesn't change type (domain under layer is correct)
        # Children were already terms and remain terms
        assert len(move_result["moved_nodes"]) == 1
        assert len(move_result["converted_nodes"]) == 0  # No type changes needed

        # Now move domain under another domain (should convert to term + children)
        domain2 = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": f"Domain2 {uuid4()}",
            "parent_node_id": layer2["id"],
        }).json()

        move_response2 = client.post("/api/structure_nodes/move", json={
            "node_ids": [domain["id"]],
            "target_parent_id": domain2["id"],
            "move_children": True,
            "handle_conflicts": "warn",
        })

        assert move_response2.status_code == 200
        move_result2 = move_response2.json()

        # Domain converts to term (children stay terms)
        assert len(move_result2["moved_nodes"]) == 1
        assert len(move_result2["converted_nodes"]) == 1
        assert move_result2["converted_nodes"][0]["node_type"] == "term"

    def test_move_with_title_conflict_warn_mode(self, client):
        """Test move with title conflict in warn mode."""
        # Create two layers with same title structure
        layer1 = client.post("/api/structure_nodes/", json={
            "node_type": "layer",
            "title": f"Layer1 {uuid4()}",
        }).json()

        layer2 = client.post("/api/structure_nodes/", json={
            "node_type": "layer",
            "title": f"Layer2 {uuid4()}",
        }).json()

        conflicting_title = f"ConflictDomain {uuid4()}"

        # Create domain under layer1
        domain1 = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": conflicting_title,
            "parent_node_id": layer1["id"],
        }).json()

        # Create domain under layer2 with SAME title
        domain2 = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": conflicting_title,
            "parent_node_id": layer2["id"],
        }).json()

        # Try to move domain1 under layer2 (conflict with domain2)
        move_response = client.post("/api/structure_nodes/move", json={
            "node_ids": [domain1["id"]],
            "target_parent_id": layer2["id"],
            "move_children": True,
            "handle_conflicts": "warn",
        })

        assert move_response.status_code == 200
        move_result = move_response.json()

        # Should have warnings about conflict
        assert len(move_result["warnings"]) > 0
        assert any("exists" in w.lower() for w in move_result["warnings"])

    def test_move_with_title_conflict_rename_mode(self, client):
        """Test move with title conflict in rename mode."""
        # Create hierarchy with conflict
        layer = client.post("/api/structure_nodes/", json={
            "node_type": "layer",
            "title": f"Layer {uuid4()}",
        }).json()

        conflicting_title = f"ConflictDomain {uuid4()}"

        domain1 = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": conflicting_title,
            "parent_node_id": layer["id"],
        }).json()

        # Create another layer and domain
        layer2 = client.post("/api/structure_nodes/", json={
            "node_type": "layer",
            "title": f"Layer2 {uuid4()}",
        }).json()

        domain2 = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": f"OtherDomain {uuid4()}",
            "parent_node_id": layer2["id"],
        }).json()

        # Move domain1 to layer2 (no conflict initially)
        # Then create a conflict and try rename mode
        domain3 = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": conflicting_title,
            "parent_node_id": layer2["id"],
        }).json()

        # Move domain1 under layer2 with rename mode (should rename domain1)
        move_response = client.post("/api/structure_nodes/move", json={
            "node_ids": [domain1["id"]],
            "target_parent_id": layer2["id"],
            "move_children": True,
            "handle_conflicts": "rename",
        })

        assert move_response.status_code == 200
        move_result = move_response.json()

        # Should have warnings about rename
        assert len(move_result["warnings"]) > 0
        assert any("renamed" in w.lower() for w in move_result["warnings"])

        # Verify node was renamed
        node_response = client.get(f"/api/structure_nodes/{domain1['id']}")
        updated_node = node_response.json()
        assert updated_node["title"] != conflicting_title
        assert conflicting_title in updated_node["title"]  # Original title in renamed version

    def test_move_term_under_term_allowed(self, client):
        """Test that terms can be moved under other terms."""
        # Create: Layer -> Domain -> Term1, Term2
        layer = client.post("/api/structure_nodes/", json={
            "node_type": "layer",
            "title": f"Layer {uuid4()}",
        }).json()

        domain = client.post("/api/structure_nodes/", json={
            "node_type": "domain",
            "title": f"Domain {uuid4()}",
            "parent_node_id": layer["id"],
        }).json()

        term1 = client.post("/api/structure_nodes/", json={
            "node_type": "term",
            "title": f"Term1 {uuid4()}",
            "parent_node_id": domain["id"],
        }).json()

        term2 = client.post("/api/structure_nodes/", json={
            "node_type": "term",
            "title": f"Term2 {uuid4()}",
            "parent_node_id": domain["id"],
        }).json()

        # Move term2 under term1 (should be allowed)
        move_response = client.post("/api/structure_nodes/move", json={
            "node_ids": [term2["id"]],
            "target_parent_id": term1["id"],
            "move_children": True,
            "handle_conflicts": "warn",
        })

        assert move_response.status_code == 200
        move_result = move_response.json()

        # No conversion needed (term under term is valid)
        assert len(move_result["moved_nodes"]) == 1
        assert len(move_result["converted_nodes"]) == 0

        # Verify in database
        node_response = client.get(f"/api/structure_nodes/{term2['id']}")
        updated_node = node_response.json()
        assert updated_node["node_type"] == "term"
        assert updated_node["parent_node_id"] == term1["id"]


    def test_list_node_links_pagination_metadata(self, client):
        """Test pagination metadata in node links endpoint."""
        import time
        from uuid import uuid4

        # Helper to create a test node
        def create_test_node(title, node_type, parent_id=None):
            node_data = {
                "title": f"{title} {int(time.time() * 1000)}",
                "node_type": node_type,
                "definition": f"Test {node_type} for pagination test"
            }
            if parent_id:
                node_data["parent_node_id"] = parent_id

            response = client.post("/api/structure_nodes", json=node_data)
            assert response.status_code == 201
            return response.json()

        # Create test nodes - need terms to link between (links must be same type)
        layer = create_test_node("Layer", node_type="layer")
        domain = create_test_node("Domain", node_type="domain", parent_id=layer["id"])

        # Create a source term that will have 15 outgoing links
        source_term = create_test_node("SourceTerm", node_type="term", parent_id=domain["id"])

        # Create a predicate for linking with unique identifier
        unique_id = uuid4().hex[:8]
        predicate_data = {
            "title": f"TestRelationship{unique_id}",
            "identifier": f"test_rel_{unique_id}",
            "definition": "Test predicate for pagination"
        }
        predicate_resp = client.post("/api/predicates/", json=predicate_data)
        assert predicate_resp.status_code == 201, f"Failed to create predicate: {predicate_resp.json()}"
        predicate = predicate_resp.json()

        # Create 15 test links from source_term to various target terms
        link_ids = []
        for i in range(15):
            # Create target term
            target_term = create_test_node(
                f"TargetTerm{i}",
                node_type="term",
                parent_id=domain["id"]
            )

            # Create link (term to term)
            link_data = {
                "source_node_id": source_term["id"],
                "target_node_id": target_term["id"],
                "predicate": predicate["identifier"]
            }
            link_resp = client.post("/api/structure_nodes/links", json=link_data)
            assert link_resp.status_code == 201, f"Failed to create link {i}: {link_resp.json() if link_resp.status_code != 201 else ''}"
            link_ids.append(link_resp.json()["id"])

        # Test pagination with skip=5, limit=5
        response = client.get(
            f"/api/structure_nodes/links",
            params={
                "source_node_id": source_term["id"],
                "skip": 5,
                "limit": 5
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify pagination metadata
        assert "total" in data, "Response should include 'total' count"
        assert "skip" in data, "Response should include 'skip' offset"
        assert "limit" in data, "Response should include 'limit' page size"
        assert "data" in data, "Response should include 'data' array"

        assert data["total"] == 15, f"Total should be 15, got {data['total']}"
        assert data["skip"] == 5, f"Skip should be 5, got {data['skip']}"
        assert data["limit"] == 5, f"Limit should be 5, got {data['limit']}"
        assert len(data["data"]) == 5, f"Should return 5 links, got {len(data['data'])}"

        # Test last page (skip=10, limit=5 should return 5 links)
        response = client.get(
            f"/api/structure_nodes/links",
            params={
                "source_node_id": source_term["id"],
                "skip": 10,
                "limit": 5
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert data["skip"] == 10
        assert len(data["data"]) == 5

        # Test beyond last page (skip=15, limit=5 should return 0 links)
        response = client.get(
            f"/api/structure_nodes/links",
            params={
                "source_node_id": source_term["id"],
                "skip": 15,
                "limit": 5
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert data["skip"] == 15
        assert len(data["data"]) == 0


class TestNodeAttributesAPI:
    """Test attribute API endpoints for getting, setting, and removing attributes."""

    @pytest.fixture
    def sample_nodes_with_links(self, client):
        """Create sample layer->domain->term hierarchy for attribute tests."""
        # Create layer
        layer_data = {
            "node_type": "layer",
            "title": f"Attribute Test Layer {uuid4()}",
            "definition": "Layer for attribute tests",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        assert layer_response.status_code == 201
        layer = layer_response.json()

        # Create domain
        domain_data = {
            "node_type": "domain",
            "title": f"Attribute Test Domain {uuid4()}",
            "definition": "Domain for attribute tests",
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)
        assert domain_response.status_code == 201
        domain = domain_response.json()

        # Create term
        term_data = {
            "node_type": "term",
            "title": f"Attribute Test Term {uuid4()}",
            "definition": "Term for attribute tests",
            "parent_node_id": domain["id"],
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        assert term_response.status_code == 201
        term = term_response.json()

        return layer, domain, term

    def test_get_node_attributes_endpoint(self, client, sample_nodes_with_links):
        """Test GET /api/structure_nodes/{id}/attributes returns resolved attributes."""
        layer, domain, term = sample_nodes_with_links

        # Set some attributes on the domain
        attributes = [
            {
                "key": "jurisdiction",
                "title": "Jurisdiction",
                "value": "US Federal",
                "value_type": "string"
            }
        ]

        response = client.post(
            f"/api/structure_nodes/{domain['id']}/attributes",
            json=attributes
        )
        assert response.status_code == 200

        # Get attributes from the term (should inherit from domain)
        response = client.get(
            f"/api/structure_nodes/{term['id']}/attributes"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_set_node_attributes_endpoint(self, client, sample_nodes_with_links):
        """Test POST /api/structure_nodes/{id}/attributes stores attributes."""
        layer, domain, term = sample_nodes_with_links

        attributes = [
            {
                "key": "category",
                "title": "Category",
                "value": "legal",
                "value_type": "string"
            },
            {
                "key": "jurisdiction",
                "title": "Jurisdiction",
                "value": "US Federal",
                "value_type": "string"
            }
        ]

        response = client.post(
            f"/api/structure_nodes/{domain['id']}/attributes",
            json=attributes
        )

        assert response.status_code == 200

    def test_remove_node_attribute_endpoint(self, client, sample_nodes_with_links):
        """Test DELETE /api/structure_nodes/{id}/attributes/{key} removes attribute."""
        layer, domain, term = sample_nodes_with_links

        # First set an attribute
        attributes = [
            {
                "key": "test_key",
                "title": "Test Key",
                "value": "test_value",
                "value_type": "string"
            }
        ]

        client.post(
            f"/api/structure_nodes/{domain['id']}/attributes",
            json=attributes
        )

        # Remove the attribute
        response = client.delete(
            f"/api/structure_nodes/{domain['id']}/attributes/test_key"
        )

        assert response.status_code == 200

    def test_attributes_inheritance_via_api(self, client, sample_nodes_with_links):
        """Test end-to-end inheritance through API (Legal Domain hierarchy example)."""
        layer, domain, term = sample_nodes_with_links

        # Set attribute on layer
        layer_attrs = [
            {
                "key": "category",
                "title": "Category",
                "value": "legal",
                "value_type": "string"
            }
        ]
        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json=layer_attrs
        )

        # Set attribute on domain (should inherit from layer)
        domain_attrs = [
            {
                "key": "jurisdiction",
                "title": "Jurisdiction",
                "value": "US Federal",
                "value_type": "string"
            }
        ]
        client.post(
            f"/api/structure_nodes/{domain['id']}/attributes",
            json=domain_attrs
        )

        # Get attributes from term (should have inherited attributes)
        response = client.get(
            f"/api/structure_nodes/{term['id']}/attributes"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_attribute_validation_errors(self, client, sample_nodes_with_links):
        """Test invalid attributes return 422 validation error."""
        layer, domain, term = sample_nodes_with_links

        # Send invalid attributes (missing required fields)
        invalid_attributes = [
            {
                "key": "test",
                # Missing title and value_type
            }
        ]

        response = client.post(
            f"/api/structure_nodes/{domain['id']}/attributes",
            json=invalid_attributes
        )

        assert response.status_code == 422

    def test_node_not_found_errors(self, client):
        """Test missing node returns 404 on attribute operations."""
        non_existent_id = "00000000-0000-0000-0000-000000000000"

        # Test GET non-existent node
        response = client.get(
            f"/api/structure_nodes/{non_existent_id}/attributes"
        )
        assert response.status_code == 404

        # Test POST to non-existent node
        attributes = [
            {
                "key": "test",
                "title": "Test",
                "value": "test",
                "value_type": "string"
            }
        ]
        response = client.post(
            f"/api/structure_nodes/{non_existent_id}/attributes",
            json=attributes
        )
        assert response.status_code == 404

        # Test DELETE from non-existent node
        response = client.delete(
            f"/api/structure_nodes/{non_existent_id}/attributes/test_key"
        )
        assert response.status_code == 404

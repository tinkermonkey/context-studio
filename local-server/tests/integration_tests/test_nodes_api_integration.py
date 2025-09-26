"""
API Integration Tests for Nodes API

Tests complete CRUD operations on the unified nodes API as specified
in section 8.3 of the Great Normalization design.
"""

import sys
import os
import uuid
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

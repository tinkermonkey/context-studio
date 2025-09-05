"""
API Integration Tests for Nodes API

Tests complete CRUD operations on the unified nodes API as specified
in section 8.3 of the Great Normalization design.
"""

import sys
import os
import pytest
import uuid
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestNodesAPICRUD:
    """Test complete CRUD operations on nodes API as specified in the design."""
    
    def test_create_layer_success(self, client):
        """Test successful layer creation."""
        layer_data = {
            'node_type': 'layer',
            'title': 'Test Layer',
            'definition': 'Test layer definition'
        }
        
        response = client.post("/api/nodes/", json=layer_data)
        
        assert response.status_code == 201
        layer = response.json()
        
        assert layer['node_type'] == 'layer'
        assert layer['title'] == 'Test Layer'
        assert layer['definition'] == 'Test layer definition'
        assert layer['parent_node_id'] is None
        assert 'id' in layer
        assert 'created_at' in layer
        assert layer['version'] == 1
    
    def test_create_domain_success(self, client):
        """Test successful domain creation with parent layer."""
        # First create a layer
        layer_data = {
            'node_type': 'layer',
            'title': 'Parent Layer',
            'definition': 'Parent layer for domain'
        }
        layer_response = client.post("/api/nodes/", json=layer_data)
        assert layer_response.status_code == 201
        layer = layer_response.json()
        
        # Create domain
        domain_data = {
            'node_type': 'domain',
            'title': 'Test Domain',
            'definition': 'Test domain definition',
            'parent_node_id': layer['id']
        }
        
        response = client.post("/api/nodes/", json=domain_data)
        
        assert response.status_code == 201
        domain = response.json()
        
        assert domain['node_type'] == 'domain'
        assert domain['title'] == 'Test Domain'
        assert domain['definition'] == 'Test domain definition'
        assert domain['parent_node_id'] == layer['id']
        assert 'id' in domain
        assert 'created_at' in domain
        assert domain['version'] == 1
    
    def test_create_term_success(self, client):
        """Test successful term creation with parent domain."""
        # Create layer -> domain -> term hierarchy
        layer_data = {
            'node_type': 'layer',
            'title': 'Test Layer',
            'definition': 'Layer for term test'
        }
        layer_response = client.post("/api/nodes/", json=layer_data)
        layer = layer_response.json()
        
        domain_data = {
            'node_type': 'domain',
            'title': 'Test Domain',
            'definition': 'Domain for term test',
            'parent_node_id': layer['id']
        }
        domain_response = client.post("/api/nodes/", json=domain_data)
        domain = domain_response.json()
        
        # Create term
        term_data = {
            'node_type': 'term',
            'title': 'Test Term',
            'definition': 'Test term definition',
            'parent_node_id': domain['id']
        }
        
        response = client.post("/api/nodes/", json=term_data)
        
        assert response.status_code == 201
        term = response.json()
        
        assert term['node_type'] == 'term'
        assert term['title'] == 'Test Term'
        assert term['definition'] == 'Test term definition'
        assert term['parent_node_id'] == domain['id']
        assert 'id' in term
        assert 'created_at' in term
        assert term['version'] == 1
    
    def test_get_node_success(self, client):
        """Test retrieving a node by ID."""
        # Create a layer
        layer_data = {
            'node_type': 'layer',
            'title': 'Get Test Layer',
            'definition': 'Layer for get test'
        }
        create_response = client.post("/api/nodes/", json=layer_data)
        created_layer = create_response.json()
        
        # Get the layer
        response = client.get(f"/api/nodes/{created_layer['id']}")
        
        assert response.status_code == 200
        retrieved_layer = response.json()
        
        assert retrieved_layer['id'] == created_layer['id']
        assert retrieved_layer['title'] == created_layer['title']
        assert retrieved_layer['node_type'] == created_layer['node_type']
    
    def test_get_node_not_found(self, client):
        """Test retrieving non-existent node returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/nodes/{fake_id}")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_update_node_success(self, client):
        """Test updating a node."""
        # Create a layer
        layer_data = {
            'node_type': 'layer',
            'title': 'Original Title',
            'definition': 'Original definition'
        }
        create_response = client.post("/api/nodes/", json=layer_data)
        created_layer = create_response.json()
        
        # Update the layer
        update_data = {
            'title': 'Updated Title',
            'definition': 'Updated definition'
        }
        response = client.put(f"/api/nodes/{created_layer['id']}", json=update_data)
        
        assert response.status_code == 200
        updated_layer = response.json()
        
        assert updated_layer['id'] == created_layer['id']
        assert updated_layer['title'] == 'Updated Title'
        assert updated_layer['definition'] == 'Updated definition'
        assert updated_layer['version'] == 2  # Version should increment
    
    def test_delete_node_success(self, client):
        """Test deleting a node."""
        # Create a layer
        layer_data = {
            'node_type': 'layer',
            'title': 'Delete Test Layer',
            'definition': 'Layer to be deleted'
        }
        create_response = client.post("/api/nodes/", json=layer_data)
        created_layer = create_response.json()
        
        # Delete the layer
        response = client.delete(f"/api/nodes/{created_layer['id']}")
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify the layer is deleted
        get_response = client.get(f"/api/nodes/{created_layer['id']}")
        assert get_response.status_code == 404
    
    def test_delete_node_cascade(self, client):
        """Test that deleting a node cascades to its children."""
        # Create layer -> domain -> term hierarchy
        layer_data = {
            'node_type': 'layer',
            'title': 'Cascade Test Layer'
        }
        layer_response = client.post("/api/nodes/", json=layer_data)
        layer = layer_response.json()
        
        domain_data = {
            'node_type': 'domain',
            'title': 'Cascade Test Domain',
            'parent_node_id': layer['id']
        }
        domain_response = client.post("/api/nodes/", json=domain_data)
        domain = domain_response.json()
        
        term_data = {
            'node_type': 'term',
            'title': 'Cascade Test Term',
            'parent_node_id': domain['id']
        }
        term_response = client.post("/api/nodes/", json=term_data)
        term = term_response.json()
        
        # Delete the layer (should cascade to domain and term)
        delete_response = client.delete(f"/api/nodes/{layer['id']}")
        assert delete_response.status_code == 200
        
        # Verify all nodes are deleted
        assert client.get(f"/api/nodes/{layer['id']}").status_code == 404
        assert client.get(f"/api/nodes/{domain['id']}").status_code == 404
        assert client.get(f"/api/nodes/{term['id']}").status_code == 404


class TestNodesAPIFiltering:
    """Test filtering and pagination functionality."""
    
    def test_list_nodes_no_filter(self, client):
        """Test listing all nodes without filters."""
        # Create a few nodes
        layer_data = {'node_type': 'layer', 'title': 'Layer 1'}
        client.post("/api/nodes/", json=layer_data)
        
        layer2_data = {'node_type': 'layer', 'title': 'Layer 2'}
        client.post("/api/nodes/", json=layer2_data)
        
        response = client.get("/api/nodes/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'data' in data
        assert 'total' in data
        assert 'skip' in data
        assert 'limit' in data
        assert len(data['data']) >= 2
        assert data['total'] >= 2
    
    def test_list_nodes_filter_by_type(self, client):
        """Test filtering nodes by node_type as specified in the design."""
        # Create layer and domain
        layer_data = {'node_type': 'layer', 'title': 'Filter Test Layer'}
        layer_response = client.post("/api/nodes/", json=layer_data)
        layer = layer_response.json()
        
        domain_data = {
            'node_type': 'domain',
            'title': 'Filter Test Domain',
            'parent_node_id': layer['id']
        }
        client.post("/api/nodes/", json=domain_data)
        
        # Filter by layer type
        response = client.get("/api/nodes/?node_type=layer")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data['data']) >= 1
        # All returned nodes should be layers
        for node in data['data']:
            assert node['node_type'] == 'layer'
    
    def test_list_nodes_filter_by_parent(self, client):
        """Test filtering nodes by parent_node_id."""
        # Create layer with multiple domains
        layer_data = {'node_type': 'layer', 'title': 'Parent Filter Test Layer'}
        layer_response = client.post("/api/nodes/", json=layer_data)
        layer = layer_response.json()
        
        domain1_data = {
            'node_type': 'domain',
            'title': 'Domain 1',
            'parent_node_id': layer['id']
        }
        client.post("/api/nodes/", json=domain1_data)
        
        domain2_data = {
            'node_type': 'domain',
            'title': 'Domain 2',
            'parent_node_id': layer['id']
        }
        client.post("/api/nodes/", json=domain2_data)
        
        # Filter by parent ID
        response = client.get(f"/api/nodes/?parent_node_id={layer['id']}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data['data']) >= 2
        # All returned nodes should have the specified parent
        for node in data['data']:
            assert node['parent_node_id'] == layer['id']
    
    def test_list_nodes_pagination(self, client):
        """Test pagination parameters."""
        # Create multiple layers
        for i in range(5):
            layer_data = {'node_type': 'layer', 'title': f'Pagination Layer {i}'}
            client.post("/api/nodes/", json=layer_data)
        
        # Test pagination
        response = client.get("/api/nodes/?skip=2&limit=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['skip'] == 2
        assert data['limit'] == 2
        assert len(data['data']) <= 2
        assert data['total'] >= 5
    
    def test_list_nodes_sorting(self, client):
        """Test sorting by different fields."""
        # Create layers with different titles (to test title sorting)
        layer_data1 = {'node_type': 'layer', 'title': 'Z Last Layer'}
        layer_data2 = {'node_type': 'layer', 'title': 'A First Layer'}
        
        client.post("/api/nodes/", json=layer_data1)
        client.post("/api/nodes/", json=layer_data2)
        
        # Sort by title
        response = client.get("/api/nodes/?sort_by=title&node_type=layer")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that results are sorted by title
        if len(data['data']) >= 2:
            titles = [node['title'] for node in data['data']]
            assert titles == sorted(titles)


class TestNodesAPIValidation:
    """Test API validation rules as specified in the design."""
    
    def test_create_layer_with_parent_fails(self, client):
        """Test that creating layer with parent returns validation error."""
        layer_data = {
            'node_type': 'layer',
            'title': 'Invalid Layer',
            'parent_node_id': str(uuid.uuid4())
        }

        response = client.post("/api/nodes/", json=layer_data)

        assert response.status_code == 422  # Pydantic validation error
        detail = response.json()["detail"]
        # Handle both string and list formats
        if isinstance(detail, list):
            error_messages = [str(error.get("msg", "")).lower() for error in detail]
            assert any("cannot have parent nodes" in msg for msg in error_messages)
        else:
            assert "cannot have parent nodes" in detail.lower()
    
    def test_create_domain_without_parent_fails(self, client):
        """Test that creating domain without parent returns validation error."""
        domain_data = {
            'node_type': 'domain',
            'title': 'Invalid Domain'
        }
        
        response = client.post("/api/nodes/", json=domain_data)
        
        assert response.status_code == 400
        assert "must have a parent" in response.json()["detail"].lower()
    
    def test_create_term_without_parent_fails(self, client):
        """Test that creating term without parent returns validation error."""
        term_data = {
            'node_type': 'term',
            'title': 'Invalid Term'
        }
        
        response = client.post("/api/nodes/", json=term_data)
        
        assert response.status_code == 400
        assert "must have a parent" in response.json()["detail"].lower()
    
    def test_create_domain_with_invalid_parent_type_fails(self, client):
        """Test that creating domain with non-layer parent fails."""
        # Create a layer and domain
        layer_data = {'node_type': 'layer', 'title': 'Test Layer'}
        layer_response = client.post("/api/nodes/", json=layer_data)
        layer = layer_response.json()
        
        domain_data = {
            'node_type': 'domain',
            'title': 'Test Domain',
            'parent_node_id': layer['id']
        }
        domain_response = client.post("/api/nodes/", json=domain_data)
        domain = domain_response.json()
        
        # Try to create domain with domain parent (should fail)
        invalid_domain_data = {
            'node_type': 'domain',
            'title': 'Invalid Domain',
            'parent_node_id': domain['id']
        }
        
        response = client.post("/api/nodes/", json=invalid_domain_data)
        
        assert response.status_code == 400
        assert "parent must be a layer" in response.json()["detail"].lower()
    
    def test_create_term_with_invalid_parent_type_fails(self, client):
        """Test that creating term with layer parent fails."""
        # Create a layer
        layer_data = {'node_type': 'layer', 'title': 'Test Layer'}
        layer_response = client.post("/api/nodes/", json=layer_data)
        layer = layer_response.json()
        
        # Try to create term with layer parent (should fail)
        term_data = {
            'node_type': 'term',
            'title': 'Invalid Term',
            'parent_node_id': layer['id']
        }
        
        response = client.post("/api/nodes/", json=term_data)
        
        assert response.status_code == 400
        assert "parent must be a domain or term" in response.json()["detail"].lower()
    
    def test_duplicate_layer_title_fails(self, client):
        """Test that creating layer with duplicate title fails."""
        layer_data = {
            'node_type': 'layer',
            'title': 'Duplicate Layer Title'
        }
        
        # Create first layer
        response1 = client.post("/api/nodes/", json=layer_data)
        assert response1.status_code == 201
        
        # Try to create second layer with same title
        response2 = client.post("/api/nodes/", json=layer_data)
        
        assert response2.status_code == 400
        assert "must be unique" in response2.json()["detail"].lower()
    
    def test_duplicate_domain_title_within_layer_fails(self, client):
        """Test that creating domain with duplicate title in same layer fails."""
        # Create layer
        layer_data = {'node_type': 'layer', 'title': 'Test Layer'}
        layer_response = client.post("/api/nodes/", json=layer_data)
        layer = layer_response.json()
        
        domain_data = {
            'node_type': 'domain',
            'title': 'Duplicate Domain Title',
            'parent_node_id': layer['id']
        }
        
        # Create first domain
        response1 = client.post("/api/nodes/", json=domain_data)
        assert response1.status_code == 201
        
        # Try to create second domain with same title in same layer
        response2 = client.post("/api/nodes/", json=domain_data)
        
        assert response2.status_code == 400
        assert "must be unique" in response2.json()["detail"].lower()
    
    def test_duplicate_term_title_within_domain_fails(self, client):
        """Test that creating term with duplicate title in same domain fails."""
        # Create layer -> domain
        layer_data = {'node_type': 'layer', 'title': 'Test Layer'}
        layer_response = client.post("/api/nodes/", json=layer_data)
        layer = layer_response.json()
        
        domain_data = {
            'node_type': 'domain',
            'title': 'Test Domain',
            'parent_node_id': layer['id']
        }
        domain_response = client.post("/api/nodes/", json=domain_data)
        domain = domain_response.json()
        
        term_data = {
            'node_type': 'term',
            'title': 'Duplicate Term Title',
            'parent_node_id': domain['id']
        }
        
        # Create first term
        response1 = client.post("/api/nodes/", json=term_data)
        assert response1.status_code == 201
        
        # Try to create second term with same title in same domain
        response2 = client.post("/api/nodes/", json=term_data)
        
        assert response2.status_code == 400
        assert "must be unique" in response2.json()["detail"].lower()


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
        layer_data = {
            'node_type': 'layer',
            'title': 'Test Layer',
            'definition': 'Test definition'
        }
        response = client.post("/api/nodes/", json=layer_data)
        assert response.status_code == 201
        layer = response.json()
        
        assert layer['node_type'] == 'layer'
        assert layer['title'] == 'Test Layer'
        assert layer['definition'] == 'Test definition'
        assert layer['parent_node_id'] is None
        
        # 2. Create domain
        domain_data = {
            'node_type': 'domain',
            'title': 'Test Domain',
            'definition': 'Test definition',
            'parent_node_id': layer['id']
        }
        response = client.post("/api/nodes/", json=domain_data)
        assert response.status_code == 201
        domain = response.json()
        
        assert domain['node_type'] == 'domain'
        assert domain['title'] == 'Test Domain'
        assert domain['definition'] == 'Test definition'
        assert domain['parent_node_id'] == layer['id']
        
        # 3. Test filtering by node_type
        response = client.get("/api/nodes/?node_type=layer")
        assert response.status_code == 200
        data = response.json()
        assert len(data['data']) >= 1
        
        # Find our layer in the results
        our_layer = None
        for node in data['data']:
            if node['id'] == layer['id']:
                our_layer = node
                break
        
        assert our_layer is not None
        assert our_layer['node_type'] == 'layer'
        
        # 4. Create term under domain
        term_data = {
            'node_type': 'term',
            'title': 'Test Term',
            'definition': 'Test term definition',
            'parent_node_id': domain['id']
        }
        response = client.post("/api/nodes/", json=term_data)
        assert response.status_code == 201
        term = response.json()
        
        # 5. Test hierarchy filtering
        # Get domains under the layer
        response = client.get(f"/api/nodes/?parent_node_id={layer['id']}")
        assert response.status_code == 200
        data = response.json()
        assert len(data['data']) >= 1
        assert data['data'][0]['node_type'] == 'domain'
        
        # Get terms under the domain
        response = client.get(f"/api/nodes/?parent_node_id={domain['id']}")
        assert response.status_code == 200
        data = response.json()
        assert len(data['data']) >= 1
        assert data['data'][0]['node_type'] == 'term'
        
        # 6. Update nodes
        layer_update = {'title': 'Updated Layer Title'}
        response = client.put(f"/api/nodes/{layer['id']}", json=layer_update)
        assert response.status_code == 200
        updated_layer = response.json()
        assert updated_layer['title'] == 'Updated Layer Title'
        assert updated_layer['version'] == 2
        
        # 7. Test cascade delete
        response = client.delete(f"/api/nodes/{layer['id']}")
        assert response.status_code == 200
        
        # Verify all nodes in hierarchy are deleted
        assert client.get(f"/api/nodes/{layer['id']}").status_code == 404
        assert client.get(f"/api/nodes/{domain['id']}").status_code == 404
        assert client.get(f"/api/nodes/{term['id']}").status_code == 404
    
    def test_multiple_layers_with_domains(self, client):
        """Test creating multiple layers each with their own domains."""
        # Create multiple layers
        layers = []
        for i in range(3):
            layer_data = {
                'node_type': 'layer',
                'title': f'Layer {i+1}',
                'definition': f'Definition for layer {i+1}'
            }
            response = client.post("/api/nodes/", json=layer_data)
            assert response.status_code == 201
            layers.append(response.json())
        
        # Create domains under each layer
        domains = []
        for i, layer in enumerate(layers):
            for j in range(2):  # 2 domains per layer
                domain_data = {
                    'node_type': 'domain',
                    'title': f'Domain {i+1}.{j+1}',
                    'definition': f'Domain {j+1} under layer {i+1}',
                    'parent_node_id': layer['id']
                }
                response = client.post("/api/nodes/", json=domain_data)
                assert response.status_code == 201
                domains.append(response.json())
        
        # Test filtering
        # Should have 3 layers
        response = client.get("/api/nodes/?node_type=layer")
        assert response.status_code == 200
        assert len(response.json()['data']) >= 3
        
        # Should have 6 domains total
        response = client.get("/api/nodes/?node_type=domain")
        assert response.status_code == 200
        assert len(response.json()['data']) >= 6
        
        # Each layer should have exactly 2 domains
        for layer in layers:
            response = client.get(f"/api/nodes/?parent_node_id={layer['id']}")
            assert response.status_code == 200
            layer_domains = response.json()['data']
            assert len(layer_domains) == 2
            for domain in layer_domains:
                assert domain['parent_node_id'] == layer['id']
                assert domain['node_type'] == 'domain'


class TestNodesAPIErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_node_type(self, client):
        """Test creating node with invalid node_type."""
        invalid_data = {
            'node_type': 'invalid_type',
            'title': 'Test Node'
        }
        
        response = client.post("/api/nodes/", json=invalid_data)
        
        assert response.status_code == 422  # Pydantic validation error
    
    def test_missing_required_fields(self, client):
        """Test creating node with missing required fields."""
        # Missing title
        response = client.post("/api/nodes/", json={'node_type': 'layer'})
        assert response.status_code == 422
        
        # Missing node_type
        response = client.post("/api/nodes/", json={'title': 'Test'})
        assert response.status_code == 422
    
    def test_invalid_uuid_format(self, client):
        """Test operations with malformed UUID."""
        # Try to get node with invalid UUID
        response = client.get("/api/nodes/not-a-uuid")
        assert response.status_code == 422
        
        # Try to create node with invalid parent UUID
        layer_data = {
            'node_type': 'domain',
            'title': 'Test Domain',
            'parent_node_id': 'not-a-uuid'
        }
        response = client.post("/api/nodes/", json=layer_data)
        assert response.status_code == 422
    
    def test_nonexistent_parent_reference(self, client):
        """Test creating node with non-existent parent."""
        fake_parent_id = str(uuid.uuid4())
        domain_data = {
            'node_type': 'domain',
            'title': 'Orphan Domain',
            'parent_node_id': fake_parent_id
        }
        
        response = client.post("/api/nodes/", json=domain_data)
        
        assert response.status_code == 400
        assert "parent must be a layer" in response.json()["detail"].lower()
    
    def test_update_nonexistent_node(self, client):
        """Test updating non-existent node."""
        fake_id = str(uuid.uuid4())
        update_data = {'title': 'Updated Title'}
        
        response = client.put(f"/api/nodes/{fake_id}", json=update_data)
        
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()
    
    def test_delete_nonexistent_node(self, client):
        """Test deleting non-existent node."""
        fake_id = str(uuid.uuid4())
        
        response = client.delete(f"/api/nodes/{fake_id}")
        
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

"""
Integration Tests for Structure Node Attributes API

Tests complete CRUD operations on the attributes API endpoints including
inheritance resolution and validation.
"""

import os
import sys
from uuid import uuid4

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ),
)


class TestAttributesAPIBasicOperations:
    """Test basic CRUD operations on attributes API endpoints."""

    def test_get_node_attributes_empty(self, client):
        """Test getting attributes for a node with no attributes set."""
        # Create a layer (no attributes)
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        assert layer_response.status_code == 201
        layer = layer_response.json()

        # Get attributes
        attr_response = client.get(
            f"/api/structure_nodes/{layer['id']}/attributes"
        )
        assert attr_response.status_code == 200
        attributes = attr_response.json()
        assert attributes == []

    def test_set_node_attributes_single(self, client):
        """Test setting a single attribute on a node."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set attributes
        attributes = [
            {
                "key": "domain_classification",
                "title": "Domain Category",
                "value_type": "string",
                "value": "legal",
            }
        ]

        set_response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        assert set_response.status_code == 200
        updated_node = set_response.json()
        assert updated_node["version"] == 2  # Version incremented

        # Verify attributes were set
        get_response = client.get(
            f"/api/structure_nodes/{layer['id']}/attributes"
        )
        assert get_response.status_code == 200
        result_attrs = get_response.json()
        assert len(result_attrs) == 1
        assert result_attrs[0]["key"] == "domain_classification"
        assert result_attrs[0]["value"] == "legal"
        assert result_attrs[0]["inherited"] is False

    def test_set_node_attributes_multiple(self, client):
        """Test setting multiple attributes on a node."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set multiple attributes
        attributes = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "legal",
            },
            {
                "key": "version_number",
                "title": "Version",
                "value_type": "number",
                "value": 1,
            },
            {
                "key": "is_active",
                "title": "Active",
                "value_type": "boolean",
                "value": True,
            },
        ]

        set_response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        assert set_response.status_code == 200

        # Verify all attributes were set
        get_response = client.get(
            f"/api/structure_nodes/{layer['id']}/attributes"
        )
        assert get_response.status_code == 200
        result_attrs = get_response.json()
        assert len(result_attrs) == 3

        keys = {attr["key"] for attr in result_attrs}
        assert keys == {"category", "version_number", "is_active"}

    def test_remove_node_attribute(self, client):
        """Test removing a specific attribute by key."""
        # Create a layer with attributes
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set attributes
        attributes = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "legal",
            },
            {
                "key": "version_number",
                "title": "Version",
                "value_type": "number",
                "value": 1,
            },
        ]

        set_response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        assert set_response.status_code == 200

        # Remove one attribute
        remove_response = client.delete(
            f"/api/structure_nodes/{layer['id']}/attributes/category"
        )
        assert remove_response.status_code == 200
        updated_node = remove_response.json()
        assert updated_node["version"] == 3  # Version incremented again

        # Verify attribute was removed
        get_response = client.get(
            f"/api/structure_nodes/{layer['id']}/attributes"
        )
        assert get_response.status_code == 200
        result_attrs = get_response.json()
        assert len(result_attrs) == 1
        assert result_attrs[0]["key"] == "version_number"

    def test_set_node_attributes_replaces_existing(self, client):
        """Test that setting attributes replaces existing ones."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set initial attributes
        attributes_v1 = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "legal",
            }
        ]

        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes_v1},
        )

        # Set new attributes (should replace old ones)
        attributes_v2 = [
            {"key": "version", "title": "Version", "value_type": "number", "value": 2}
        ]

        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes_v2},
        )

        # Verify old attribute is gone
        get_response = client.get(
            f"/api/structure_nodes/{layer['id']}/attributes"
        )
        assert get_response.status_code == 200
        result_attrs = get_response.json()
        assert len(result_attrs) == 1
        assert result_attrs[0]["key"] == "version"


class TestAttributesInheritance:
    """Test attribute inheritance across node hierarchy."""

    def test_attributes_inheritance_via_api_simple(self, client):
        """Test inheritance: layer -> domain -> term."""
        # Create layer with attribute
        unique_layer_title = f"Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_layer_title,
            "definition": "Test layer",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set layer attribute
        layer_attrs = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "legal",
            }
        ]
        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": layer_attrs},
        )

        # Create domain under layer
        unique_domain_title = f"Domain {uuid4()}"
        domain_data = {
            "node_type": "domain",
            "title": unique_domain_title,
            "parent_node_id": layer["id"],
            "definition": "Test domain",
        }
        domain_response = client.post(
            "/api/structure_nodes/", json=domain_data
        )
        domain = domain_response.json()

        # Create term under domain
        unique_term_title = f"Term {uuid4()}"
        term_data = {
            "node_type": "term",
            "title": unique_term_title,
            "parent_node_id": domain["id"],
            "definition": "Test term",
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        term = term_response.json()

        # Get term attributes - should inherit from layer
        attr_response = client.get(
            f"/api/structure_nodes/{term['id']}/attributes"
        )
        assert attr_response.status_code == 200
        result_attrs = attr_response.json()

        # Should have inherited layer attribute
        assert len(result_attrs) == 1
        assert result_attrs[0]["key"] == "category"
        assert result_attrs[0]["value"] == "legal"
        assert result_attrs[0]["inherited"] is True
        assert result_attrs[0]["source_node_id"] == layer["id"]

    def test_attributes_inheritance_override(self, client):
        """Test that child attributes override parent attributes."""
        # Create layer with attribute
        unique_layer_title = f"Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_layer_title,
            "definition": "Test layer",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set layer attribute
        layer_attrs = [
            {
                "key": "jurisdiction",
                "title": "Jurisdiction",
                "value_type": "string",
                "value": "US Federal",
            }
        ]
        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": layer_attrs},
        )

        # Create domain under layer
        unique_domain_title = f"Domain {uuid4()}"
        domain_data = {
            "node_type": "domain",
            "title": unique_domain_title,
            "parent_node_id": layer["id"],
            "definition": "Test domain",
        }
        domain_response = client.post(
            "/api/structure_nodes/", json=domain_data
        )
        domain = domain_response.json()

        # Create term under domain with overriding attribute
        unique_term_title = f"Term {uuid4()}"
        term_data = {
            "node_type": "term",
            "title": unique_term_title,
            "parent_node_id": domain["id"],
            "definition": "Test term",
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        term = term_response.json()

        # Set term attribute that overrides parent
        term_attrs = [
            {
                "key": "jurisdiction",
                "title": "Jurisdiction",
                "value_type": "string",
                "value": "New York State",
            }
        ]
        client.post(
            f"/api/structure_nodes/{term['id']}/attributes",
            json={"attributes": term_attrs},
        )

        # Get term attributes
        attr_response = client.get(
            f"/api/structure_nodes/{term['id']}/attributes"
        )
        assert attr_response.status_code == 200
        result_attrs = attr_response.json()

        # Should have jurisdiction with term's value
        assert len(result_attrs) == 1
        jurisdiction = result_attrs[0]
        assert jurisdiction["key"] == "jurisdiction"
        assert jurisdiction["value"] == "New York State"
        assert jurisdiction["inherited"] is False
        assert jurisdiction["source_node_id"] == term["id"]

    def test_attributes_multi_level_inheritance(self, client):
        """Test inheritance through multiple levels."""
        # Create layer with attribute
        unique_layer_title = f"Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_layer_title,
            "definition": "Test layer",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set layer attribute
        layer_attrs = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "legal",
            }
        ]
        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": layer_attrs},
        )

        # Create domain with its own attribute
        unique_domain_title = f"Domain {uuid4()}"
        domain_data = {
            "node_type": "domain",
            "title": unique_domain_title,
            "parent_node_id": layer["id"],
            "definition": "Test domain",
        }
        domain_response = client.post(
            "/api/structure_nodes/", json=domain_data
        )
        domain = domain_response.json()

        # Set domain attribute
        domain_attrs = [
            {
                "key": "jurisdiction",
                "title": "Jurisdiction",
                "value_type": "string",
                "value": "US Federal",
            }
        ]
        client.post(
            f"/api/structure_nodes/{domain['id']}/attributes",
            json={"attributes": domain_attrs},
        )

        # Create term under domain
        unique_term_title = f"Term {uuid4()}"
        term_data = {
            "node_type": "term",
            "title": unique_term_title,
            "parent_node_id": domain["id"],
            "definition": "Test term",
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        term = term_response.json()

        # Get term attributes - should have both layer and domain attributes
        attr_response = client.get(
            f"/api/structure_nodes/{term['id']}/attributes"
        )
        assert attr_response.status_code == 200
        result_attrs = attr_response.json()

        # Should have both inherited attributes
        assert len(result_attrs) == 2
        keys = {attr["key"] for attr in result_attrs}
        assert keys == {"category", "jurisdiction"}

        # Verify inheritance flags
        for attr in result_attrs:
            assert attr["inherited"] is True


class TestAttributeValidation:
    """Test attribute value type validation and error handling."""

    def test_attribute_validation_invalid_string(self, client):
        """Test validation fails for invalid string type."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Try to set attribute with invalid key format
        attributes = [
            {
                "key": "123invalid",  # Invalid: starts with number
                "title": "Title",
                "value_type": "string",
                "value": "test",
            }
        ]

        response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        # Should fail validation
        assert response.status_code >= 400

    def test_attribute_validation_invalid_number(self, client):
        """Test validation fails for invalid number type."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Try to set attribute with non-numeric value
        attributes = [
            {
                "key": "count",
                "title": "Count",
                "value_type": "number",
                "value": "not_a_number",
            }
        ]

        response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        # Should fail validation
        assert response.status_code >= 400

    def test_attribute_validation_invalid_boolean(self, client):
        """Test validation fails for invalid boolean type."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Try to set attribute with non-boolean value
        attributes = [
            {
                "key": "active",
                "title": "Active",
                "value_type": "boolean",
                "value": "yes",  # String instead of boolean
            }
        ]

        response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        # Should fail validation
        assert response.status_code >= 400

    def test_attribute_validation_invalid_date_format(self, client):
        """Test validation fails for invalid date format."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Try to set attribute with invalid date format
        attributes = [
            {
                "key": "created",
                "title": "Created",
                "value_type": "date",
                "value": "2025/01/15",  # Invalid format
            }
        ]

        response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        # Should fail validation
        assert response.status_code >= 400

    def test_attribute_validation_valid_date_format(self, client):
        """Test validation passes for valid date format."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set attribute with valid date format
        attributes = [
            {
                "key": "created",
                "title": "Created",
                "value_type": "date",
                "value": "2025-01-15",  # Valid ISO 8601 format
            }
        ]

        response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        # Should succeed
        assert response.status_code == 200

    def test_attribute_validation_invalid_url_format(self, client):
        """Test validation fails for invalid URL format."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Try to set attribute with invalid URL
        attributes = [
            {
                "key": "reference",
                "title": "Reference",
                "value_type": "url",
                "value": "not-a-url",  # Missing protocol
            }
        ]

        response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        # Should fail validation
        assert response.status_code >= 400

    def test_attribute_validation_valid_urls(self, client):
        """Test validation passes for valid URLs."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set attributes with valid URLs
        attributes = [
            {
                "key": "https_ref",
                "title": "HTTPS Reference",
                "value_type": "url",
                "value": "https://example.com/path",
            },
            {
                "key": "http_ref",
                "title": "HTTP Reference",
                "value_type": "url",
                "value": "http://example.com",
            },
        ]

        response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        # Should succeed
        assert response.status_code == 200
        result_attrs = response.json()
        assert len(result_attrs) >= 1

    def test_attribute_null_values(self, client):
        """Test that null values are allowed for attributes."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set attributes with null values
        attributes = [
            {
                "key": "optional_field",
                "title": "Optional Field",
                "value_type": "string",
                "value": None,
            }
        ]

        response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        # Should succeed - null values are allowed
        assert response.status_code == 200

        # Verify attribute was set with null value
        get_response = client.get(
            f"/api/structure_nodes/{layer['id']}/attributes"
        )
        result_attrs = get_response.json()
        assert len(result_attrs) == 1
        assert result_attrs[0]["value"] is None


class TestAttributeErrorHandling:
    """Test error handling for attributes API endpoints."""

    def test_get_attributes_node_not_found(self, client):
        """Test GET attributes endpoint returns 404 for non-existent node."""
        fake_id = str(uuid4())
        response = client.get(f"/api/structure_nodes/{fake_id}/attributes")
        assert response.status_code == 404

    def test_set_attributes_node_not_found(self, client):
        """Test POST attributes endpoint returns 404 for non-existent node."""
        fake_id = str(uuid4())
        attributes = [
            {"key": "test", "title": "Test", "value_type": "string", "value": "test"}
        ]
        response = client.post(
            f"/api/structure_nodes/{fake_id}/attributes",
            json={"attributes": attributes},
        )
        assert response.status_code == 404

    def test_remove_attributes_node_not_found(self, client):
        """Test DELETE attributes endpoint returns 404 for non-existent node."""
        fake_id = str(uuid4())
        response = client.delete(
            f"/api/structure_nodes/{fake_id}/attributes/test_key"
        )
        assert response.status_code == 404

    def test_remove_nonexistent_attribute_key(self, client):
        """Test removing a non-existent attribute key (should succeed with no effect)."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set an attribute
        attributes = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "test",
            }
        ]
        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )

        # Remove a non-existent key
        response = client.delete(
            f"/api/structure_nodes/{layer['id']}/attributes/nonexistent"
        )
        assert response.status_code == 200

        # Verify original attribute still exists
        get_response = client.get(
            f"/api/structure_nodes/{layer['id']}/attributes"
        )
        result_attrs = get_response.json()
        assert len(result_attrs) == 1
        assert result_attrs[0]["key"] == "category"


class TestAttributeEdgeCases:
    """Test edge cases for attributes functionality."""

    def test_empty_attributes_list(self, client):
        """Test setting empty attributes list."""
        # Create a layer with initial attributes
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set initial attributes
        initial_attrs = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "test",
            }
        ]
        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": initial_attrs},
        )

        # Set empty attributes list
        response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes", json={"attributes": []}
        )
        assert response.status_code == 200

        # Verify all attributes were removed
        get_response = client.get(
            f"/api/structure_nodes/{layer['id']}/attributes"
        )
        result_attrs = get_response.json()
        assert result_attrs == []

    def test_deeply_nested_hierarchy(self, client):
        """Test attribute inheritance through deeply nested hierarchy (5+ levels)."""
        # Create layer with attribute
        unique_layer_title = f"Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_layer_title,
            "definition": "Test layer",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set layer attribute
        layer_attrs = [
            {
                "key": "root_attr",
                "title": "Root Attribute",
                "value_type": "string",
                "value": "from_layer",
            }
        ]
        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": layer_attrs},
        )

        # Create domain
        unique_domain_title = f"Domain {uuid4()}"
        domain_data = {
            "node_type": "domain",
            "title": unique_domain_title,
            "parent_node_id": layer["id"],
            "definition": "Test domain",
        }
        domain_response = client.post(
            "/api/structure_nodes/", json=domain_data
        )
        domain = domain_response.json()

        # Create nested terms (5+ levels)
        current_parent = domain["id"]
        for i in range(5):
            unique_term_title = f"Term Level {i} {uuid4()}"
            term_data = {
                "node_type": "term",
                "title": unique_term_title,
                "parent_node_id": current_parent,
                "definition": f"Test term level {i}",
            }
            term_response = client.post(
                "/api/structure_nodes/", json=term_data
            )
            current_term = term_response.json()
            current_parent = current_term["id"]

        # Get attributes of deeply nested term - should inherit from layer
        attr_response = client.get(
            f"/api/structure_nodes/{current_parent}/attributes"
        )
        assert attr_response.status_code == 200
        result_attrs = attr_response.json()

        # Should have inherited attribute from layer
        assert len(result_attrs) == 1
        assert result_attrs[0]["key"] == "root_attr"
        assert result_attrs[0]["value"] == "from_layer"
        assert result_attrs[0]["inherited"] is True

    def test_attribute_key_collision_resolution(self, client):
        """Test that attribute keys at multiple levels resolve correctly."""
        # Create layer with attribute
        unique_layer_title = f"Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_layer_title,
            "definition": "Test layer",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set layer attribute
        layer_attrs = [
            {
                "key": "shared_key",
                "title": "Shared Key",
                "value_type": "string",
                "value": "layer_value",
            }
        ]
        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": layer_attrs},
        )

        # Create domain with same key
        unique_domain_title = f"Domain {uuid4()}"
        domain_data = {
            "node_type": "domain",
            "title": unique_domain_title,
            "parent_node_id": layer["id"],
            "definition": "Test domain",
        }
        domain_response = client.post(
            "/api/structure_nodes/", json=domain_data
        )
        domain = domain_response.json()

        domain_attrs = [
            {
                "key": "shared_key",
                "title": "Shared Key",
                "value_type": "string",
                "value": "domain_value",
            }
        ]
        client.post(
            f"/api/structure_nodes/{domain['id']}/attributes",
            json={"attributes": domain_attrs},
        )

        # Create term under domain
        unique_term_title = f"Term {uuid4()}"
        term_data = {
            "node_type": "term",
            "title": unique_term_title,
            "parent_node_id": domain["id"],
            "definition": "Test term",
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        term = term_response.json()

        # Term should get domain's value (nearest ancestor)
        attr_response = client.get(
            f"/api/structure_nodes/{term['id']}/attributes"
        )
        result_attrs = attr_response.json()

        assert len(result_attrs) == 1
        assert result_attrs[0]["key"] == "shared_key"
        assert result_attrs[0]["value"] == "domain_value"
        assert result_attrs[0]["source_node_id"] == domain["id"]

    def test_all_value_types_together(self, client):
        """Test setting all value types in a single node."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # Set attributes with all types
        attributes = [
            {
                "key": "str_attr",
                "title": "String",
                "value_type": "string",
                "value": "test_value",
            },
            {"key": "num_attr", "title": "Number", "value_type": "number", "value": 42},
            {
                "key": "bool_attr",
                "title": "Boolean",
                "value_type": "boolean",
                "value": True,
            },
            {
                "key": "date_attr",
                "title": "Date",
                "value_type": "date",
                "value": "2025-01-15",
            },
            {
                "key": "url_attr",
                "title": "URL",
                "value_type": "url",
                "value": "https://example.com",
            },
        ]

        set_response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes},
        )
        assert set_response.status_code == 200

        # Verify all attributes
        get_response = client.get(
            f"/api/structure_nodes/{layer['id']}/attributes"
        )
        result_attrs = get_response.json()

        assert len(result_attrs) == 5
        keys = {attr["key"] for attr in result_attrs}
        assert keys == {
            "str_attr",
            "num_attr",
            "bool_attr",
            "date_attr",
            "url_attr",
        }


class TestOptimisticLocking:
    """Test optimistic locking for attribute updates."""

    def test_set_attributes_without_version_check_succeeds(self, client):
        """Test setting attributes without version check always succeeds."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()
        initial_version = layer["version"]

        # Set attributes without expected_version (first update)
        attributes_v1 = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "legal",
            }
        ]

        set_response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes_v1},
        )
        assert set_response.status_code == 200
        updated_node = set_response.json()
        assert updated_node["version"] == initial_version + 1

    def test_set_attributes_with_correct_version_succeeds(self, client):
        """Test setting attributes with correct expected_version succeeds."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        # First update without version check
        attributes_v1 = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "legal",
            }
        ]

        set_response1 = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes_v1},
        )
        assert set_response1.status_code == 200
        node_after_v1 = set_response1.json()
        v1_version = node_after_v1["version"]

        # Second update with correct expected_version
        attributes_v2 = [
            {
                "key": "status",
                "title": "Status",
                "value_type": "string",
                "value": "active",
            }
        ]

        set_response2 = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes_v2, "expected_version": v1_version},
        )
        assert set_response2.status_code == 200
        node_after_v2 = set_response2.json()
        assert node_after_v2["version"] == v1_version + 1

    def test_set_attributes_with_stale_version_fails_with_409(self, client):
        """Test setting attributes with stale expected_version fails with 409 Conflict."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()
        initial_version = layer["version"]

        # First update
        attributes_v1 = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "legal",
            }
        ]

        set_response1 = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attributes_v1},
        )
        assert set_response1.status_code == 200

        # Try to update with stale version
        attributes_v2 = [
            {
                "key": "status",
                "title": "Status",
                "value_type": "string",
                "value": "active",
            }
        ]

        set_response2 = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={
                "attributes": attributes_v2,
                "expected_version": initial_version,  # This is stale
            },
        )
        assert set_response2.status_code == 409
        error_response = set_response2.json()
        assert "detail" in error_response
        assert len(error_response["detail"]) > 0
        error_msg = error_response["detail"][0]["msg"].lower()
        assert "version" in error_msg

    def test_concurrent_attribute_updates_with_locking(self, client):
        """Test that second concurrent update fails when first succeeds with locking."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()
        initial_version = layer["version"]

        # Simulate User A and User B both reading the same version
        # User A updates successfully
        attrs_user_a = [
            {
                "key": "category",
                "title": "Category",
                "value_type": "string",
                "value": "legal",
            }
        ]

        response_a = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attrs_user_a, "expected_version": initial_version},
        )
        assert response_a.status_code == 200
        node_a = response_a.json()
        assert node_a["version"] == initial_version + 1

        # User B tries to update with the original version (stale)
        attrs_user_b = [
            {
                "key": "status",
                "title": "Status",
                "value_type": "string",
                "value": "active",
            }
        ]

        response_b = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={
                "attributes": attrs_user_b,
                "expected_version": initial_version,  # Stale - User A already updated
            },
        )
        assert response_b.status_code == 409

        # Verify User A's attributes are still there
        get_response = client.get(
            f"/api/structure_nodes/{layer['id']}/attributes"
        )
        result_attrs = get_response.json()
        assert len(result_attrs) == 1
        assert result_attrs[0]["key"] == "category"
        assert result_attrs[0]["value"] == "legal"

    def test_optimistic_locking_error_includes_version_info(self, client):
        """Test that 409 error response includes current and expected versions."""
        # Create a layer
        unique_title = f"Test Layer {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": unique_title,
            "definition": "Test layer",
        }

        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()
        initial_version = layer["version"]

        # Update the node
        attrs = [
            {"key": "test", "title": "Test", "value_type": "string", "value": "test"}
        ]

        client.post(
            f"/api/structure_nodes/{layer['id']}/attributes", json={"attributes": attrs}
        )

        # Try to update with stale version
        conflict_response = client.post(
            f"/api/structure_nodes/{layer['id']}/attributes",
            json={"attributes": attrs, "expected_version": initial_version},
        )

        assert conflict_response.status_code == 409
        error_data = conflict_response.json()
        assert "detail" in error_data
        assert len(error_data["detail"]) > 0
        error_msg = error_data["detail"][0]["msg"]
        # Error message should contain version information
        assert "version" in error_msg.lower()
        assert (
            str(initial_version) in error_msg or "expected" in error_msg.lower()
        )

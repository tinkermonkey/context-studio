"""
Integration tests for word sense update API endpoint.

Tests the PUT /api/structure_nodes/{node_id}/word_senses endpoint for updating
selected word senses with conservative merge strategy.
"""

import sys
import os
from uuid import uuid4

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: E501
)


class TestWordSenseUpdateAPI:
    """Test word sense update API endpoint."""

    def test_update_word_senses_success(self, client):
        """Test successfully updating selected word senses."""
        # Create a test node
        unique_title = f"Test Term {uuid4()}"
        layer_data = {
            "node_type": "layer",
            "title": f"Test Layer {uuid4()}",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain_data = {
            "node_type": "domain",
            "title": f"Test Domain {uuid4()}",
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)  # noqa: E501
        domain = domain_response.json()

        term_data = {
            "node_type": "term",
            "title": unique_title,
            "parent_node_id": domain["id"],
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        assert term_response.status_code == 201
        term = term_response.json()
        node_id = term["id"]

        # Update word senses
        word_senses_data = {
            "selected_senses": [
                {
                    "term": "test",
                    "sense_type": "wordnet",
                    "sense_id": "test.n.01",
                    "definition": "a test definition"
                }
            ]
        }

        response = client.put(
            f"/api/structure_nodes/{node_id}/word_senses",
            json=word_senses_data
        )

        assert response.status_code == 200
        result = response.json()

        # Verify response
        assert len(result) == 1
        assert result[0]["term"] == "test"
        assert result[0]["sense_id"] == "test.n.01"
        assert result[0]["definition"] == "a test definition"

        # Verify persisted by fetching again
        get_response = client.get(f"/api/structure_nodes/{node_id}/word_senses")  # noqa: E501
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert len(fetched) == 1
        assert fetched[0]["sense_id"] == "test.n.01"

    def test_update_word_senses_conservative_merge(self, client):
        """Test conservative merge preserves senses for other words."""
        # Create a test node
        layer_data = {
            "node_type": "layer",
            "title": f"Test Layer {uuid4()}",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain_data = {
            "node_type": "domain",
            "title": f"Test Domain {uuid4()}",
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)  # noqa: E501
        domain = domain_response.json()

        term_data = {
            "node_type": "term",
            "title": f"Test Term {uuid4()}",
            "parent_node_id": domain["id"],
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        term = term_response.json()
        node_id = term["id"]

        # First update - add senses for two words
        initial_senses = {
            "selected_senses": [
                {
                    "term": "bank",
                    "sense_type": "wordnet",
                    "sense_id": "bank.n.01",
                    "definition": "financial institution",
                    "domain": "noun.group"
                },
                {
                    "term": "account",
                    "sense_type": "wordnet",
                    "sense_id": "account.n.01",
                    "definition": "a record or narrative description",
                    "domain": "noun.communication"
                }
            ]
        }

        response1 = client.put(
            f"/api/structure_nodes/{node_id}/word_senses",
            json=initial_senses
        )
        assert response1.status_code == 200

        # Second update - update only "bank", not "account"
        updated_senses = {
            "selected_senses": [
                {
                    "term": "bank",
                    "sense_type": "wordnet",
                    "sense_id": "bank.n.02",
                    "definition": "sloping land beside water",
                    "domain": "noun.object"
                }
            ]
        }

        response2 = client.put(
            f"/api/structure_nodes/{node_id}/word_senses",
            json=updated_senses
        )
        assert response2.status_code == 200
        result = response2.json()

        # Verify both words are present
        assert len(result) == 2
        sense_by_term = {s["term"]: s for s in result}

        # "bank" should be updated
        assert "bank" in sense_by_term
        assert sense_by_term["bank"]["sense_id"] == "bank.n.02"

        # "account" should be preserved
        assert "account" in sense_by_term
        assert sense_by_term["account"]["sense_id"] == "account.n.01"

    def test_update_word_senses_replaces_all_for_word(self, client):
        """Test that updating a word replaces all its previous senses."""
        # Create a test node
        layer_data = {
            "node_type": "layer",
            "title": f"Test Layer {uuid4()}",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain_data = {
            "node_type": "domain",
            "title": f"Test Domain {uuid4()}",
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)  # noqa: E501
        domain = domain_response.json()

        term_data = {
            "node_type": "term",
            "title": f"Test Term {uuid4()}",
            "parent_node_id": domain["id"],
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        term = term_response.json()
        node_id = term["id"]

        # First update - add multiple senses for "bank"
        initial_senses = {
            "selected_senses": [
                {
                    "term": "bank",
                    "sense_type": "wordnet",
                    "sense_id": "bank.n.01",
                    "definition": "financial institution"
                },
                {
                    "term": "bank",
                    "sense_type": "wordnet",
                    "sense_id": "bank.n.02",
                    "definition": "sloping land beside water"
                }
            ]
        }

        response1 = client.put(
            f"/api/structure_nodes/{node_id}/word_senses",
            json=initial_senses
        )
        assert response1.status_code == 200

        # Second update - replace with single sense
        updated_senses = {
            "selected_senses": [
                {
                    "term": "bank",
                    "sense_type": "wordnet",
                    "sense_id": "bank.n.03",
                    "definition": "building housing a bank"
                }
            ]
        }

        response2 = client.put(
            f"/api/structure_nodes/{node_id}/word_senses",
            json=updated_senses
        )
        assert response2.status_code == 200
        result = response2.json()

        # Verify only the new sense remains
        assert len(result) == 1
        assert result[0]["sense_id"] == "bank.n.03"

    def test_update_word_senses_invalid_sense_id(self, client):
        """Test validation rejects invalid WordNet sense IDs."""
        # Create a test node
        layer_data = {
            "node_type": "layer",
            "title": f"Test Layer {uuid4()}",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain_data = {
            "node_type": "domain",
            "title": f"Test Domain {uuid4()}",
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)  # noqa: E501
        domain = domain_response.json()

        term_data = {
            "node_type": "term",
            "title": f"Test Term {uuid4()}",
            "parent_node_id": domain["id"],
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        term = term_response.json()
        node_id = term["id"]

        # Attempt to update with invalid sense_id
        invalid_senses = {
            "selected_senses": [
                {
                    "term": "test",
                    "sense_type": "wordnet",
                    "sense_id": "invalid-format",  # Invalid WordNet format
                    "definition": "test definition"
                }
            ]
        }

        response = client.put(
            f"/api/structure_nodes/{node_id}/word_senses",
            json=invalid_senses
        )

        # Should return 400 Bad Request
        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]

    def test_update_word_senses_node_not_found(self, client):
        """Test updating word senses for non-existent node returns 404."""
        fake_id = str(uuid4())

        word_senses_data = {
            "selected_senses": [
                {
                    "term": "test",
                    "sense_type": "wordnet",
                    "sense_id": "test.n.01",
                    "definition": "test definition"
                }
            ]
        }

        response = client.put(
            f"/api/structure_nodes/{fake_id}/word_senses",
            json=word_senses_data
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_word_senses_version_increment(self, client):
        """Test that updating word senses increments node version."""
        # Create a test node
        layer_data = {
            "node_type": "layer",
            "title": f"Test Layer {uuid4()}",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain_data = {
            "node_type": "domain",
            "title": f"Test Domain {uuid4()}",
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)  # noqa: E501
        domain = domain_response.json()

        term_data = {
            "node_type": "term",
            "title": f"Test Term {uuid4()}",
            "parent_node_id": domain["id"],
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        term = term_response.json()
        node_id = term["id"]
        initial_version = term["version"]  # Get initial version from create response  # noqa: E501

        # Update word senses
        word_senses_data = {
            "selected_senses": [
                {
                    "term": "test",
                    "sense_type": "wordnet",
                    "sense_id": "test.n.01",
                    "definition": "test definition"
                }
            ]
        }

        client.put(
            f"/api/structure_nodes/{node_id}/word_senses",
            json=word_senses_data
        )

        # Get updated node to verify version increment
        updated_node = client.get(f"/api/structure_nodes/{node_id}").json()

        # Version should be incremented
        assert updated_node["version"] == initial_version + 1

    def test_update_word_senses_empty_list(self, client):
        """Test updating with empty list removes all senses for specified terms."""  # noqa: E501
        # Create a test node
        layer_data = {
            "node_type": "layer",
            "title": f"Test Layer {uuid4()}",
        }
        layer_response = client.post("/api/structure_nodes/", json=layer_data)
        layer = layer_response.json()

        domain_data = {
            "node_type": "domain",
            "title": f"Test Domain {uuid4()}",
            "parent_node_id": layer["id"],
        }
        domain_response = client.post("/api/structure_nodes/", json=domain_data)  # noqa: E501
        domain = domain_response.json()

        term_data = {
            "node_type": "term",
            "title": f"Test Term {uuid4()}",
            "parent_node_id": domain["id"],
        }
        term_response = client.post("/api/structure_nodes/", json=term_data)
        term = term_response.json()
        node_id = term["id"]

        # First add some senses
        initial_senses = {
            "selected_senses": [
                {
                    "term": "test",
                    "sense_type": "wordnet",
                    "sense_id": "test.n.01",
                    "definition": "test definition"
                }
            ]
        }

        client.put(
            f"/api/structure_nodes/{node_id}/word_senses",
            json=initial_senses
        )

        # Update with empty list (technically no terms to update, so all senses preserved)  # noqa: E501
        empty_update = {
            "selected_senses": []
        }

        response = client.put(
            f"/api/structure_nodes/{node_id}/word_senses",
            json=empty_update
        )

        assert response.status_code == 200
        result = response.json()

        # Since we're not updating any terms, existing senses should be preserved  # noqa: E501
        assert len(result) == 1
        assert result[0]["sense_id"] == "test.n.01"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

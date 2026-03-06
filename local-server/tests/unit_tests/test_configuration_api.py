"""
Unit tests for configuration API endpoints
"""

import sys
import os
from fastapi.testclient import TestClient

# Add the project root to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from config import get_config_manager  # noqa: E402


class TestConfigurationAPI:
    """Test configuration API endpoints"""

    def setup_method(self):
        """Set up test environment"""
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_get_full_configuration(self):
        """Test GET /api/config/ endpoint returns full configuration"""
        response = self.client.get("/api/config/")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "server" in data["data"]
        assert "database" in data["data"]
        assert "nlp" in data["data"]

    def test_get_specific_configuration_value(self):
        """Test GET /api/config/{path} endpoint returns specific values"""
        response = self.client.get("/api/config/server.host")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        # Should return the server host value

    def test_get_nested_configuration_value(self):
        """Test getting nested configuration values"""
        response = self.client.get("/api/config/database.check_same_thread")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], bool)

    def test_get_nonexistent_configuration_value(self):
        """Test GET with invalid path returns 404"""
        response = self.client.get("/api/config/nonexistent.path")

        assert response.status_code == 404

    def test_patch_configuration_value(self):
        """Test PATCH /api/config/ endpoint updates configuration"""
        update_data = {"path": "server.port", "value": 9004}

        response = self.client.patch("/api/config/", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify the change was applied
        config_manager = get_config_manager()
        assert config_manager.get("server.port") == 9004

    def test_patch_invalid_configuration_path(self):
        """Test PATCH with invalid path returns 400"""
        update_data = {"path": "invalid.nonexistent.path", "value": "test_value"}  # noqa: E501

        response = self.client.patch("/api/config/", json=update_data)

        assert response.status_code == 400

    def test_patch_invalid_configuration_value_type(self):
        """Test PATCH with invalid value type returns 400"""
        update_data = {"path": "server.port", "value": "not_a_number"}

        response = self.client.patch("/api/config/", json=update_data)

        assert response.status_code == 400

    def test_configuration_validation_endpoint(self):
        """Test GET /api/config/validate endpoint"""
        response = self.client.get("/api/config/validate")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "errors" in data["data"]
        assert isinstance(data["data"]["errors"], list)

    def test_configuration_schema_endpoint(self):
        """Test GET /api/config/schema/ endpoint"""
        response = self.client.get("/api/config/schema/")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "properties" in data["data"]

        # Should have all main configuration sections
        properties = data["data"]["properties"]
        expected_sections = [
            "server",
            "database",
            "nlp",
            "llm",
            "reference_sources",
            "proxy_server",
            "logging",
            "security",
        ]
        for section in expected_sections:
            assert section in properties, f"Missing {section} in schema"

    def test_configuration_reload_endpoint(self):
        """Test POST /api/config/reload endpoint"""
        response = self.client.post("/api/config/reload")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "reloaded successfully" in data["data"]["message"]

    def test_configuration_reset_endpoint(self):
        """Test POST /api/config/reset endpoint"""
        # First make a change
        config_manager = get_config_manager()
        config_manager.set("server.port", 9005)

        # Reset to defaults
        response = self.client.post("/api/config/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "reset to defaults" in data["data"]["message"]

        # Verify reset worked (should be back to default port)
        default_port = config_manager.get("server.port")
        assert default_port == 8000  # Default port

    def test_patch_request_validation(self):
        """Test that PATCH requests are properly validated"""
        # Missing path field
        response = self.client.patch("/api/config/", json={"value": "test"})
        assert response.status_code == 422

        # Missing value field
        response = self.client.patch("/api/config/", json={"path": "server.port"})  # noqa: E501
        assert response.status_code == 422

        # Empty path
        response = self.client.patch("/api/config/", json={"path": "", "value": "test"})  # noqa: E501
        assert response.status_code == 400

    def test_configuration_endpoint_error_handling(self):
        """Test proper error handling in configuration endpoints"""
        # Test that endpoints handle errors gracefully without crashing

        # Try to set a read-only or computed value that might cause issues
        update_data = {
            "path": "server.host",
            "value": None,  # Invalid value that should trigger error handling
        }

        response = self.client.patch("/api/config/", json=update_data)

        # Should return an error code, not crash
        assert response.status_code in [400, 422, 500]

        # Response should still be properly formatted
        data = response.json()
        assert "success" in data
        assert data["success"] is False

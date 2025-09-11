from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from config import S3Config


class TestS3SyncIntegration:

    def test_sync_status_endpoint(self, client: TestClient):
        """Test sync status API endpoint."""
        response = client.get("/api/sync/status")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "data" in data
        assert "pending_push_count" in data["data"]
        assert "s3_configured" in data["data"]

    def test_push_changes_without_s3_config(self, client: TestClient):
        """Test push changes without S3 configuration."""
        response = client.post("/api/sync/push", json={"author_id": "test-user"})
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "error"
        assert "not configured" in data["message"]

    @patch("services.s3_sync_manager.DuckDBService")
    def test_push_changes_with_mocked_s3(
        self, mock_duckdb_service, client: TestClient, db_session
    ):
        """Test push changes with mocked S3 service."""
        # Mock the DuckDB service
        mock_conn = Mock()
        mock_duckdb_service.return_value.get_connection.return_value = mock_conn

        # Create a test change event
        from database.models import ChangeEvent

        change = ChangeEvent(
            event_type="create",
            record_type="structure_node",
            record_id="test-id",
            new_data={"title": "Test Node"},
            processed=False,
        )
        db_session.add(change)
        db_session.commit()

        with patch("config.get_settings") as mock_settings:
            mock_config = Mock()
            mock_config.get_s3_config.return_value = S3Config(
                bucket="test-bucket",
                region="us-east-1",
                access_key="test-key",
                secret_key="test-secret",
            )
            mock_settings.return_value = mock_config

            response = client.post("/api/sync/push", json={"author_id": "test-user"})

        assert response.status_code == 200

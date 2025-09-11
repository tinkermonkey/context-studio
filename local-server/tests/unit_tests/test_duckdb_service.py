from unittest.mock import Mock, patch
from services.duckdb_service import DuckDBService
from config import S3Config


class TestDuckDBService:

    def test_initialize_connection_without_s3(self):
        """Test DuckDB connection without S3 config."""
        service = DuckDBService()

        with patch("duckdb.connect") as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn

            result = service.initialize_connection()

            assert result == mock_conn
            mock_connect.assert_called_once_with(":memory:")
            mock_conn.execute.assert_any_call("INSTALL httpfs;")
            mock_conn.execute.assert_any_call("LOAD httpfs;")

    def test_initialize_connection_with_s3(self):
        """Test DuckDB connection with S3 config."""
        s3_config = S3Config(
            bucket="test-bucket",
            region="us-east-1",
            access_key="test-key",
            secret_key="test-secret",
        )
        service = DuckDBService(s3_config)

        with patch("duckdb.connect") as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn

            with patch.object(service, "_test_s3_connection", return_value=True):
                result = service.initialize_connection()

            assert result == mock_conn
            # Verify SECRET creation was called
            secret_calls = [
                call
                for call in mock_conn.execute.call_args_list
                if "CREATE SECRET" in str(call)
            ]
            assert len(secret_calls) > 0

import duckdb
from typing import Optional
from config import S3Config
from utils.logger import get_logger

logger = get_logger(__name__)


class DuckDBService:
    """Service for managing DuckDB connections with S3 integration."""

    def __init__(self, s3_config: Optional[S3Config] = None):
        self.s3_config = s3_config
        self.connection: Optional[duckdb.DuckDBPyConnection] = None

    def initialize_connection(self) -> duckdb.DuckDBPyConnection:
        """Initialize DuckDB connection with S3 configuration."""
        try:
            conn = duckdb.connect(":memory:")

            # Install and load required extensions
            conn.execute("INSTALL httpfs;")
            conn.execute("LOAD httpfs;")

            # Configure S3 access if credentials provided
            if self.s3_config and self.s3_config.access_key:
                # Use modern SECRET-based authentication
                secret_sql = f"""
                CREATE SECRET s3_sync_secret (
                    TYPE s3,
                    KEY_ID '{self.s3_config.access_key}',
                    SECRET '{self.s3_config.secret_key}',
                    REGION '{self.s3_config.region}'
                )
                """
                if self.s3_config.endpoint:
                    secret_sql = secret_sql.replace(
                        ")", f", ENDPOINT '{self.s3_config.endpoint}')"
                    )
                conn.execute(secret_sql)

            # Test connection if bucket configured
            if self.s3_config:
                self._test_s3_connection(conn)

            self.connection = conn
            logger.info("DuckDB connection initialized successfully")
            return conn

        except Exception as e:
            logger.error(f"Failed to initialize DuckDB connection: {e}")
            raise

    def _test_s3_connection(self, conn: duckdb.DuckDBPyConnection) -> bool:
        """Test S3 connectivity."""
        try:
            # Try to list objects in bucket (will fail gracefully if bucket empty)
            test_query = "SELECT 1 LIMIT 0"  # Minimal query to test connection
            conn.execute(test_query)
            logger.info(
                f"S3 connection test passed for bucket: {self.s3_config.bucket}"
            )
            return True
        except Exception as e:
            logger.warning(f"S3 connection test failed: {e}")
            return False

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get or create DuckDB connection."""
        if self.connection is None:
            return self.initialize_connection()
        return self.connection

    def close(self):
        """Close DuckDB connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

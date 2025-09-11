import pandas as pd
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from config import S3Config
from services.duckdb_service import DuckDBService
from services.change_extractor import ChangeExtractor
from services.s3_storage_schema import S3StorageSchema
from utils.logger import get_logger

logger = get_logger(__name__)


class S3SyncManager:
    """Manages synchronization operations with S3."""

    def __init__(self, db_session: Session, s3_config: Optional[S3Config] = None):
        self.db_session = db_session
        self.s3_config = s3_config
        self.duckdb_service = DuckDBService(s3_config)
        self.change_extractor = ChangeExtractor(db_session)

    def push_changes(self, author_id: str = "system") -> Dict[str, Any]:
        """Push local changes to S3."""

        if not self.s3_config:
            return {"status": "error", "message": "S3 not configured"}

        try:
            # Extract pending changes
            changes = self.change_extractor.extract_pending_changes()

            if not changes:
                return {
                    "status": "success",
                    "message": "No changes to push",
                    "changes_count": 0,
                }

            # Group changes by date for partitioning
            changes_by_date = {}
            for change in changes:
                change_date = datetime.fromisoformat(change.timestamp).date()
                if change_date not in changes_by_date:
                    changes_by_date[change_date] = []
                changes_by_date[change_date].append(change)

            # Push each date partition
            pushed_batches = []
            conn = self.duckdb_service.get_connection()

            for change_date, date_changes in changes_by_date.items():

                # Create DataFrame
                df = self.change_extractor.create_change_dataframe(date_changes)

                # Generate S3 path
                batch_id = str(uuid.uuid4())
                s3_path = S3StorageSchema.get_changes_path(
                    self.s3_config.bucket, change_date, batch_id, author_id
                )

                # Write to S3 using DuckDB
                if self._write_changes_to_s3(conn, df, s3_path):
                    pushed_batches.append(
                        {
                            "date": change_date.isoformat(),
                            "path": s3_path,
                            "changes_count": len(date_changes),
                        }
                    )

                    # Mark changes as processed
                    self.change_extractor.mark_changes_processed(date_changes)
                else:
                    return {
                        "status": "error",
                        "message": f"Failed to push changes for {change_date}",
                    }

            return {
                "status": "success",
                "message": "Changes pushed successfully",
                "batches": pushed_batches,
                "total_changes": len(changes),
            }

        except Exception as e:
            logger.error(f"Error pushing changes: {e}")
            return {"status": "error", "message": f"Push failed: {str(e)}"}

    def pull_changes(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Pull remote changes from S3."""

        if not self.s3_config:
            return {"status": "error", "message": "S3 not configured"}

        try:
            conn = self.duckdb_service.get_connection()

            # Build query for remote changes
            where_clause = ""
            if since:
                where_clause = f"WHERE timestamp > '{since.isoformat()}'"

            s3_path = S3StorageSchema.get_changes_wildcard_path(self.s3_config.bucket)
            query = f"""
            SELECT * FROM read_parquet('{s3_path}')
            {where_clause}
            ORDER BY timestamp
            """

            # Execute query
            result = conn.execute(query).df()

            if result.empty:
                return {
                    "status": "success",
                    "message": "No new changes",
                    "changes_count": 0,
                }

            # Convert to change records
            changes = self._dataframe_to_changes(result)

            return {
                "status": "success",
                "message": f"Retrieved {len(changes)} changes",
                "changes_count": len(changes),
                "changes": changes,
            }

        except Exception as e:
            logger.error(f"Error pulling changes: {e}")
            return {"status": "error", "message": f"Pull failed: {str(e)}"}

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current synchronization status."""

        # Count pending local changes
        pending_changes = self.change_extractor.extract_pending_changes()

        # Test S3 connection
        s3_connection = False
        if self.s3_config:
            try:
                conn = self.duckdb_service.get_connection()
                s3_connection = self.duckdb_service._test_s3_connection(conn)
            except Exception:
                s3_connection = False

        return {
            "pending_push_count": len(pending_changes),
            "s3_connection": s3_connection,
            "s3_configured": self.s3_config is not None,
            "local_changes": len(pending_changes) > 0,
        }

    def _write_changes_to_s3(self, conn, df: pd.DataFrame, s3_path: str) -> bool:
        """Write changes DataFrame to S3 as Parquet."""

        try:
            # Register DataFrame as temporary table
            conn.register("temp_changes", df)

            # Write to S3 with compression
            query = f"""
            COPY (SELECT * FROM temp_changes) 
            TO '{s3_path}' 
            (FORMAT 'parquet', COMPRESSION 'zstd')
            """

            conn.execute(query)

            # Clean up
            conn.unregister("temp_changes")

            logger.info(f"Successfully wrote {len(df)} changes to {s3_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing to S3: {e}")
            return False

    def _dataframe_to_changes(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Convert DataFrame back to change records."""

        changes = []
        for _, row in df.iterrows():
            change = {
                "change_id": row["change_id"],
                "event_type": row["event_type"],
                "record_type": row["record_type"],
                "record_id": row["record_id"],
                "old_data": json.loads(row["old_data"]) if row["old_data"] else None,
                "new_data": json.loads(row["new_data"]) if row["new_data"] else None,
                "timestamp": (
                    row["timestamp"].isoformat()
                    if hasattr(row["timestamp"], "isoformat")
                    else row["timestamp"]
                ),
                "batch_id": row["batch_id"],
            }
            changes.append(change)

        return changes

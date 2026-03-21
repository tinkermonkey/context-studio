from datetime import date


class S3StorageSchema:
    """Defines the S3 storage structure and partitioning strategy."""

    @staticmethod
    def get_changes_path(
        bucket: str, change_date: date, batch_id: str, user_id: str = "system"
    ) -> str:
        """Generate S3 path for change batch."""
        return f"s3://{bucket}/changes/year={change_date.year}/month={change_date.month:02d}/day={change_date.day:02d}/batch_{batch_id}_{user_id}.parquet"

    @staticmethod
    def get_metadata_path(bucket: str, entity_type: str) -> str:
        """Generate S3 path for entity metadata."""
        return f"s3://{bucket}/metadata/{entity_type}/metadata.parquet"

    @staticmethod
    def get_changes_wildcard_path(bucket: str) -> str:
        """Generate S3 wildcard path for reading all changes."""
        return f"s3://{bucket}/changes/*/*/*.parquet"

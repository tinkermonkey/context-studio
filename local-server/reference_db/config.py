"""
Configuration models for the reference database.

This module defines Pydantic models for validating reference database configuration.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


# Schema version tracking
REFERENCE_SCHEMA_VERSION = "1.0.0"
EMBEDDING_MODEL_VERSION = "all-MiniLM-L6-v2"  # Default embedding model


class ReferenceConfig(BaseModel):
    """
    Configuration for reference database operations.

    Provides validated parameters for database operations including
    similarity search thresholds, batch sizes, and retry logic.

    Fields:
        database_path: Path to the reference SQLite database file
        similarity_threshold: Cosine similarity threshold (0.0-1.0) for semantic search
        batch_size: Number of items to process in a single batch (1-1000)
        retry_count: Number of retry attempts for failed operations (0-10)
        source_url: HTTPS URL for downloading reference data
        auto_initialize: Whether to auto-populate on first run
        schema_version: Current schema version for validation
        embedding_model: Embedding model identifier for version tracking
    """

    database_path: str = Field(
        default="./reference.db",
        description="Path to the reference database file"
    )

    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for semantic search (0.0-1.0)"
    )

    batch_size: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="Batch size for bulk operations (1-1000)"
    )

    retry_count: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retry attempts for failed operations (0-10)"
    )

    source_url: Optional[str] = Field(
        default=None,
        description="HTTPS URL for downloading reference data"
    )

    auto_initialize: bool = Field(
        default=True,
        description="Automatically initialize database on first access"
    )

    schema_version: str = Field(
        default=REFERENCE_SCHEMA_VERSION,
        description="Database schema version"
    )

    embedding_model: str = Field(
        default=EMBEDDING_MODEL_VERSION,
        description="Embedding model identifier"
    )

    @field_validator('source_url')
    @classmethod
    def validate_https_only(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate that source URLs use HTTPS for security.

        Args:
            v: URL value to validate

        Returns:
            Validated URL

        Raises:
            ValueError: If URL uses HTTP instead of HTTPS
        """
        if v is not None and v.strip():
            if v.startswith('http://'):
                raise ValueError('Source URLs must use HTTPS, not HTTP')
            if not v.startswith('https://'):
                raise ValueError('Source URLs must start with https://')
        return v

    @field_validator('similarity_threshold')
    @classmethod
    def validate_similarity_threshold_range(cls, v: float) -> float:
        """
        Validate similarity threshold is within valid range.

        Args:
            v: Threshold value to validate

        Returns:
            Validated threshold

        Raises:
            ValueError: If threshold is outside [0.0, 1.0] range
        """
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f'Similarity threshold must be between 0.0 and 1.0, got {v}'
            )
        return v

    @field_validator('batch_size')
    @classmethod
    def validate_batch_size_range(cls, v: int) -> int:
        """
        Validate batch size is within acceptable range.

        Args:
            v: Batch size value to validate

        Returns:
            Validated batch size

        Raises:
            ValueError: If batch size is outside [1, 1000] range
        """
        if not (1 <= v <= 1000):
            raise ValueError(
                f'Batch size must be between 1 and 1000, got {v}'
            )
        return v

    @field_validator('retry_count')
    @classmethod
    def validate_retry_count_range(cls, v: int) -> int:
        """
        Validate retry count is within acceptable range.

        Args:
            v: Retry count value to validate

        Returns:
            Validated retry count

        Raises:
            ValueError: If retry count is outside [0, 10] range
        """
        if not (0 <= v <= 10):
            raise ValueError(
                f'Retry count must be between 0 and 10, got {v}'
            )
        return v

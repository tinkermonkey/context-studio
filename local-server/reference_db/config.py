"""
Configuration management for the reference database.

This module provides Pydantic-validated configuration for reference database operations,
including Schema.org API access, embedding models, and operational parameters.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


# Schema version for the reference database structure
# Increment this when making breaking changes to the database schema
REFERENCE_SCHEMA_VERSION = "1.0.0"


class ReferenceConfig(BaseModel):
    """
    Configuration for reference database operations.

    This configuration class provides validated settings for:
    - External API access (Schema.org, WikiData, etc.)
    - Operational limits and thresholds
    - Retry and timeout behaviors

    Default Value Rationale:
        - schema_org_api_url: Standard Schema.org HTTPS endpoint for production use
        - similarity_threshold: 0.7 provides good precision/recall for semantic matching
        - batch_size: 100 balances memory usage with API efficiency
        - retry_count: 3 retries handles transient failures without excessive delay
        - request_timeout: 30s accommodates slow network conditions

    Performance Implications:
        - Higher batch_size reduces API calls but increases memory usage
        - Lower similarity_threshold increases recall but may reduce precision
        - Higher retry_count improves reliability but increases latency on failures

    Examples:
        >>> config = ReferenceConfig()
        >>> config.schema_org_api_url
        'https://schema.org/version/latest/schemaorg-current-https.jsonld'

        >>> config = ReferenceConfig(similarity_threshold=0.8, batch_size=50)
        >>> config.similarity_threshold
        0.8
    """

    # Schema.org API configuration
    schema_org_api_url: str = Field(
        default="https://schema.org/version/latest/schemaorg-current-https.jsonld",
        description="URL to the Schema.org JSON-LD API endpoint"
    )

    # Operational parameters
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score for reference matching (0.0-1.0)"
    )

    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Number of reference nodes to process in a single batch operation"
    )

    retry_count: int = Field(
        default=3,
        description="Number of retry attempts for failed API requests"
    )

    request_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout in seconds for external API requests"
    )

    @field_validator('schema_org_api_url')
    @classmethod
    def validate_schema_org_api_url(cls, v: str) -> str:
        """
        Validate that the Schema.org API URL uses HTTPS.

        Security requirement: External API endpoints must use HTTPS to prevent
        man-in-the-middle attacks and ensure data integrity. Localhost and
        127.0.0.1 are exempted for development/testing purposes.

        Args:
            v: The URL string to validate

        Returns:
            The validated URL string

        Raises:
            ValueError: If the URL uses HTTP for non-localhost addresses

        Examples:
            >>> ReferenceConfig.validate_schema_org_api_url('https://schema.org/api')
            'https://schema.org/api'

            >>> ReferenceConfig.validate_schema_org_api_url('http://localhost:8000/api')
            'http://localhost:8000/api'

            >>> ReferenceConfig.validate_schema_org_api_url('http://example.com/api')
            Traceback (most recent call last):
                ...
            ValueError: Schema.org API URL must use HTTPS for security. HTTP is only allowed for localhost/127.0.0.1.
        """
        if not v:
            raise ValueError("Schema.org API URL cannot be empty")

        # Allow HTTP for localhost and 127.0.0.1 (development/testing)
        if v.startswith('http://'):
            if not ('localhost' in v or '127.0.0.1' in v):
                raise ValueError(
                    "Schema.org API URL must use HTTPS for security. "
                    "HTTP is only allowed for localhost/127.0.0.1."
                )

        return v

    @field_validator('similarity_threshold')
    @classmethod
    def validate_similarity_threshold(cls, v: float) -> float:
        """
        Validate that the similarity threshold is within valid range.

        Args:
            v: The similarity threshold value

        Returns:
            The validated threshold value

        Raises:
            ValueError: If the threshold is outside the range [0.0, 1.0]

        Examples:
            >>> ReferenceConfig.validate_similarity_threshold(0.7)
            0.7

            >>> ReferenceConfig.validate_similarity_threshold(1.5)
            Traceback (most recent call last):
                ...
            ValueError: Similarity threshold must be between 0.0 and 1.0
        """
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"Similarity threshold must be between 0.0 and 1.0, got {v}"
            )
        return v

    @field_validator('batch_size')
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        """
        Validate that the batch size is within reasonable limits.

        Args:
            v: The batch size value

        Returns:
            The validated batch size

        Raises:
            ValueError: If the batch size is outside the range [1, 1000]

        Examples:
            >>> ReferenceConfig.validate_batch_size(100)
            100

            >>> ReferenceConfig.validate_batch_size(5000)
            Traceback (most recent call last):
                ...
            ValueError: Batch size must be between 1 and 1000
        """
        if not (1 <= v <= 1000):
            raise ValueError(
                f"Batch size must be between 1 and 1000, got {v}"
            )
        return v

    @field_validator('retry_count', mode='after')
    @classmethod
    def validate_retry_count(cls, v: int) -> int:
        """
        Validate that the retry count is within reasonable limits.

        Args:
            v: The retry count value

        Returns:
            The validated retry count

        Raises:
            ValueError: If the retry count is outside the range [0, 10]

        Examples:
            >>> ReferenceConfig.validate_retry_count(3)
            3

            >>> ReferenceConfig.validate_retry_count(20)
            Traceback (most recent call last):
                ...
            ValueError: Retry count must be between 0 and 10
        """
        if not (0 <= v <= 10):
            raise ValueError(
                f"Retry count must be between 0 and 10, got {v}"
            )
        return v

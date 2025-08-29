"""Custom exceptions for schema_org module."""
from typing import Optional


class SchemaOrgError(Exception):
    """Base class for schema.org related errors."""


class DownloadError(SchemaOrgError):
    """Raised when downloading the schema.org JSON-LD fails."""
    def __init__(self, message: str, http_status: Optional[int] = None):
        super().__init__(message)
        self.http_status = http_status


class ParseError(SchemaOrgError):
    """Raised when parsing the downloaded JSON-LD fails or is invalid."""


class BackupError(SchemaOrgError):
    """Raised when a backup cannot be created or restore fails."""


class RestoreError(SchemaOrgError):
    """Raised when a restore from backup fails."""


class DatabaseError(SchemaOrgError):
    """Raised for generic database population/operation errors."""


class EmbeddingError(SchemaOrgError):
    """Raised when embedding generation fails in an unrecoverable way."""


class ValidationError(SchemaOrgError):
    """Raised when user input or parameters are invalid."""


class SearchError(SchemaOrgError):
    """Raised for errors during search operations."""

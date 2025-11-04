"""
Custom exceptions for service layer operations.

These exceptions provide type-safe error handling and eliminate the need for
fragile string matching in error handlers.
"""


class ServiceError(Exception):
    """Base exception for all service-layer errors."""
    pass


class NotFoundError(ServiceError):
    """Raised when a requested resource is not found."""

    def __init__(self, resource_type: str, resource_id: str):
        """
        Initialize NotFoundError.

        Args:
            resource_type: Type of resource (e.g., 'StructureNode', 'Link')
            resource_id: Identifier of the resource that was not found
        """
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(f"{resource_type} not found: {resource_id}")


class ValidationError(ServiceError):
    """Raised when validation fails (invalid input, constraint violations, etc.)."""
    pass


class ConflictError(ServiceError):
    """Raised when an operation conflicts with existing state (e.g., uniqueness violations)."""
    pass


class ReferenceNotFoundError(NotFoundError):
    """Raised when a reference link target doesn't exist in reference.db."""

    def __init__(self, source: str, external_id: str):
        """
        Initialize ReferenceNotFoundError.

        Args:
            source: Reference source identifier (e.g., 'schema.org')
            external_id: Source-specific identifier
        """
        self.source = source
        self.external_id = external_id
        super(ServiceError, self).__init__(
            f"Reference not found in reference.db: source='{source}', external_id='{external_id}'"
        )


class CircularReferenceError(ValidationError):
    """Raised when an operation would create a circular reference."""
    pass


class InvalidHierarchyError(ValidationError):
    """Raised when a hierarchy constraint is violated (e.g., wrong parent type)."""
    pass

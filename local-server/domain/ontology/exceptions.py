"""
Exception classes for the Ontology Management domain.

These exceptions represent domain-specific errors that may occur
during ontology operations.
"""


class OntologyError(Exception):
    """Base exception for all ontology domain errors."""

    pass


class EntityNotFoundError(OntologyError):
    """Raised when a requested entity does not exist."""

    def __init__(self, entity_type: str, entity_id: str):
        """
        Initialize the exception.

        Args:
            entity_type: The type of entity that was not found
            entity_id: The ID of the entity that was not found
        """
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with id {entity_id} not found")


class CircularReferenceError(OntologyError):
    """Raised when a circular reference would be created."""

    pass


class DuplicateEntityError(OntologyError):
    """Raised when attempting to create a duplicate entity."""

    pass

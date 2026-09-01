"""
Domain exceptions for the ontology bounded context.

These are separate from the service-layer exceptions in services/exceptions.py.
Domain exceptions represent errors within the ontology domain logic.
No framework or external dependencies - pure Python only.
"""


class OntologyError(Exception):
    """Base exception for all ontology domain errors."""



class EntityNotFoundError(OntologyError):
    """Raised when a domain entity is not found."""

    def __init__(self, entity_type: str, entity_id: str):
        """
        Initialize EntityNotFoundError.

        Args:
            entity_type: Type of entity (e.g., 'Class', 'Taxonomy', 'Scheme')
            entity_id: Identifier of the entity that was not found
        """
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with id '{entity_id}' not found")


class CircularReferenceError(OntologyError):
    """Raised when an operation would create a circular reference."""



class DuplicateEntityError(OntologyError):
    """Raised when attempting to create an entity that already exists."""


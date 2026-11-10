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


class IdentifierConflictError(OntologyError):
    """
    Raised when attempting to create an entity whose `identifier` slug
    is already in use by another ontology entity in the workspace.
    """

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Identifier '{identifier}' is already in use")


class EntityInUseError(OntologyError):
    """Raised when deleting an entity that other entities still reference."""

    pass


class DerivedTypeError(OntologyError):
    """
    Raised when creating an individual of a derived class or a relationship of a
    derived relationship type: the client computes those from other data.
    """

    pass


class DatasetRequiredError(OntologyError):
    """Raised when a taxonomy has several datasets and a write names none of them."""

    def __init__(self, taxonomy_id: str, identifiers: list[str]):
        self.taxonomy_id = taxonomy_id
        self.identifiers = identifiers
        super().__init__(
            f"Taxonomy {taxonomy_id} has several datasets; name one of:"
            f" {', '.join(identifiers)}"
        )


class DatasetMismatchError(OntologyError):
    """
    Raised when a write would cross datasets: an individual with a class outside
    its dataset's taxonomy, or a relationship between individuals of two datasets.
    """

    pass

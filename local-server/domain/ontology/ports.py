"""
Port interfaces for the Ontology bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
"""
from typing import Protocol, Optional, Sequence, Callable

from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Individual,
    Relationship,
    PropertyDefinition,
)
from domain.ontology.value_objects import SearchCriteria
from domain.ontology.events import DomainEvent


class OntologyRepository(Protocol):
    """Repository port for managing ontology entities (Taxonomy, ConceptScheme, Class, etc.)."""

    # Taxonomy operations
    def get_taxonomy(self, taxonomy_id: str) -> Optional[Taxonomy]:
        """Retrieve a taxonomy by ID."""
        ...

    def list_taxonomies(self) -> Sequence[Taxonomy]:
        """List all taxonomies."""
        ...

    def save_taxonomy(self, taxonomy: Taxonomy) -> Taxonomy:
        """Save or update a taxonomy."""
        ...

    def delete_taxonomy(self, taxonomy_id: str) -> None:
        """Delete a taxonomy."""
        ...

    # ConceptScheme operations
    def get_scheme(self, scheme_id: str) -> Optional[ConceptScheme]:
        """Retrieve a concept scheme by ID."""
        ...

    def list_schemes(self, taxonomy_id: str) -> Sequence[ConceptScheme]:
        """List all concept schemes in a taxonomy."""
        ...

    def save_scheme(self, scheme: ConceptScheme) -> ConceptScheme:
        """Save or update a concept scheme."""
        ...

    def delete_scheme(self, scheme_id: str) -> None:
        """Delete a concept scheme."""
        ...

    # Class operations
    def get_class(self, class_id: str) -> Optional[Class]:
        """Retrieve a class by ID."""
        ...

    def list_classes(
        self,
        scheme_id: Optional[str] = None,
        parent_class_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Class]:
        """List classes with optional filtering by scheme or parent."""
        ...

    def search_classes(self, criteria: SearchCriteria) -> Sequence[Class]:
        """Search classes based on search criteria."""
        ...

    def count_classes(self, scheme_id: Optional[str] = None) -> int:
        """Count the number of classes, optionally filtered by scheme."""
        ...

    def save_class(self, cls: Class) -> Class:
        """Save or update a class."""
        ...

    def delete_class(self, class_id: str) -> None:
        """Delete a class."""
        ...

    # Relationship operations
    def get_relationship(self, relationship_id: str) -> Optional[Relationship]:
        """Retrieve a relationship by ID."""
        ...

    def list_relationships(self, source_id: str) -> Sequence[Relationship]:
        """List all relationships from a source entity."""
        ...

    def save_relationship(self, rel: Relationship) -> Relationship:
        """Save or update a relationship."""
        ...

    def delete_relationship(self, relationship_id: str) -> None:
        """Delete a relationship."""
        ...

    # PropertyDefinition operations
    def get_property_definition(self, property_id: str) -> Optional[PropertyDefinition]:
        """Retrieve a property definition by ID."""
        ...

    def get_property_definition_by_identifier(self, identifier: str) -> Optional[PropertyDefinition]:
        """Retrieve a property definition by its identifier string."""
        ...

    def list_property_definitions(self, is_relevant: Optional[bool] = None) -> Sequence[PropertyDefinition]:
        """List all property definitions, optionally filtered by relevance."""
        ...

    def save_property_definition(self, prop: PropertyDefinition) -> PropertyDefinition:
        """Save or update a property definition."""
        ...

    def delete_property_definition(self, property_id: str) -> None:
        """Delete a property definition."""
        ...

    # Individual operations - NOT IMPLEMENTED until a future phase
    def get_individual(self, individual_id: str) -> Optional[Individual]:
        """Retrieve an individual by ID.

        NOT IMPLEMENTED: This method is reserved for a future phase.
        Implementations MUST raise NotImplementedError.
        """
        ...

    def list_individuals(self, class_id: Optional[str] = None) -> Sequence[Individual]:
        """List individuals, optionally filtered by class.

        NOT IMPLEMENTED: This method is reserved for a future phase.
        Implementations MUST raise NotImplementedError.
        """
        ...

    def save_individual(self, individual: Individual) -> Individual:
        """Save or update an individual.

        NOT IMPLEMENTED: This method is reserved for a future phase.
        Implementations MUST raise NotImplementedError.
        """
        ...

    def delete_individual(self, individual_id: str) -> bool:
        """Delete an individual.

        NOT IMPLEMENTED: This method is reserved for a future phase.
        Implementations MUST raise NotImplementedError.
        """
        ...

    # Bulk operations
    def get_all_entities_and_relationships(self) -> tuple[Sequence, Sequence[Relationship]]:
        """Return all entities and relationships for graph building."""
        ...


class EmbeddingService(Protocol):
    """Service for generating vector embeddings from text.

    Embeddings are returned as bytes (serialized float32 numpy arrays)
    matching the current storage format in the database.

    The embed_text method must be thread-safe.
    """

    def embed_text(self, text: str) -> bytes:
        """Generate an embedding for the given text."""
        ...

    def embed_batch(self, texts: list[str]) -> list[bytes]:
        """Generate embeddings for multiple texts."""
        ...

    def similarity(self, embedding_a: bytes, embedding_b: bytes) -> float:
        """Calculate the similarity between two embeddings (0.0 to 1.0)."""
        ...


class EventPublisher(Protocol):
    """Publisher port for domain events."""

    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event."""
        ...

    def subscribe(self, event_type: type, handler: Callable[[DomainEvent], None]) -> None:
        """Subscribe a handler to a specific event type."""
        ...

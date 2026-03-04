"""
Port interfaces for the Ontology bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
"""
from typing import Protocol, Optional, Sequence, List, Callable

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

    def list_classes(self, scheme_id: str) -> Sequence[Class]:
        """List all classes in a concept scheme."""
        ...

    def search_classes(self, criteria: SearchCriteria) -> Sequence[Class]:
        """Search classes based on search criteria."""
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

    def list_property_definitions(self) -> Sequence[PropertyDefinition]:
        """List all property definitions."""
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

    def save_individual(self, individual: Individual) -> Individual:
        """Save or update an individual.

        NOT IMPLEMENTED: This method is reserved for a future phase.
        Implementations MUST raise NotImplementedError.
        """
        ...


class EmbeddingService(Protocol):
    """Service port for generating and comparing embeddings."""

    def generate(self, text: str) -> bytes:
        """Generate an embedding for the given text."""
        ...

    def similarity(self, embedding_a: bytes, embedding_b: bytes) -> float:
        """Calculate the similarity between two embeddings (0.0 to 1.0)."""
        ...

    def batch_generate(self, texts: List[str]) -> List[bytes]:
        """Generate embeddings for multiple texts."""
        ...


class EventPublisher(Protocol):
    """Publisher port for domain events."""

    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event."""
        ...

    def subscribe(self, event_type: type, handler: Callable[[DomainEvent], None]) -> None:
        """Subscribe a handler to a specific event type."""
        ...

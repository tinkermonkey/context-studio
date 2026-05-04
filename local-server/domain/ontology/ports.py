"""
Port interfaces (protocols) for the Ontology Management bounded context.

Ports define contracts for external adapters (persistence, embedding, events, etc.).
Using typing.Protocol enables structural subtyping — implementations need not
explicitly inherit from these protocols.

See ADR-2: Ports are Protocol interfaces (typing.Protocol), not abstract base classes.
Implementations do not inherit from the protocol; they implement the interface structurally.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from .entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from .value_objects import SearchCriteria


class OntologyRepository(Protocol):
    """
    Port for persisting and retrieving ontology entities.

    All CRUD operations on Taxonomy, ConceptScheme, Class, Individual, Relationship,
    and PropertyDefinition entities flow through this repository.
    """

    # Taxonomy operations
    def get_taxonomy(self, taxonomy_id: str) -> Taxonomy | None:
        """
        Retrieve a taxonomy by ID.

        Args:
            taxonomy_id: The ID of the taxonomy

        Returns:
            The Taxonomy if found, None otherwise
        """
        ...

    def list_taxonomies(self) -> list[Taxonomy]:
        """
        Retrieve all taxonomies.

        Returns:
            List of all Taxonomy entities
        """
        ...

    def save_taxonomy(self, taxonomy: Taxonomy) -> Taxonomy:
        """
        Persist a taxonomy (create or update).

        Args:
            taxonomy: The Taxonomy entity to save

        Returns:
            The persisted Taxonomy entity
        """
        ...

    def delete_taxonomy(self, taxonomy_id: str) -> bool:
        """
        Delete a taxonomy by ID.

        Args:
            taxonomy_id: The ID of the taxonomy to delete

        Returns:
            True if the taxonomy was deleted, False if it did not exist
        """
        ...

    # ConceptScheme operations
    def get_concept_scheme(self, concept_scheme_id: str) -> ConceptScheme | None:
        """
        Retrieve a concept scheme by ID.

        Args:
            concept_scheme_id: The ID of the concept scheme

        Returns:
            The ConceptScheme if found, None otherwise
        """
        ...

    def list_concept_schemes(
        self, taxonomy_id: str | None = None
    ) -> list[ConceptScheme]:
        """
        Retrieve concept schemes, optionally filtered by taxonomy.

        Args:
            taxonomy_id: Optional ID to filter schemes to a specific taxonomy

        Returns:
            List of ConceptScheme entities
        """
        ...

    def save_concept_scheme(self, scheme: ConceptScheme) -> ConceptScheme:
        """
        Persist a concept scheme (create or update).

        Args:
            scheme: The ConceptScheme entity to save

        Returns:
            The persisted ConceptScheme entity
        """
        ...

    def delete_concept_scheme(self, concept_scheme_id: str) -> bool:
        """
        Delete a concept scheme by ID.

        Args:
            concept_scheme_id: The ID of the concept scheme to delete

        Returns:
            True if the concept scheme was deleted, False if it did not exist
        """
        ...

    # Class operations
    def get_class(self, class_id: str) -> Class | None:
        """
        Retrieve a class by ID.

        Args:
            class_id: The ID of the class

        Returns:
            The Class if found, None otherwise
        """
        ...

    def list_classes(
        self,
        concept_scheme_id: str | None = None,
        parent_class_id: str | None = None,
        limit: int | None = 100,
        offset: int = 0,
    ) -> list[Class]:
        """
        Retrieve classes with optional filtering and pagination.

        Args:
            concept_scheme_id: Optional concept scheme ID to filter by
            parent_class_id: Optional parent class ID to filter by (for hierarchy)
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip

        Returns:
            List of Class entities
        """
        ...

    def search_classes(self, criteria: SearchCriteria) -> list[Class]:
        """
        Search for classes using search criteria.

        Args:
            criteria: SearchCriteria object specifying query, filters, and pagination

        Returns:
            List of matching Class entities
        """
        ...

    def count_classes(self, concept_scheme_id: str | None = None) -> int:
        """
        Count classes, optionally filtered by scheme.

        Args:
            concept_scheme_id: Optional concept scheme ID to count classes within

        Returns:
            Total count of classes
        """
        ...

    def save_class(self, cls: Class) -> Class:
        """
        Persist a class (create or update).

        Args:
            cls: The Class entity to save

        Returns:
            The persisted Class entity
        """
        ...

    def delete_class(self, class_id: str) -> bool:
        """
        Delete a class by ID.

        Args:
            class_id: The ID of the class to delete

        Returns:
            True if the class was deleted, False if it did not exist
        """
        ...

    # Relationship operations
    def get_relationship(self, relationship_id: str) -> Relationship | None:
        """
        Retrieve a relationship by ID.

        Args:
            relationship_id: The ID of the relationship

        Returns:
            The Relationship if found, None otherwise
        """
        ...

    def list_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        property_id: str | None = None,
    ) -> list[Relationship]:
        """
        Retrieve relationships with optional filtering.

        Args:
            source_id: Optional source entity ID to filter by
            target_id: Optional target entity ID to filter by
            property_id: Optional property definition ID to filter by (relationship type)

        Returns:
            List of Relationship entities
        """
        ...

    def save_relationship(self, relationship: Relationship) -> Relationship:
        """
        Persist a relationship (create or update).

        Args:
            relationship: The Relationship entity to save

        Returns:
            The persisted Relationship entity
        """
        ...

    def delete_relationship(self, relationship_id: str) -> bool:
        """
        Delete a relationship by ID.

        Args:
            relationship_id: The ID of the relationship to delete

        Returns:
            True if the relationship was deleted, False if it did not exist
        """
        ...

    # PropertyDefinition operations
    def get_property_definition(self, property_id: str) -> PropertyDefinition | None:
        """
        Retrieve a property definition by ID.

        Args:
            property_id: The ID of the property definition

        Returns:
            The PropertyDefinition if found, None otherwise
        """
        ...

    def get_property_definition_by_identifier(
        self, identifier: str
    ) -> PropertyDefinition | None:
        """
        Retrieve a property definition by its machine-readable identifier.

        Args:
            identifier: The identifier of the property definition

        Returns:
            The PropertyDefinition if found, None otherwise
        """
        ...

    def list_property_definitions(
        self, is_relevant: bool | None = None
    ) -> list[PropertyDefinition]:
        """
        Retrieve property definitions, optionally filtered by relevance.

        Args:
            is_relevant: Optional filter for relevant property definitions

        Returns:
            List of PropertyDefinition entities
        """
        ...

    def save_property_definition(self, prop: PropertyDefinition) -> PropertyDefinition:
        """
        Persist a property definition (create or update).

        Args:
            prop: The PropertyDefinition entity to save

        Returns:
            The persisted PropertyDefinition entity
        """
        ...

    def delete_property_definition(self, property_id: str) -> bool:
        """
        Delete a property definition by ID.

        Args:
            property_id: The ID of the property definition to delete

        Returns:
            True if the property definition was deleted, False if it did not exist
        """
        ...

    # Individual operations (deferred — all raise NotImplementedError for now)
    def get_individual(self, individual_id: str) -> Individual | None:
        """
        Retrieve an individual by ID.

        Args:
            individual_id: The ID of the individual

        Returns:
            The Individual if found, None otherwise

        Note:
            Currently not implemented — raises NotImplementedError
        """
        ...

    def list_individuals(self, class_id: str | None = None) -> list[Individual]:
        """
        Retrieve individuals, optionally filtered by class.

        Args:
            class_id: Optional class ID to filter by

        Returns:
            List of Individual entities

        Note:
            Currently not implemented — raises NotImplementedError
        """
        ...

    def save_individual(self, individual: Individual) -> Individual:
        """
        Persist an individual (create or update).

        Args:
            individual: The Individual entity to save

        Returns:
            The persisted Individual entity

        Note:
            Currently not implemented — raises NotImplementedError
        """
        ...

    def delete_individual(self, individual_id: str) -> bool:
        """
        Delete an individual by ID.

        Args:
            individual_id: The ID of the individual to delete

        Returns:
            True if the individual was deleted, False if it did not exist

        Note:
            Currently not implemented — raises NotImplementedError
        """
        ...

    # Bulk operations
    def get_all_entities_and_relationships(
        self,
    ) -> tuple[
        Sequence[Taxonomy | ConceptScheme | Class | Individual], Sequence[Relationship]
    ]:
        """
        Retrieve all entities and relationships for graph building.

        Returns:
            Tuple of (all entities as typed domain objects, all relationships) for building a complete graph
        """
        ...


class EmbeddingService(Protocol):
    """
    Port for embedding text into vector space.

    Used to convert text into semantic embeddings for similarity searches
    and clustering operations. Embeddings are returned as fixed-length lists
    of floats for semantic operations.
    """

    def embed(self, text: str) -> list[float]:
        """
        Embed a single text into a vector.

        Args:
            text: The text to embed

        Returns:
            The embedding as a list of floats (fixed-length vector)
        """
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings, each as a list of floats
        """
        ...

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """
        Compute similarity between two embeddings.

        Args:
            embedding_a: First embedding as a list of floats
            embedding_b: Second embedding as a list of floats

        Returns:
            Similarity score as float (typically 0.0 to 1.0)
        """
        ...

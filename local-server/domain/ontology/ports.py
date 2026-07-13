"""
Port interfaces (protocols) for the Ontology Management bounded context.

Ports define contracts for external adapters (persistence, embedding, events, etc.).
Using typing.Protocol enables structural subtyping — implementations need not
explicitly inherit from these protocols.

See ADR-2: Ports are Protocol interfaces (typing.Protocol), not abstract base classes.
Implementations do not inherit from the protocol; they implement the interface structurally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence

from .entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from .value_objects import SearchCriteria

SchemaKind = Literal["class", "property_definition", "relationship"]
MatchedField = Literal["title", "definition"]


class OntologyRepository(Protocol):
    """
    Port for persisting and retrieving ontology entities.

    All CRUD operations on Taxonomy, ConceptScheme, Class, Individual, Relationship,
    and PropertyDefinition entities flow through this repository.
    """

    # Identifier lookup across schema-tier entities
    def get_by_identifier(self, identifier: str) -> Taxonomy | ConceptScheme | Class | None:
        """
        Retrieve a Taxonomy, ConceptScheme, or Class by its globally-unique
        slug identifier.

        Used for pre-save uniqueness checks and identifier-based lookups.
        Property definitions are addressed via
        `get_property_definition_by_identifier` and intentionally NOT covered
        by this method.

        Args:
            identifier: The slug-style identifier (e.g. 'tax_life')

        Returns:
            The matching domain entity, or None if no entity owns this identifier
        """
        ...

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

    def list_taxonomies(
        self,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: str | None = None,
    ) -> list[Taxonomy]:
        """
        Retrieve taxonomies with optional pagination, sorting, and text search.

        Args:
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (title, created_at, last_modified); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query for LIKE search on title

        Returns:
            List of Taxonomy entities
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

    def count_taxonomies(self, query: str | None = None) -> int:
        """
        Count taxonomies, optionally filtered by text search.

        Args:
            query: Optional text query for LIKE search on title

        Returns:
            Total count of taxonomies
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
        self,
        taxonomy_id: str | None = None,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: str | None = None,
    ) -> list[ConceptScheme]:
        """
        Retrieve concept schemes with optional filtering, pagination, sorting, and text search.

        Args:
            taxonomy_id: Optional ID to filter schemes to a specific taxonomy
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (title, created_at, last_modified); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query for LIKE search on title

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

    def count_concept_schemes(
        self, taxonomy_id: str | None = None, query: str | None = None
    ) -> int:
        """
        Count concept schemes, optionally filtered by taxonomy and text search.

        Args:
            taxonomy_id: Optional taxonomy ID to filter by
            query: Optional text query for LIKE search on title

        Returns:
            Total count of concept schemes
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
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: str | None = None,
    ) -> list[Relationship]:
        """
        Retrieve relationships with optional filtering, pagination, sorting, and text search.

        Args:
            source_id: Optional source entity ID to filter by
            target_id: Optional target entity ID to filter by
            property_id: Optional property definition ID to filter by (relationship type)
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (created_at); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query (not applicable for relationships)

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

    def count_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        property_id: str | None = None,
    ) -> int:
        """
        Count relationships, optionally filtered by source, target, or property.

        Args:
            source_id: Optional source entity ID to filter by
            target_id: Optional target entity ID to filter by
            property_id: Optional property definition ID to filter by (relationship type)

        Returns:
            Total count of relationships
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

    def get_property_definition_by_identifier(self, identifier: str) -> PropertyDefinition | None:
        """
        Retrieve a property definition by its machine-readable identifier.

        Args:
            identifier: The identifier of the property definition

        Returns:
            The PropertyDefinition if found, None otherwise
        """
        ...

    def list_property_definitions(
        self,
        is_relevant: bool | None = None,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: str | None = None,
    ) -> list[PropertyDefinition]:
        """
        Retrieve property definitions with optional filtering, pagination, sorting, and text search.

        Args:
            is_relevant: Optional filter for relevant property definitions
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (title, created_at, last_modified); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query for LIKE search on title

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

    def count_property_definitions(
        self, is_relevant: bool | None = None, query: str | None = None
    ) -> int:
        """
        Count property definitions, optionally filtered by relevance and text search.

        Args:
            is_relevant: Optional filter for relevant property definitions
            query: Optional text query for LIKE search on title

        Returns:
            Total count of property definitions
        """
        ...

    def count_property_definitions_referencing_class(self, class_id: str) -> int:
        """
        Count property definitions that reference a class as domain or range.

        Args:
            class_id: The ID of the class to check for references

        Returns:
            Count of property definitions with domain_class_id or range_class_id
            equal to class_id
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

    def list_individuals(
        self,
        class_id: str | None = None,
        limit: int | None = 100,
        offset: int = 0,
    ) -> list[Individual]:
        """
        Retrieve individuals, optionally filtered by class.

        Args:
            class_id: Optional class ID to filter by
            limit: Maximum number of results (None for unlimited)
            offset: Number of results to skip

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
    ) -> tuple[Sequence[Taxonomy | ConceptScheme | Class | Individual], Sequence[Relationship]]:
        """
        Retrieve all entities and relationships for graph building.

        Returns:
            Tuple of (all entities as typed domain objects, all relationships) for building a
            complete graph
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


@dataclass(frozen=True)
class SchemaMatch:
    """
    A schema entity matched by vector similarity to a query embedding.

    Used by the open-extraction individuals flow to find which existing schema
    nodes and relation types an extracted phrase plausibly instantiates.

    Attributes:
        entity_id: ID of the matched entity (class id, property_definition id,
            or relationship id)
        kind: Which kind of schema entity matched
        label: Human-readable title of the matched entity
        score: Similarity score in 0.0-1.0 (1.0 = identical)
        matched_field: Whether the title or the definition embedding produced the
            best score
        external_id: The entity's external schema identifier (e.g. the DR spec
            node id "motivation.goal"), or None if the entity has no external
            reference. Lets grounding emit the identifier the source ontology
            uses rather than only the human-readable title.
        predicate: For a property_definition/relationship match, the bare
            relation verb (e.g. "navigates-to") — the canonical predicate token
            the ground truth uses, distinct from `external_id` (a dotted
            source.predicate.destination identifier) and `label` (a
            "source predicate destination" title). None for class matches and
            when the backing entity does not expose a bare predicate. Lets
            predicate grounding rewrite an extracted verb to the vocabulary's
            canonical predicate rather than to a compound identifier that would
            never match the GT.

    Raises:
        ValueError: If score is not 0.0-1.0
    """

    entity_id: str
    kind: SchemaKind
    label: str
    score: float
    matched_field: MatchedField
    external_id: str | None = None
    predicate: str | None = None

    def __post_init__(self) -> None:
        """Validate schema match invariants."""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be 0.0-1.0, got {self.score}")


class SchemaVectorIndex(Protocol):
    """
    Port for semantic vector search over existing schema entities.

    A first-class persistence capability: it both maintains the title/definition
    embeddings of schema entities (kept in sync on write) and searches them by a
    query embedding. Classes and property definitions carry their own
    embeddings; a relationship is matched via its property definition's
    embeddings. The backing adapter lives in adapters/persistence/sqlite/.
    """

    def index_entity(
        self, entity_id: str, title: str, description: str | None
    ) -> None:
        """
        (Re)compute and persist the title and definition embeddings for one
        schema entity, keeping the vector index in sync with its text.

        Args:
            entity_id: ID of the class or property definition to index.
            title: Current title text (embedded as the title vector).
            description: Current description text (embedded as the definition
                vector); None/empty leaves the definition vector unset.
        """
        ...

    def search(
        self,
        query_embedding: list[float],
        kinds: Sequence[SchemaKind],
        top_k: int = 20,
        threshold: float = 0.0,
        taxonomy_id: str | None = None,
    ) -> list[SchemaMatch]:
        """
        Find schema entities whose title or definition is similar to the query.

        Each candidate reports a single score with matched_field recording which
        vector produced it. How the title and definition scores combine is an
        adapter-level configuration (e.g. taking the higher of the two, or
        letting the curated definition drive the score); the port stays
        indifferent to that choice and only guarantees matched_field is honest
        about the field behind the returned score.

        Args:
            query_embedding: The query vector (e.g. an extracted-phrase embedding).
            kinds: Which schema kinds to include in the search.
            top_k: Maximum number of matches to return, highest score first.
            threshold: Minimum similarity score (0.0-1.0) for inclusion.
            taxonomy_id: When given, restrict results to schema entities that
                belong to this taxonomy — a class directly, or a property
                definition/relationship via its domain class. Lets multiple
                ontologies (e.g. the placeholder and an imported DR spec)
                coexist in the same database without cross-contaminating
                grounding results.

        Returns:
            SchemaMatch objects sorted by descending score (length <= top_k).
            Empty if nothing meets the threshold.
        """
        ...

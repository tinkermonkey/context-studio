"""
Domain entities for the Ontology Management bounded context.

These dataclasses represent the core concepts of an ontology system:
taxonomies, concept schemes, classes, individuals, relationships, and
property definitions. All entities are mutable but enforce invariants
through their methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .value_objects import (
    DataPropertyValue,
    ExternalReference,
    LexicalSense,
    OntologyMapping,
)


@dataclass
class Taxonomy:
    """
    A taxonomy organizes concepts and their relationships at the top level.

    Attributes:
        id: Unique identifier (UUID as string)
        title: Display name for the taxonomy
        definition: Optional longer description
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
    """

    id: str
    title: str
    definition: str | None = None
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1

    def rename(self, new_title: str) -> None:
        """
        Rename the taxonomy.

        Args:
            new_title: The new title

        Raises:
            ValueError: If new_title is empty or only whitespace
        """
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")
        self.title = new_title
        self.last_modified = datetime.now(timezone.utc)


@dataclass
class ConceptScheme:
    """
    A concept scheme groups classes within a taxonomy.

    Attributes:
        id: Unique identifier (UUID as string)
        taxonomy_id: ID of the parent taxonomy
        title: Display name for the scheme
        definition: Optional longer description
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
    """

    id: str
    taxonomy_id: str
    title: str
    definition: str | None = None
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1

    def rename(self, new_title: str) -> None:
        """
        Rename the concept scheme.

        Args:
            new_title: The new title

        Raises:
            ValueError: If new_title is empty or only whitespace
        """
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")
        self.title = new_title
        self.last_modified = datetime.now(timezone.utc)


@dataclass
class Class:
    """
    A class represents a concept in the ontology with optional hierarchical relationships.

    Attributes:
        id: Unique identifier (UUID as string)
        concept_scheme_id: ID of the parent concept scheme
        taxonomy_id: ID of the parent taxonomy
        title: Display name for the class
        definition: Optional longer description
        parent_class_id: Optional ID of the parent class for hierarchy
        structural_property_id: Optional ID of the primary structural relationship property definition
        external_references: List of references to external knowledge bases
        lexical_senses: List of word sense disambiguation entries (e.g., WordNet synsets)
        data_properties: List of data property values on this class
        title_embedding: Optional bytes representing the embedding of the title (serialized float32 array)
        definition_embedding: Optional bytes representing the embedding of the definition (serialized float32 array)
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
    """

    id: str
    concept_scheme_id: str
    taxonomy_id: str
    title: str
    definition: str | None = None
    parent_class_id: str | None = None
    structural_property_id: str | None = None
    external_references: list[ExternalReference] = field(default_factory=list)
    lexical_senses: list[LexicalSense] = field(default_factory=list)
    data_properties: list[DataPropertyValue] = field(default_factory=list)
    title_embedding: bytes | None = None
    definition_embedding: bytes | None = None
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1

    def rename(self, new_title: str) -> None:
        """
        Rename the class.

        Args:
            new_title: The new title

        Raises:
            ValueError: If new_title is empty or only whitespace
        """
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")
        self.title = new_title
        self.last_modified = datetime.now(timezone.utc)

    def add_subclass_of(self, parent_id: str) -> None:
        """
        Set the parent class for this class (hierarchy).

        Args:
            parent_id: The ID of the parent class

        Raises:
            ValueError: If parent_id is the same as this class's id
        """
        if parent_id == self.id:
            raise ValueError("A class cannot be its own parent")
        self.parent_class_id = parent_id
        self.last_modified = datetime.now(timezone.utc)

    def remove_subclass_of(self) -> None:
        """Remove the parent class relationship (set to None)."""
        self.parent_class_id = None
        self.last_modified = datetime.now(timezone.utc)


@dataclass
class Individual:
    """
    An individual is an instance of a class with specific data property values.

    Attributes:
        id: Unique identifier (UUID as string)
        class_id: ID of the class this individual instantiates
        title: Display name for the individual
        definition: Optional longer description
        data_property_values: List of data property values for this individual
        external_references: List of references to external knowledge bases
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
    """

    id: str
    class_id: str
    title: str
    definition: str | None = None
    data_property_values: list[DataPropertyValue] = field(default_factory=list)
    external_references: list[ExternalReference] = field(default_factory=list)
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1

    def rename(self, new_title: str) -> None:
        """
        Rename the individual.

        Args:
            new_title: The new title

        Raises:
            ValueError: If new_title is empty or only whitespace
        """
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")
        self.title = new_title
        self.last_modified = datetime.now(timezone.utc)


@dataclass
class Relationship:
    """
    A typed relationship between two ontology entities.

    Attributes:
        id: Unique identifier (UUID as string)
        source_id: ID of the source entity
        target_id: ID of the target entity
        property_definition_id: ID of the property definition that defines this relationship type
        property_label: Denormalized display label for the relationship type (from PropertyDefinition title)
        created_at: Timestamp of creation (auto-generated on instantiation)

    Raises:
        ValueError: If source_id equals target_id (checked in __post_init__)
    """

    id: str
    source_id: str
    target_id: str
    property_definition_id: str
    property_label: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate relationship invariants."""
        if self.source_id == self.target_id:
            raise ValueError("A relationship cannot have the same source and target")


@dataclass
class PropertyDefinition:
    """
    Defines the type and metadata for a property (relationship type).

    Attributes:
        id: Unique identifier (UUID as string)
        identifier: Machine-readable identifier for the property
        title: Display name for the property
        definition: Optional longer description
        ontology_mapping: Optional mapping to an external ontology standard
        is_relevant: Optional relevance flag (None=not evaluated, True=relevant, False=irrelevant)
        date_created: Timestamp of creation
        date_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
    """

    id: str
    identifier: str
    title: str
    definition: str | None = None
    ontology_mapping: OntologyMapping | None = None
    is_relevant: bool | None = None
    date_created: datetime | None = None
    date_modified: datetime | None = None
    version: int = 1

    def rename(self, new_title: str) -> None:
        """
        Rename the property definition.

        Args:
            new_title: The new title

        Raises:
            ValueError: If new_title is empty or only whitespace
        """
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")
        self.title = new_title
        self.date_modified = datetime.now(timezone.utc)

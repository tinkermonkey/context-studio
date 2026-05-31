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
    Status,
    validate_hex_color,
    validate_identifier,
)


@dataclass
class Taxonomy:
    """
    A taxonomy organizes concepts and their relationships at the top level.

    Attributes:
        id: Unique identifier (UUID as string)
        title: Display name for the taxonomy
        identifier: Slug-style identifier (globally unique, immutable post-create); auto-generated if not provided
        description: Optional longer description
        color: Optional hex color string (e.g. '#a3f2e4')
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
        status: Publication status (draft or published)
    """

    id: str
    title: str
    identifier: str | None = None
    description: str | None = None
    color: str | None = None
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1
    status: Status = Status.DRAFT

    def __post_init__(self) -> None:
        if self.identifier is None:
            import re
            self.identifier = re.sub(r"[^a-z0-9]+", "_", self.title.lower()).strip("_")
        self.identifier = validate_identifier(self.identifier)
        self.color = validate_hex_color(self.color)

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
        identifier: Slug-style identifier (globally unique, immutable post-create); auto-generated if not provided
        description: Optional longer description
        color: Optional hex color string (e.g. '#a3f2e4')
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
        status: Publication status (draft or published)
    """

    id: str
    taxonomy_id: str
    title: str
    identifier: str | None = None
    description: str | None = None
    color: str | None = None
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1
    status: Status = Status.DRAFT

    def __post_init__(self) -> None:
        if self.identifier is None:
            import re
            self.identifier = re.sub(r"[^a-z0-9]+", "_", self.title.lower()).strip("_")
        self.identifier = validate_identifier(self.identifier)
        self.color = validate_hex_color(self.color)

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
        identifier: Slug-style identifier (globally unique, immutable post-create); auto-generated if not provided
        description: Optional longer description
        color: Optional hex color string (e.g. '#a3f2e4')
        parent_class_id: Optional ID of the parent class for hierarchy
        structural_property_id: Optional ID of the primary structural relationship property
        definition
        external_references: List of references to external knowledge bases
        lexical_senses: List of word sense disambiguation entries
        data_properties: List of data property values on this class
        embedding: Optional list of floats representing the semantic embedding
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
        status: Publication status (draft or published)
    """

    id: str
    concept_scheme_id: str
    taxonomy_id: str
    title: str
    identifier: str | None = None
    description: str | None = None
    color: str | None = None
    parent_class_id: str | None = None
    structural_property_id: str | None = None
    external_references: list[ExternalReference] = field(default_factory=list)
    lexical_senses: list[LexicalSense] = field(default_factory=list)
    data_properties: list[DataPropertyValue] = field(default_factory=list)
    embedding: list[float] | None = None
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1
    status: Status = Status.DRAFT
    source_run_id: str | None = None

    def __post_init__(self) -> None:
        if self.identifier is None:
            import re
            self.identifier = re.sub(r"[^a-z0-9]+", "_", self.title.lower()).strip("_")
        self.identifier = validate_identifier(self.identifier)
        self.color = validate_hex_color(self.color)

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
    An individual is an instance of one or more classes with specific data property values.

    An individual can belong to multiple parent classes with an ordered list that matters
    for property attribute inheritance: when two parent Classes declare a property with the
    same name but conflicting type/constraints, the first parent (by class membership order) wins.

    Attributes:
        id: Unique identifier (UUID as string)
        class_ids: Ordered list of IDs of classes this individual instantiates (≥1 required)
        title: Display name for the individual
        description: Optional longer description
        data_properties: List of data property values for this individual
        external_references: List of references to external knowledge bases
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
    """

    id: str
    class_ids: list[str]
    title: str
    description: str | None = None
    data_properties: list[DataPropertyValue] = field(default_factory=list)
    external_references: list[ExternalReference] = field(default_factory=list)
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1
    status: Status = Status.DRAFT
    source_run_id: str | None = None

    def __post_init__(self) -> None:
        """Validate individual invariants."""
        if not self.class_ids:
            raise ValueError("Individual must have at least one parent class")
        if len(self.class_ids) != len(set(self.class_ids)):
            raise ValueError("Individual class list contains duplicates")

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

    def add_parent_class(self, class_id: str) -> None:
        """
        Add a parent class to this individual (appended to the end).

        Args:
            class_id: The ID of the class to add

        Raises:
            ValueError: If class_id is already a parent class of this individual
        """
        if class_id in self.class_ids:
            raise ValueError(f"Class {class_id} is already a parent of this individual")
        self.class_ids.append(class_id)
        self.last_modified = datetime.now(timezone.utc)

    def remove_parent_class(self, class_id: str) -> None:
        """
        Remove a parent class from this individual.

        Args:
            class_id: The ID of the class to remove

        Raises:
            ValueError: If this is the last parent class or if the class is not a parent
        """
        if class_id not in self.class_ids:
            raise ValueError(f"Class {class_id} is not a parent of this individual")
        if len(self.class_ids) == 1:
            raise ValueError(
                "Cannot remove the last parent class; Individual must have at least one"
                " parent class"
            )
        self.class_ids.remove(class_id)
        self.last_modified = datetime.now(timezone.utc)

    def reorder_parent_classes(self, ordered_class_ids: list[str]) -> None:
        """
        Reorder the parent classes for this individual.

        Args:
            ordered_class_ids: The new ordered list of class IDs

        Raises:
            ValueError: If the list is empty, contains duplicates, or doesn't match current classes
        """
        if not ordered_class_ids:
            raise ValueError("Individual must have at least one parent class")
        if len(ordered_class_ids) != len(set(ordered_class_ids)):
            raise ValueError("Ordered class list contains duplicates")
        if set(ordered_class_ids) != set(self.class_ids):
            raise ValueError("Ordered class list must contain exactly the same classes")
        self.class_ids = ordered_class_ids
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
        created_at: Timestamp of creation (auto-generated on instantiation)

    Raises:
        ValueError: If source_id equals target_id (checked in __post_init__)
    """

    id: str
    source_id: str
    target_id: str
    property_definition_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_run_id: str | None = None

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
        description: Optional longer description
        ontology_mapping: Optional mapping to an external ontology standard
        is_relevant: Optional relevance flag (None=not evaluated, True=relevant, False=irrelevant)
        lexical_senses: Word-sense disambiguation entries. A property whose
            label has more than one distinct meaning across the corpus
            (e.g. "service" or "clock") carries one LexicalSense per sense.
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
        status: Publication status (draft or published)
    """

    id: str
    identifier: str
    title: str
    description: str | None = None
    ontology_mapping: OntologyMapping | None = None
    is_relevant: bool | None = None
    lexical_senses: list[LexicalSense] = field(default_factory=list)
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1
    status: Status = Status.DRAFT
    source_run_id: str | None = None

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
        self.last_modified = datetime.now(timezone.utc)

"""
Domain entities for the ontology bounded context.

Entities represent the core business objects with identity and mutable state.
They import only from domain/ontology/value_objects.py and Python stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from domain.ontology.value_objects import (
    NodeType,
    ExternalReference,
    LexicalSense,
    DataPropertyValue,
    OntologyMapping,
)


@dataclass
class Taxonomy:
    """
    The top-level organizational container in the ontology.

    Represents a broad domain of knowledge (e.g., "Technology", "Biology").
    Taxonomies have no parent and are the root-level entities in the hierarchy.
    """

    id: str
    title: str
    description: Optional[str]
    node_type: NodeType  # always NodeType.TAXONOMY
    created_at: str
    updated_at: str
    concept_schemes: List[str] = field(default_factory=list)  # IDs


@dataclass
class ConceptScheme:
    """
    A coherent grouping of related concepts within a taxonomy.

    Inspired by SKOS ConceptScheme. Examples: within a "Technology" taxonomy,
    schemes might be "Programming Languages", "Data Stores", "Protocols".
    """

    id: str
    title: str
    description: Optional[str]
    taxonomy_id: str
    node_type: NodeType  # always NodeType.CONCEPT_SCHEME
    created_at: str
    updated_at: str
    classes: List[str] = field(default_factory=list)  # IDs


@dataclass
class Class:
    """
    An ontology concept that defines a category of things.

    Classes form the primary working entity in Context Studio. They can form
    subclass hierarchies and carry metadata like external references, lexical senses,
    data properties, ontology mappings, and embeddings.
    """

    id: str
    title: str
    definition: Optional[str]
    scheme_id: str
    taxonomy_id: str
    node_type: NodeType  # always NodeType.CLASS
    parent_id: Optional[str]
    created_at: str
    updated_at: str
    subclass_of: List[str] = field(default_factory=list)  # IDs
    external_references: List[ExternalReference] = field(default_factory=list)
    lexical_senses: List[LexicalSense] = field(default_factory=list)
    data_properties: List[DataPropertyValue] = field(default_factory=list)
    ontology_mappings: List[OntologyMapping] = field(default_factory=list)
    embedding: Optional[bytes] = None

    def rename(self, new_title: str) -> None:
        """
        Rename this class, validating the new title is non-empty.

        Args:
            new_title: The new title for this class.

        Raises:
            ValueError: If the new title is empty or contains only whitespace.
        """
        if not new_title or not new_title.strip():
            raise ValueError("Class title cannot be empty")
        self.title = new_title.strip()

    def add_subclass_of(self, parent_id: str) -> None:
        """
        Add a subclass relationship, preventing self-reference.

        Args:
            parent_id: The ID of the parent class.

        Raises:
            ValueError: If the parent ID is the same as this class's ID (self-reference).
        """
        if parent_id == self.id:
            raise ValueError("A class cannot be a subclass of itself")
        if parent_id not in self.subclass_of:
            self.subclass_of.append(parent_id)


@dataclass
class Individual:
    """
    Represents an individual instance of a Class.

    NOTE: Individual support is deferred to a future phase per
    rearchitecture/transformation_roadmap.md. This entity is defined for
    interface completeness only and is not yet functional.
    """

    id: str
    title: str
    class_id: str
    node_type: NodeType  # always NodeType.INDIVIDUAL
    created_at: str
    updated_at: str


@dataclass
class Relationship:
    """
    Represents a directed relationship between two entities.

    Relationships connect entities with a labeled predicate and optional weight
    and metadata for additional context.
    """

    id: str
    source_id: str
    target_id: str
    predicate_id: str
    predicate_label: str
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)
    created_at: str = ""


@dataclass
class PropertyDefinition:
    """
    Defines a reusable property that can be asserted on entities.

    Property definitions establish the schema for data properties and may map to
    external ontologies via URI.
    """

    id: str
    label: str
    description: Optional[str]
    ontology_uri: Optional[str]
    created_at: str
    updated_at: str

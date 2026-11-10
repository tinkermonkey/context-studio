"""
Domain entities for the Ontology Management bounded context.

These dataclasses represent the core concepts of an ontology system:
taxonomies, concept schemes, classes, individuals, relationships, and
property definitions. All entities are mutable but enforce invariants
through their methods.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .value_objects import (
    DataPropertyValue,
    DataType,
    ExternalReference,
    LexicalSense,
    OntologyMapping,
    SourceRevision,
    Status,
    validate_dataset_identifier,
    validate_default_value_against_allowed_values,
    validate_hex_color,
    validate_identifier,
    validate_predicate_identifier,
)


@dataclass
class Taxonomy:
    """
    A taxonomy organizes concepts and their relationships at the top level.

    Attributes:
        id: Unique identifier (UUID as string)
        title: Display name for the taxonomy
        identifier: Slug-style identifier (optional); must be unique if provided
        description: The one-paragraph summary of what the taxonomy is for. Short
            enough to go into every agent's and pipeline's context.
        vision: The full vision statement (markdown): what the taxonomy is for,
            what its classes and relationships model, and how changes are judged.
            Given to strong reasoners (judges, labellers), not to every call.
        color: Optional hex color string (e.g. '#a3f2e4')
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
        status: Publication status (draft or published)
        external_references: References to the source the taxonomy was imported
            from (e.g. the DR spec, whose predicate catalog rides in the metadata)
        mirrored: The taxonomy mirrors an external source of truth (a client's
            spec): nothing auto-applies to it, Context Studio runs no proposals
            of its own on it, and a proposal the client has landed can't be
            reverted here
        source_revision: The source revision the taxonomy was last imported at
    """

    id: str
    title: str
    identifier: str | None = None
    description: str | None = None
    vision: str | None = None
    color: str | None = None
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1
    status: Status = Status.DRAFT
    external_references: list[ExternalReference] = field(default_factory=list)
    mirrored: bool = False
    source_revision: SourceRevision | None = None

    def __post_init__(self) -> None:
        if self.identifier is not None:
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
        identifier: Slug-style identifier (optional); must be unique if provided
        description: The scheme's scope note: what belongs in it and what does not
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
        if self.identifier is not None:
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
        identifier: Slug-style identifier (optional); must be unique if provided
        description: Optional longer description
        color: Optional hex color string (e.g. '#a3f2e4')
        parent_class_id: Optional ID of the parent class for hierarchy
        structural_property_id: Optional ID of the primary structural relationship property
        definition
        derived: Computed by the client from other data (a House kit, say): its
            individuals are never created directly, and extraction doesn't target it
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
    derived: bool = False
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
        if self.identifier is not None:
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
class Dataset:
    """
    A named body of data over one taxonomy's schema.

    A dataset owns individuals; a relationship belongs to its source
    individual's dataset. Several datasets can share a taxonomy's schema
    (schemes, classes, relationship types, attributes) and nothing else.

    Attributes:
        id: Unique identifier (UUID as string)
        taxonomy_id: The taxonomy whose schema the dataset's data uses
        identifier: Slug, unique within the taxonomy
        title: Display name
        yields_to_schema: Schema operations never block on this dataset's data;
            its data follows them instead
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
    """

    id: str
    taxonomy_id: str
    identifier: str
    title: str
    yields_to_schema: bool = False
    created_at: datetime | None = None
    last_modified: datetime | None = None

    def __post_init__(self) -> None:
        """Validate dataset invariants."""
        if not self.title or not self.title.strip():
            raise ValueError("Dataset title cannot be empty")
        self.identifier = validate_dataset_identifier(self.identifier)


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
        dataset_id: The dataset the individual belongs to. Every stored individual
            has one; None only before a write resolves it (see
            domain.ontology.datasets.resolve_dataset_id).
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
    dataset_id: str | None = None

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
        attributes: Values carried on the edge itself (a kit's quantity, unit,
            optional), keyed by name; JSON scalars only. The relationship type's
            attribute definitions say which names are allowed and their datatypes.

    Raises:
        ValueError: If source_id equals target_id, or an attribute is not a
            JSON scalar (checked in __post_init__)
    """

    id: str
    source_id: str
    target_id: str
    property_definition_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_run_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate relationship invariants."""
        if self.source_id == self.target_id:
            raise ValueError("A relationship cannot have the same source and target")
        validate_relationship_attributes(self.attributes)


_ATTRIBUTE_VALUE_TYPES = (str, int, float, bool, type(None))


def same_attribute_value(a: Any, b: Any) -> bool:
    """Whether two attribute values are equal and of the same type (True is not 1, 1 is not 1.0)."""
    return type(a) is type(b) and a == b


def same_attributes(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Whether two attribute maps have the same names, each with the same typed value."""
    return a.keys() == b.keys() and all(same_attribute_value(a[k], b[k]) for k in a)


# The JSON types an edge attribute's value may have, by datatype (edge values are
# scalars, so array and object attributes take none).
_EDGE_VALUE_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "date": (str,),
}
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def edge_value_problem(definition: "AttributeDefinition", value: Any) -> str | None:
    """Why a non-null edge value doesn't fit its attribute definition."""
    datatype = getattr(definition.datatype, "value", definition.datatype)
    types = _EDGE_VALUE_TYPES.get(datatype, ())
    if not isinstance(value, types) or (datatype in ("integer", "number") and isinstance(value, bool)):
        return f"is {datatype}, so {value!r} doesn't fit"
    if datatype == "date" and not _ISO_DATE.fullmatch(value):
        return f"is a date (YYYY-MM-DD), so {value!r} doesn't fit"
    allowed = definition.allowed_values
    text = value if isinstance(value, str) else json.dumps(value)
    if allowed and text not in allowed:
        return f"allows only {allowed}, not {value!r}"
    return None


def edge_default(definition: "AttributeDefinition") -> Any:
    """An edge attribute's default value, read as its datatype (None when it has none)."""
    default = definition.default_value
    if default is None:
        return None
    datatype = getattr(definition.datatype, "value", definition.datatype)
    if datatype in ("integer", "number", "boolean"):
        try:
            return json.loads(default)
        except ValueError:
            return default
    return default


def edge_attribute_values(
    type_identifier: str,
    definitions: list["AttributeDefinition"],
    attributes: dict[str, Any],
) -> dict[str, Any]:
    """
    A relationship's attributes checked against its type's attribute
    definitions: only defined names, each value of its datatype and among its
    allowed values. A required attribute that's missing takes its default, or is
    refused without one. Returns the attributes to store (defaults filled in).

    Raises:
        ValueError: Naming each problem
    """
    validate_relationship_attributes(attributes)
    by_name = {d.identifier: d for d in definitions}
    unknown = sorted(set(attributes) - set(by_name))
    if unknown:
        listed = ", ".join(sorted(by_name)) or "none"
        raise ValueError(
            f"Relationship type {type_identifier!r} does not allow attributes {unknown}"
            f" (allowed: {listed})"
        )
    values = dict(attributes)
    problems = []
    for name, definition in by_name.items():
        value = values.get(name)
        if value is None and definition.is_required:
            default = edge_default(definition)
            if default is None:
                problems.append(f"{name!r} is required")
                continue
            values[name] = value = default
        if value is not None:
            problem = edge_value_problem(definition, value)
            if problem:
                problems.append(f"{name!r} {problem}")
    if problems:
        raise ValueError(
            f"Relationship type {type_identifier!r}: attribute " + "; ".join(problems)
        )
    return values


def validate_relationship_attributes(attributes: Any) -> None:
    """
    Check that relationship attributes map names to JSON scalars.

    Raises:
        ValueError: If attributes is not a dict, a name is not a non-empty
            string, or a value is not a string, number, boolean or null
    """
    if not isinstance(attributes, dict):
        raise ValueError(f"Relationship attributes must be an object, not {attributes!r}")
    for name, value in attributes.items():
        if not isinstance(name, str) or not name:
            raise ValueError(f"Relationship attribute names must be non-empty strings: {name!r}")
        if not isinstance(value, _ATTRIBUTE_VALUE_TYPES):
            raise ValueError(
                f"Relationship attribute {name!r} must be a string, number, boolean or null,"
                f" not {value!r}"
            )


@dataclass
class Predicate:
    """
    A relation verb in a taxonomy's predicate catalog (e.g. "part_of" or
    "navigates-to"). Every relationship type of the taxonomy uses one.

    A taxonomy holds its own catalog, so two taxonomies may both have "part_of".
    The identifier never changes: a rename is a delete with a replacement,
    because clients (DR) embed the predicate in their relationship ids.

    Attributes:
        id: Unique identifier (UUID as string)
        taxonomy_id: The taxonomy whose catalog holds it
        identifier: The verb, unique within the taxonomy
        title: Display name (the identifier when none is given)
        description: What the relation means
        external_references: Client metadata (DR's inverse, category,
            archimate_alignment and semantics ride in its documentation_robotics
            reference's metadata)
        status, version, created_at, last_modified: As on other entities
    """

    id: str
    taxonomy_id: str
    identifier: str
    title: str = ""
    description: str | None = None
    external_references: list[ExternalReference] = field(default_factory=list)
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1
    status: Status = Status.DRAFT

    def __post_init__(self) -> None:
        self.identifier = validate_predicate_identifier(self.identifier)
        if not self.title or not self.title.strip():
            self.title = self.identifier


@dataclass
class PropertyDefinition:
    """
    Defines the type and metadata for a property (relationship type).

    Attributes:
        id: Unique identifier (UUID as string)
        identifier: Machine-readable identifier for the property
        title: Display name for the property
        description: Optional longer description
        predicate_id: The Predicate (in its taxonomy's catalog) this type uses;
            None for a type imported without one (OWL, SKOS, GraphML)
        canonical_predicate: The identifier of that predicate (e.g.
            "navigates-to"), read-only: the repository fills it from predicate_id.
            It's the form extraction clamps predicates to, distinct from the
            display title and the machine identifier.
        ontology_mapping: Optional mapping to an external ontology standard
        domain_class_id: Optional ID of the Class this property's source/subject
            must belong to (rdfs:domain)
        range_class_id: Optional ID of the Class this property's target/object
            must belong to (rdfs:range)
        derived: Computed by the client from other data: its relationships are
            never created directly, and extraction doesn't target it
        external_references: List of references to external knowledge bases
        is_relevant: Optional relevance flag (None=not evaluated, True=relevant, False=irrelevant)
        min_per_source: Fewest relationships of this type a source has (0: optional)
        max_per_source: Most relationships of this type a source has (None: no limit)
        max_per_target: Most relationships of this type a target has (None: no limit).
            DR's cardinality: many-to-many (0, None, None), many-to-one
            max_per_source 1, one-to-many max_per_target 1, one-to-one both
        hierarchy: Its relationships form no cycles (a tree when max_per_source is 1)
        symmetric: A relationship one way holds the other way too
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
    canonical_predicate: str | None = None
    ontology_mapping: OntologyMapping | None = None
    domain_class_id: str | None = None
    range_class_id: str | None = None
    derived: bool = False
    external_references: list[ExternalReference] = field(default_factory=list)
    is_relevant: bool | None = None
    lexical_senses: list[LexicalSense] = field(default_factory=list)
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1
    status: Status = Status.DRAFT
    source_run_id: str | None = None
    predicate_id: str | None = None
    min_per_source: int = 0
    max_per_source: int | None = None
    max_per_target: int | None = None
    hierarchy: bool = False
    symmetric: bool = False

    def structure_problems(self) -> list[str]:
        """
        How its structure is ill-formed: a negative minimum, a maximum below one
        or below the minimum, or a `symmetric` or `hierarchy` type whose domain
        and range differ. (Not checked against stored relationships.)
        """
        problems: list[str] = []
        if isinstance(self.min_per_source, bool) or not isinstance(self.min_per_source, int):
            problems.append("min_per_source must be a whole number")
        elif self.min_per_source < 0:
            problems.append("min_per_source can't be negative")
        for name in ("max_per_source", "max_per_target"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                problems.append(f"{name} must be a whole number of at least 1, or null")
        if (
            not problems
            and self.max_per_source is not None
            and self.min_per_source > self.max_per_source
        ):
            problems.append(
                f"min_per_source ({self.min_per_source}) is above max_per_source"
                f" ({self.max_per_source})"
            )
        for flag in ("symmetric", "hierarchy"):
            if getattr(self, flag) and self.domain_class_id != self.range_class_id:
                problems.append(f"a {flag} relationship type needs the same domain and range")
        return problems

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


@dataclass
class AttributeDefinition:
    """
    Defines the type-level (TBox) declaration of an attribute (OWL DatatypeProperty)
    on a Class, or on a relationship type (an edge attribute such as a kit's quantity).

    AttributeDefinition is the complement to DataPropertyValue (instance/ABox level).
    It declares "Class X has an attribute named Y of type Z with these constraints",
    scoped to exactly one owner: a class (class_id) or a relationship type
    (property_definition_id), whose relationships' attributes are checked against it.

    Attributes:
        id: Unique identifier (UUID as string)
        class_id: ID of the class this attribute is scoped to (None for an edge attribute)
        identifier: Machine-readable identifier for the attribute within its owner
        title: Display name for the attribute
        datatype: The data type (one of: string, integer, number, date, boolean, array, object)
        description: Optional longer description
        is_required: Whether this attribute must be present on instances of the class
        allowed_values: Enum constraint; a list of allowed string values, or None if unconstrained
        default_value: Optional default value (as string)
        sort_order: Display order within the class's attribute list
        external_references: List of references to external knowledge bases (e.g., DR provenance)
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
        status: Publication status (draft or published)
        property_definition_id: ID of the relationship type an edge attribute is on
            (None for a class attribute)
    """

    id: str
    class_id: str | None
    identifier: str
    title: str
    datatype: DataType
    description: str | None = None
    is_required: bool = False
    allowed_values: list[str] | None = None
    default_value: str | None = None
    sort_order: int = 0
    external_references: list[ExternalReference] = field(default_factory=list)
    created_at: datetime | None = None
    last_modified: datetime | None = None
    version: int = 1
    status: Status = Status.DRAFT
    source_run_id: str | None = None
    property_definition_id: str | None = None

    def __post_init__(self) -> None:
        self.identifier = validate_identifier(self.identifier)
        if (self.class_id is None) == (self.property_definition_id is None):
            raise ValueError(
                "An attribute definition belongs to exactly one class or one relationship type"
            )
        if isinstance(self.datatype, str):
            try:
                self.datatype = DataType(self.datatype)
            except ValueError:
                raise ValueError(
                    f"Invalid datatype '{self.datatype}'. Must be one of: "
                    f"{', '.join(dt.value for dt in DataType)}"
                )
        validate_default_value_against_allowed_values(self.default_value, self.allowed_values)

    def rename(self, new_title: str) -> None:
        """
        Rename the attribute definition.

        Args:
            new_title: The new title

        Raises:
            ValueError: If new_title is empty or only whitespace
        """
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")
        self.title = new_title
        self.last_modified = datetime.now(timezone.utc)

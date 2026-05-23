"""
Shared schema neighborhood traversal for refinement pipelines.

Provides utilities to extract schema context around nodes
(parent/sibling/child classes, properties, and extraction examples)
for use by Definition and Connection Refinement pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from domain.ontology.entities import Class, PropertyDefinition, Relationship
from domain.ontology.ports import OntologyRepository


@dataclass(frozen=True)
class ClassNeighborhood:
    """Neighborhood context for a class node."""

    class_id: str
    class_label: str
    parent_class: Class | None = None
    sibling_classes: list[Class] = None
    child_classes: list[Class] = None
    property_definitions: list[PropertyDefinition] = None

    def __post_init__(self) -> None:
        """Initialize default empty lists."""
        if self.sibling_classes is None:
            object.__setattr__(self, "sibling_classes", [])
        if self.child_classes is None:
            object.__setattr__(self, "child_classes", [])
        if self.property_definitions is None:
            object.__setattr__(self, "property_definitions", [])


@dataclass(frozen=True)
class PropertyNeighborhood:
    """Neighborhood context for a property definition."""

    property_id: str
    property_label: str
    domain_neighborhood: ClassNeighborhood | None = None
    range_neighborhood: ClassNeighborhood | None = None
    sibling_properties: list[PropertyDefinition] = None

    def __post_init__(self) -> None:
        """Initialize default empty list."""
        if self.sibling_properties is None:
            object.__setattr__(self, "sibling_properties", [])


@dataclass(frozen=True)
class ExtractionUsage:
    """Example usage of an entity from extraction runs."""

    run_id: str
    entity_id: str
    extracted_text: str
    context: str
    confidence: float
    source_uri: str | None = None


class ExtractionUsageRepository(Protocol):
    """Port for accessing extraction usage examples."""

    def get_usages(
        self,
        entity_id: str,
        limit: int = 50,
    ) -> list[ExtractionUsage]:
        """
        Get extraction examples that reference an entity.

        Args:
            entity_id: ID of the class or property
            limit: Maximum number of results

        Returns:
            List of ExtractionUsage records
        """
        ...


class SchemaNeighborhoodTraversal:
    """Traversal utility for schema neighborhoods."""

    def __init__(
        self,
        ontology_repo: OntologyRepository,
        extraction_repo: ExtractionUsageRepository | None = None,
    ) -> None:
        """
        Initialize traversal with repository ports.

        Args:
            ontology_repo: Port for ontology queries
            extraction_repo: Optional port for extraction usages
        """
        self._ontology = ontology_repo
        self._extraction = extraction_repo

    def get_class_neighborhood(
        self,
        class_id: str,
        depth: int = 1,
    ) -> ClassNeighborhood:
        """
        Get neighborhood context for a class.

        Returns parent class, sibling classes, child classes (up to depth),
        and property definitions declared on this class.

        Args:
            class_id: ID of the class
            depth: Traversal depth (default 1, neighbors only)

        Returns:
            ClassNeighborhood with parent, siblings, children, and properties

        Raises:
            ValueError: If class_id not found
        """
        cls = self._ontology.get_class(class_id)
        if cls is None:
            raise ValueError(f"Class not found: {class_id}")

        parent_class = None
        if cls.parent_class_id:
            parent_class = self._ontology.get_class(cls.parent_class_id)

        sibling_classes = []
        if cls.parent_class_id:
            sibling_classes = self._ontology.list_classes(
                parent_class_id=cls.parent_class_id,
                limit=None,
            )
            sibling_classes = [s for s in sibling_classes if s.id != class_id]

        child_classes = self._ontology.list_classes(
            parent_class_id=class_id,
            limit=None,
        )

        # Get properties used in relationships with this class as source
        relationships = self._ontology.list_relationships(
            source_id=class_id,
            limit=None,
        )
        property_ids = set(r.property_definition_id for r in relationships)
        property_defs = []
        for prop_id in property_ids:
            prop_def = self._ontology.get_property_definition(prop_id)
            if prop_def:
                property_defs.append(prop_def)

        return ClassNeighborhood(
            class_id=class_id,
            class_label=cls.title,
            parent_class=parent_class,
            sibling_classes=sibling_classes,
            child_classes=child_classes,
            property_definitions=property_defs,
        )

    def get_property_neighborhood(
        self,
        property_id: str,
    ) -> PropertyNeighborhood:
        """
        Get neighborhood context for a property definition.

        Returns domain class neighborhood, range class neighborhood,
        and sibling properties on the same domain class.

        Args:
            property_id: ID of the property definition

        Returns:
            PropertyNeighborhood with domain and range contexts

        Raises:
            ValueError: If property_id not found
        """
        prop_def = self._ontology.get_property_definition(property_id)
        if prop_def is None:
            raise ValueError(f"Property definition not found: {property_id}")

        domain_neighborhood = None
        range_neighborhood = None
        sibling_properties = []

        # Find classes using this property by querying relationships
        relationships_using_prop = self._ontology.list_relationships(
            property_id=property_id,
            limit=None,
        )

        if relationships_using_prop:
            # Get neighborhoods from the first few classes using this property
            domain_classes = set(r.source_id for r in relationships_using_prop)
            if domain_classes:
                domain_neighborhood = self.get_class_neighborhood(
                    next(iter(domain_classes))
                )

            range_classes = set(r.target_id for r in relationships_using_prop)
            if range_classes:
                range_neighborhood = self.get_class_neighborhood(
                    next(iter(range_classes))
                )

            # Get sibling properties from the domain class
            if domain_classes:
                domain_class_id = next(iter(domain_classes))
                domain_relationships = self._ontology.list_relationships(
                    source_id=domain_class_id,
                    limit=None,
                )
                sibling_prop_ids = set(
                    r.property_definition_id
                    for r in domain_relationships
                    if r.property_definition_id != property_id
                )
                for sibling_prop_id in sibling_prop_ids:
                    prop = self._ontology.get_property_definition(sibling_prop_id)
                    if prop:
                        sibling_properties.append(prop)

        return PropertyNeighborhood(
            property_id=property_id,
            property_label=prop_def.title,
            domain_neighborhood=domain_neighborhood,
            range_neighborhood=range_neighborhood,
            sibling_properties=sibling_properties,
        )

    def get_extraction_usages(
        self,
        entity_id: str,
        limit: int = 50,
    ) -> list[ExtractionUsage]:
        """
        Get validated extraction examples referencing this entity.

        Returns recent extraction-pipeline candidates that referenced
        this entity, with provenance.

        Args:
            entity_id: ID of class or property
            limit: Maximum number of results

        Returns:
            List of ExtractionUsage records, or empty if no extraction repo
        """
        if not self._extraction:
            return []
        return self._extraction.get_usages(entity_id, limit)

"""
Fake in-memory implementation of OntologyRepository for testing.

This implementation stores all entities in memory using dictionaries.
It enforces uniqueness constraints and supports all CRUD operations for
all entity types including Individuals, Classes, Relationships, and others.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.value_objects import SearchCriteria


class FakeOntologyRepository:
    """In-memory implementation of OntologyRepository for unit testing."""

    def __init__(self) -> None:
        self._taxonomies: dict[str, Taxonomy] = {}
        self._schemes: dict[str, ConceptScheme] = {}
        self._classes: dict[str, Class] = {}
        self._individuals: dict[str, Individual] = {}
        self._relationships: dict[str, Relationship] = {}
        self._property_definitions: dict[str, PropertyDefinition] = {}

    # Taxonomy operations

    def get_taxonomy(self, taxonomy_id: str) -> Taxonomy | None:
        return self._taxonomies.get(taxonomy_id)

    def list_taxonomies(self) -> list[Taxonomy]:
        return list(self._taxonomies.values())

    def save_taxonomy(self, taxonomy: Taxonomy) -> None:
        self._taxonomies[taxonomy.id] = taxonomy

    def delete_taxonomy(self, taxonomy_id: str) -> None:
        self._taxonomies.pop(taxonomy_id, None)

    # ConceptScheme operations

    def get_concept_scheme(self, scheme_id: str) -> ConceptScheme | None:
        return self._schemes.get(scheme_id)

    def list_concept_schemes(
        self, taxonomy_id: str | None = None
    ) -> list[ConceptScheme]:
        results = list(self._schemes.values())
        if taxonomy_id is not None:
            results = [s for s in results if s.taxonomy_id == taxonomy_id]
        return results

    def save_concept_scheme(self, scheme: ConceptScheme) -> None:
        self._schemes[scheme.id] = scheme

    def delete_concept_scheme(self, scheme_id: str) -> None:
        self._schemes.pop(scheme_id, None)

    # Class operations

    def get_class(self, class_id: str) -> Class | None:
        return self._classes.get(class_id)

    def list_classes(
        self,
        scheme_id: str | None = None,
        parent_class_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Class]:
        results = list(self._classes.values())
        if scheme_id is not None:
            results = [c for c in results if c.scheme_id == scheme_id]
        if parent_class_id is not None:
            results = [c for c in results if c.parent_class_id == parent_class_id]
        return results[offset : offset + limit]

    def search_classes(self, criteria: SearchCriteria) -> list[Class]:
        results = list(self._classes.values())

        if criteria.query:
            query_lower = criteria.query.lower()
            results = [
                c
                for c in results
                if query_lower in c.title.lower()
                or (c.description and query_lower in c.description.lower())
            ]

        if criteria.scheme_id:
            results = [c for c in results if c.scheme_id == criteria.scheme_id]

        if criteria.taxonomy_id:
            results = [c for c in results if c.taxonomy_id == criteria.taxonomy_id]

        return results[criteria.offset : criteria.offset + criteria.limit]

    def count_classes(self, scheme_id: str | None = None) -> int:
        if scheme_id:
            return sum(1 for c in self._classes.values() if c.scheme_id == scheme_id)
        return len(self._classes)

    def save_class(self, cls: Class) -> None:
        self._classes[cls.id] = cls

    def delete_class(self, class_id: str) -> None:
        self._classes.pop(class_id, None)

    # Relationship operations

    def get_relationship(self, relationship_id: str) -> Relationship | None:
        return self._relationships.get(relationship_id)

    def list_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        property_id: str | None = None,
    ) -> list[Relationship]:
        results = list(self._relationships.values())
        if source_id is not None:
            results = [r for r in results if r.source_id == source_id]
        if target_id is not None:
            results = [r for r in results if r.target_id == target_id]
        if property_id is not None:
            results = [r for r in results if r.property_definition_id == property_id]
        return results

    def save_relationship(self, relationship: Relationship) -> None:
        self._relationships[relationship.id] = relationship

    def delete_relationship(self, relationship_id: str) -> None:
        self._relationships.pop(relationship_id, None)

    # PropertyDefinition operations

    def get_property_definition(self, property_id: str) -> PropertyDefinition | None:
        return self._property_definitions.get(property_id)

    def get_property_definition_by_identifier(
        self, identifier: str
    ) -> PropertyDefinition | None:
        for prop in self._property_definitions.values():
            if prop.identifier == identifier:
                return prop
        return None

    def list_property_definitions(
        self, is_relevant: bool | None = None
    ) -> list[PropertyDefinition]:
        results = list(self._property_definitions.values())
        if is_relevant is not None:
            results = [p for p in results if p.is_relevant == is_relevant]
        return results

    def save_property_definition(self, prop: PropertyDefinition) -> None:
        self._property_definitions[prop.id] = prop

    def delete_property_definition(self, property_id: str) -> None:
        self._property_definitions.pop(property_id, None)

    # Individual operations

    def get_individual(self, individual_id: str) -> Individual | None:
        return self._individuals.get(individual_id)

    def list_individuals(self, class_id: str | None = None) -> list[Individual]:
        results = list(self._individuals.values())
        if class_id is not None:
            results = [i for i in results if i.class_id == class_id]
        return results

    def save_individual(self, individual: Individual) -> None:
        self._individuals[individual.id] = individual

    def delete_individual(self, individual_id: str) -> None:
        self._individuals.pop(individual_id, None)

    # Bulk operations

    def get_all_entities_and_relationships(self, taxonomy_id: str) -> dict[str, list]:
        return {
            "taxonomies": [t for t in self._taxonomies.values() if t.id == taxonomy_id],
            "schemes": [s for s in self._schemes.values() if s.taxonomy_id == taxonomy_id],
            "classes": [c for c in self._classes.values() if c.taxonomy_id == taxonomy_id],
            "relationships": list(self._relationships.values()),
        }

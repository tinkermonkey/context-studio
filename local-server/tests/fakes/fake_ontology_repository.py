"""
Fake in-memory implementation of OntologyRepository for testing.

This implementation stores all entities in memory using dictionaries.
It enforces uniqueness constraints and supports all CRUD operations except
for Individual-related methods, which raise NotImplementedError.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Optional

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
    """
    In-memory implementation of OntologyRepository for unit testing.

    Stores entities in typed dictionaries and enforces uniqueness constraints.
    Individual operations are not implemented and raise NotImplementedError.
    """

    def __init__(self) -> None:
        """Initialize empty dictionaries for each entity type."""
        self._taxonomies: dict[str, Taxonomy] = {}
        self._schemes: dict[str, ConceptScheme] = {}
        self._classes: dict[str, Class] = {}
        self._relationships: dict[str, Relationship] = {}
        self._property_definitions: dict[str, PropertyDefinition] = {}

    # Taxonomy operations
    def get_taxonomy(self, taxonomy_id: str) -> Optional[Taxonomy]:
        """
        Retrieve a taxonomy by ID.

        Args:
            taxonomy_id: The ID of the taxonomy

        Returns:
            The Taxonomy if found, None otherwise
        """
        return self._taxonomies.get(taxonomy_id)

    def list_taxonomies(self) -> list[Taxonomy]:
        """
        Retrieve all taxonomies.

        Returns:
            List of all Taxonomy entities
        """
        return list(self._taxonomies.values())

    def save_taxonomy(self, taxonomy: Taxonomy) -> None:
        """
        Persist a taxonomy (create or update).

        Args:
            taxonomy: The Taxonomy entity to save
        """
        self._taxonomies[taxonomy.id] = taxonomy

    def delete_taxonomy(self, taxonomy_id: str) -> None:
        """
        Delete a taxonomy by ID.

        Args:
            taxonomy_id: The ID of the taxonomy to delete
        """
        self._taxonomies.pop(taxonomy_id, None)

    # ConceptScheme operations
    def get_concept_scheme(self, scheme_id: str) -> Optional[ConceptScheme]:
        """
        Retrieve a concept scheme by ID.

        Args:
            scheme_id: The ID of the concept scheme

        Returns:
            The ConceptScheme if found, None otherwise
        """
        return self._schemes.get(scheme_id)

    def list_concept_schemes(self, taxonomy_id: Optional[str] = None) -> list[ConceptScheme]:
        """
        Retrieve concept schemes, optionally filtered by taxonomy.

        Args:
            taxonomy_id: Optional ID to filter schemes to a specific taxonomy

        Returns:
            List of ConceptScheme entities
        """
        results = list(self._schemes.values())
        if taxonomy_id is not None:
            results = [s for s in results if s.taxonomy_id == taxonomy_id]
        return results

    def save_concept_scheme(self, scheme: ConceptScheme) -> None:
        """
        Persist a concept scheme (create or update).

        Args:
            scheme: The ConceptScheme entity to save
        """
        self._schemes[scheme.id] = scheme

    def delete_concept_scheme(self, scheme_id: str) -> None:
        """
        Delete a concept scheme by ID.

        Args:
            scheme_id: The ID of the concept scheme to delete
        """
        self._schemes.pop(scheme_id, None)

    # Class operations
    def get_class(self, class_id: str) -> Optional[Class]:
        """
        Retrieve a class by ID.

        Args:
            class_id: The ID of the class

        Returns:
            The Class if found, None otherwise
        """
        return self._classes.get(class_id)

    def list_classes(
        self,
        scheme_id: Optional[str] = None,
        parent_class_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Class]:
        """
        Retrieve classes with optional filtering and pagination.

        Args:
            scheme_id: Optional concept scheme ID to filter by
            parent_class_id: Optional parent class ID to filter by (for hierarchy)
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of Class entities
        """
        results = list(self._classes.values())
        if scheme_id is not None:
            results = [c for c in results if c.scheme_id == scheme_id]
        if parent_class_id is not None:
            results = [c for c in results if c.parent_class_id == parent_class_id]
        return results[offset : offset + limit]

    def search_classes(self, criteria: SearchCriteria) -> list[Class]:
        """
        Search for classes using search criteria.

        Args:
            criteria: SearchCriteria object specifying query, filters, and pagination

        Returns:
            List of matching Class entities
        """
        results = list(self._classes.values())

        # Text-based search on title and description
        if criteria.query:
            query_lower = criteria.query.lower()
            results = [
                c
                for c in results
                if query_lower in c.title.lower()
                or (c.description and query_lower in c.description.lower())
            ]

        # Filter by scheme if provided
        if criteria.scheme_id:
            results = [c for c in results if c.scheme_id == criteria.scheme_id]

        # Filter by taxonomy if provided
        if criteria.taxonomy_id:
            results = [c for c in results if c.taxonomy_id == criteria.taxonomy_id]

        # Apply pagination
        return results[criteria.offset : criteria.offset + criteria.limit]

    def count_classes(self, scheme_id: Optional[str] = None) -> int:
        """
        Count classes, optionally filtered by scheme.

        Args:
            scheme_id: Optional concept scheme ID to count classes within

        Returns:
            Total count of classes
        """
        if scheme_id:
            return sum(1 for c in self._classes.values() if c.scheme_id == scheme_id)
        return len(self._classes)

    def save_class(self, cls: Class) -> None:
        """
        Persist a class (create or update).

        Args:
            cls: The Class entity to save
        """
        self._classes[cls.id] = cls

    def delete_class(self, class_id: str) -> None:
        """
        Delete a class by ID.

        Args:
            class_id: The ID of the class to delete
        """
        self._classes.pop(class_id, None)

    # Relationship operations
    def get_relationship(self, relationship_id: str) -> Optional[Relationship]:
        """
        Retrieve a relationship by ID.

        Args:
            relationship_id: The ID of the relationship

        Returns:
            The Relationship if found, None otherwise
        """
        return self._relationships.get(relationship_id)

    def list_relationships(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        property_id: Optional[str] = None,
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
        results = list(self._relationships.values())
        if source_id is not None:
            results = [r for r in results if r.source_id == source_id]
        if target_id is not None:
            results = [r for r in results if r.target_id == target_id]
        if property_id is not None:
            results = [r for r in results if r.property_definition_id == property_id]
        return results

    def save_relationship(self, relationship: Relationship) -> None:
        """
        Persist a relationship (create or update).

        Args:
            relationship: The Relationship entity to save
        """
        self._relationships[relationship.id] = relationship

    def delete_relationship(self, relationship_id: str) -> None:
        """
        Delete a relationship by ID.

        Args:
            relationship_id: The ID of the relationship to delete
        """
        self._relationships.pop(relationship_id, None)

    # PropertyDefinition operations
    def get_property_definition(self, property_id: str) -> Optional[PropertyDefinition]:
        """
        Retrieve a property definition by ID.

        Args:
            property_id: The ID of the property definition

        Returns:
            The PropertyDefinition if found, None otherwise
        """
        return self._property_definitions.get(property_id)

    def get_property_definition_by_identifier(self, identifier: str) -> Optional[PropertyDefinition]:
        """
        Retrieve a property definition by its machine-readable identifier.

        Args:
            identifier: The identifier of the property definition

        Returns:
            The PropertyDefinition if found, None otherwise
        """
        for prop in self._property_definitions.values():
            if prop.identifier == identifier:
                return prop
        return None

    def list_property_definitions(self, is_relevant: Optional[bool] = None) -> list[PropertyDefinition]:
        """
        Retrieve property definitions, optionally filtered by relevance.

        Args:
            is_relevant: Optional filter for relevant property definitions

        Returns:
            List of PropertyDefinition entities
        """
        # Fake implementation ignores is_relevant filter for now
        return list(self._property_definitions.values())

    def save_property_definition(self, prop: PropertyDefinition) -> None:
        """
        Persist a property definition (create or update).

        Args:
            prop: The PropertyDefinition entity to save
        """
        self._property_definitions[prop.id] = prop

    def delete_property_definition(self, property_id: str) -> None:
        """
        Delete a property definition by ID.

        Args:
            property_id: The ID of the property definition to delete
        """
        self._property_definitions.pop(property_id, None)

    # Individual operations (deferred — all raise NotImplementedError for now)
    def get_individual(self, individual_id: str) -> Optional[Individual]:
        """
        Retrieve an individual by ID.

        Args:
            individual_id: The ID of the individual

        Returns:
            The Individual if found, None otherwise

        Note:
            Currently not implemented — raises NotImplementedError
        """
        raise NotImplementedError("Individual persistence not yet implemented")

    def list_individuals(self, class_id: Optional[str] = None) -> list[Individual]:
        """
        Retrieve individuals, optionally filtered by class.

        Args:
            class_id: Optional class ID to filter by

        Returns:
            List of Individual entities

        Note:
            Currently not implemented — raises NotImplementedError
        """
        raise NotImplementedError("Individual persistence not yet implemented")

    def save_individual(self, individual: Individual) -> None:
        """
        Persist an individual (create or update).

        Args:
            individual: The Individual entity to save

        Note:
            Currently not implemented — raises NotImplementedError
        """
        raise NotImplementedError("Individual persistence not yet implemented")

    def delete_individual(self, individual_id: str) -> None:
        """
        Delete an individual by ID.

        Args:
            individual_id: The ID of the individual to delete

        Note:
            Currently not implemented — raises NotImplementedError
        """
        raise NotImplementedError("Individual persistence not yet implemented")

    # Bulk operations
    def get_all_entities_and_relationships(self, taxonomy_id: str) -> dict[str, list]:
        """
        Retrieve all entities and relationships for a taxonomy.

        Args:
            taxonomy_id: The ID of the taxonomy

        Returns:
            Dictionary containing all entities and relationships
        """
        return {
            "taxonomies": [t for t in self._taxonomies.values() if t.id == taxonomy_id],
            "schemes": [s for s in self._schemes.values() if s.taxonomy_id == taxonomy_id],
            "classes": [c for c in self._classes.values() if c.taxonomy_id == taxonomy_id],
            "relationships": list(self._relationships.values()),
        }

"""
In-memory implementation of OntologyRepository for testing.

Provides a structural implementation of the OntologyRepository port interface
using dictionaries to store entities. Individual support is explicitly deferred
to a future phase per the domain model.
"""

from typing import Optional, Sequence, Dict

from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Individual,
    Relationship,
    PropertyDefinition,
)
from domain.ontology.value_objects import SearchCriteria


class InMemoryOntologyRepository:
    """In-memory repository for ontology entities supporting full CRUD operations."""

    def __init__(self):
        self._taxonomies: Dict[str, Taxonomy] = {}
        self._schemes: Dict[str, ConceptScheme] = {}
        self._classes: Dict[str, Class] = {}
        self._relationships: Dict[str, Relationship] = {}
        self._property_definitions: Dict[str, PropertyDefinition] = {}

    # Taxonomy operations
    def get_taxonomy(self, taxonomy_id: str) -> Optional[Taxonomy]:
        """Retrieve a taxonomy by ID."""
        return self._taxonomies.get(taxonomy_id)

    def list_taxonomies(self) -> Sequence[Taxonomy]:
        """List all taxonomies."""
        return list(self._taxonomies.values())

    def save_taxonomy(self, taxonomy: Taxonomy) -> Taxonomy:
        """Save or update a taxonomy."""
        self._taxonomies[taxonomy.id] = taxonomy
        return taxonomy

    def delete_taxonomy(self, taxonomy_id: str) -> None:
        """Delete a taxonomy."""
        self._taxonomies.pop(taxonomy_id, None)

    # ConceptScheme operations
    def get_scheme(self, scheme_id: str) -> Optional[ConceptScheme]:
        """Retrieve a concept scheme by ID."""
        return self._schemes.get(scheme_id)

    def list_schemes(self, taxonomy_id: str) -> Sequence[ConceptScheme]:
        """List all concept schemes in a taxonomy."""
        return [s for s in self._schemes.values() if s.taxonomy_id == taxonomy_id]

    def save_scheme(self, scheme: ConceptScheme) -> ConceptScheme:
        """Save or update a concept scheme."""
        self._schemes[scheme.id] = scheme
        return scheme

    def delete_scheme(self, scheme_id: str) -> None:
        """Delete a concept scheme."""
        self._schemes.pop(scheme_id, None)

    # Class operations
    def get_class(self, class_id: str) -> Optional[Class]:
        """Retrieve a class by ID."""
        return self._classes.get(class_id)

    def list_classes(self, scheme_id: str) -> Sequence[Class]:
        """List all classes in a concept scheme."""
        return [c for c in self._classes.values() if c.scheme_id == scheme_id]

    def search_classes(self, criteria: SearchCriteria) -> Sequence[Class]:
        """Search classes based on search criteria.

        Performs substring matching on title and definition, and filters by
        optional taxonomy_id and scheme_id.
        """
        results = list(self._classes.values())

        # Filter by query (substring match on title and definition)
        if criteria.query:
            q = criteria.query.lower()
            results = [
                c for c in results
                if q in (c.title or "").lower() or q in (c.definition or "").lower()
            ]

        # Filter by scheme_id
        if criteria.scheme_id:
            results = [c for c in results if c.scheme_id == criteria.scheme_id]

        # Filter by taxonomy_id
        if criteria.taxonomy_id:
            results = [c for c in results if c.taxonomy_id == criteria.taxonomy_id]

        # Apply limit
        return results[:criteria.limit]

    def save_class(self, cls: Class) -> Class:
        """Save or update a class."""
        self._classes[cls.id] = cls
        return cls

    def delete_class(self, class_id: str) -> None:
        """Delete a class."""
        self._classes.pop(class_id, None)

    # Relationship operations
    def get_relationship(self, relationship_id: str) -> Optional[Relationship]:
        """Retrieve a relationship by ID."""
        return self._relationships.get(relationship_id)

    def list_relationships(self, source_id: str) -> Sequence[Relationship]:
        """List all relationships from a source entity."""
        return [r for r in self._relationships.values() if r.source_id == source_id]

    def save_relationship(self, rel: Relationship) -> Relationship:
        """Save or update a relationship."""
        self._relationships[rel.id] = rel
        return rel

    def delete_relationship(self, relationship_id: str) -> None:
        """Delete a relationship."""
        self._relationships.pop(relationship_id, None)

    # PropertyDefinition operations
    def get_property_definition(
        self, property_id: str
    ) -> Optional[PropertyDefinition]:
        """Retrieve a property definition by ID."""
        return self._property_definitions.get(property_id)

    def list_property_definitions(self) -> Sequence[PropertyDefinition]:
        """List all property definitions."""
        return list(self._property_definitions.values())

    def save_property_definition(
        self, prop: PropertyDefinition
    ) -> PropertyDefinition:
        """Save or update a property definition."""
        self._property_definitions[prop.id] = prop
        return prop

    def delete_property_definition(self, property_id: str) -> None:
        """Delete a property definition."""
        self._property_definitions.pop(property_id, None)

    # Individual operations - NOT IMPLEMENTED
    def get_individual(self, individual_id: str) -> Optional[Individual]:
        """Individual support is deferred to a future phase.

        Raises:
            NotImplementedError: Always, as Individual support is not yet implemented.
        """
        raise NotImplementedError(
            "Individual support is deferred to a future phase"
        )

    def save_individual(self, individual: Individual) -> Individual:
        """Individual support is deferred to a future phase.

        Raises:
            NotImplementedError: Always, as Individual support is not yet implemented.
        """
        raise NotImplementedError(
            "Individual support is deferred to a future phase"
        )

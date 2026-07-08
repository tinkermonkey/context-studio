"""Fake in-memory implementation of OntologyRepository for testing.

Provides in-memory implementation of the OntologyRepository port for unit testing.
Supports all CRUD operations for Taxonomies, ConceptSchemes, and Classes.
Individual operations are deferred to Phase 2 and raise NotImplementedError.
"""

from typing import Any
from uuid import uuid4

from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.exceptions import DuplicateEntityError
from domain.ontology.value_objects import SearchCriteria


class FakeOntologyRepository:
    """In-memory implementation of OntologyRepository for unit testing."""

    def __init__(self) -> None:
        self._taxonomies: dict[str, Taxonomy] = {}
        self._schemes: dict[str, ConceptScheme] = {}
        self._classes: dict[str, Class] = {}
        self._relationships: dict[str, Relationship] = {}
        self._property_definitions: dict[str, PropertyDefinition] = {}
        self._individuals: dict[str, Individual] = {}

    # Lookup operations

    def get_by_identifier(self, identifier: str) -> Taxonomy | ConceptScheme | Class | None:
        """Retrieve a Taxonomy, ConceptScheme, or Class by its identifier."""
        for tax in self._taxonomies.values():
            if tax.identifier == identifier:
                return tax
        for scheme in self._schemes.values():
            if scheme.identifier == identifier:
                return scheme
        for cls in self._classes.values():
            if cls.identifier == identifier:
                return cls
        return None

    # Taxonomy operations

    def get_taxonomy(self, taxonomy_id: str) -> Taxonomy | None:
        return self._taxonomies.get(taxonomy_id)

    def list_taxonomies(
        self,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: str = "asc",
        query: str | None = None,
    ) -> list[Taxonomy]:
        results = list(self._taxonomies.values())

        if query:
            query_lower = query.lower()
            results = [t for t in results if query_lower in t.title.lower()]

        if sort_by == "title":
            results.sort(key=lambda t: t.title, reverse=(sort_order == "desc"))
        elif sort_by == "created_at" and hasattr(results[0] if results else None, "created_at"):
            results.sort(
                key=lambda t: getattr(t, "created_at", ""),
                reverse=(sort_order == "desc"),
            )

        end = None if limit is None else offset + limit
        return results[offset:end]

    def save_taxonomy(self, taxonomy: Taxonomy) -> Taxonomy:
        for existing_taxonomy in self._taxonomies.values():
            if existing_taxonomy.title == taxonomy.title and existing_taxonomy.id != taxonomy.id:
                raise DuplicateEntityError(f"Taxonomy with title '{taxonomy.title}' already exists")
        self._taxonomies[taxonomy.id] = taxonomy
        return taxonomy

    def delete_taxonomy(self, taxonomy_id: str) -> bool:
        if taxonomy_id in self._taxonomies:
            self._taxonomies.pop(taxonomy_id)
            return True
        return False

    # ConceptScheme operations

    def get_concept_scheme(self, concept_scheme_id: str) -> ConceptScheme | None:
        return self._schemes.get(concept_scheme_id)

    def list_concept_schemes(
        self,
        taxonomy_id: str | None = None,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: str = "asc",
        query: str | None = None,
    ) -> list[ConceptScheme]:
        results = list(self._schemes.values())
        if taxonomy_id is not None:
            results = [s for s in results if s.taxonomy_id == taxonomy_id]

        if query:
            query_lower = query.lower()
            results = [s for s in results if query_lower in s.title.lower()]

        if sort_by == "title":
            results.sort(key=lambda s: s.title, reverse=(sort_order == "desc"))
        elif sort_by == "created_at" and hasattr(results[0] if results else None, "created_at"):
            results.sort(
                key=lambda s: getattr(s, "created_at", ""),
                reverse=(sort_order == "desc"),
            )

        end = None if limit is None else offset + limit
        return results[offset:end]

    def save_concept_scheme(self, scheme: ConceptScheme) -> ConceptScheme:
        for existing_scheme in self._schemes.values():
            if (
                existing_scheme.title == scheme.title
                and existing_scheme.id != scheme.id
                and existing_scheme.taxonomy_id == scheme.taxonomy_id
            ):
                raise DuplicateEntityError(
                    f"ConceptScheme with title '{scheme.title}' already exists in this" " taxonomy"
                )
        self._schemes[scheme.id] = scheme
        return scheme

    def delete_concept_scheme(self, concept_scheme_id: str) -> bool:
        if concept_scheme_id in self._schemes:
            self._schemes.pop(concept_scheme_id)
            return True
        return False

    # Class operations

    def get_class(self, class_id: str) -> Class | None:
        return self._classes.get(class_id)

    def list_classes(
        self,
        concept_scheme_id: str | None = None,
        parent_class_id: str | None = None,
        limit: int | None = 100,
        offset: int = 0,
    ) -> list[Class]:
        results = list(self._classes.values())
        if concept_scheme_id is not None:
            results = [c for c in results if c.concept_scheme_id == concept_scheme_id]
        if parent_class_id is not None:
            results = [c for c in results if c.parent_class_id == parent_class_id]
        end = None if limit is None else offset + limit
        return results[offset:end]

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

        if criteria.concept_scheme_id:
            results = [c for c in results if c.concept_scheme_id == criteria.concept_scheme_id]

        if criteria.taxonomy_id:
            results = [c for c in results if c.taxonomy_id == criteria.taxonomy_id]

        return results[criteria.offset : criteria.offset + criteria.limit]

    def count_taxonomies(self, query: str | None = None) -> int:
        results = list(self._taxonomies.values())
        if query:
            query_lower = query.lower()
            results = [t for t in results if query_lower in t.title.lower()]
        return len(results)

    def count_concept_schemes(
        self, taxonomy_id: str | None = None, query: str | None = None
    ) -> int:
        results = list(self._schemes.values())
        if taxonomy_id is not None:
            results = [s for s in results if s.taxonomy_id == taxonomy_id]
        if query:
            query_lower = query.lower()
            results = [s for s in results if query_lower in s.title.lower()]
        return len(results)

    def count_classes(self, concept_scheme_id: str | None = None) -> int:
        if concept_scheme_id:
            return sum(
                1 for c in self._classes.values() if c.concept_scheme_id == concept_scheme_id
            )
        return len(self._classes)

    def save_class(self, cls: Class) -> Class:
        for existing_class in self._classes.values():
            if (
                existing_class.title == cls.title
                and existing_class.id != cls.id
                and existing_class.concept_scheme_id == cls.concept_scheme_id
            ):
                raise DuplicateEntityError(
                    f"Class with title '{cls.title}' already exists in this scheme"
                )
        self._classes[cls.id] = cls
        return cls

    def delete_class(self, class_id: str) -> bool:
        if class_id in self._classes:
            self._classes.pop(class_id)
            return True
        return False

    # Relationship operations

    def get_relationship(self, relationship_id: str) -> Relationship | None:
        return self._relationships.get(relationship_id)

    def list_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        property_id: str | None = None,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: str = "asc",
        query: str | None = None,
    ) -> list[Relationship]:
        results = list(self._relationships.values())
        if source_id is not None:
            results = [r for r in results if r.source_id == source_id]
        if target_id is not None:
            results = [r for r in results if r.target_id == target_id]
        if property_id is not None:
            results = [r for r in results if r.property_definition_id == property_id]

        if sort_by == "created_at" and hasattr(results[0] if results else None, "created_at"):
            results.sort(
                key=lambda r: getattr(r, "created_at", ""),
                reverse=(sort_order == "desc"),
            )

        end = None if limit is None else offset + limit
        return results[offset:end]

    def save_relationship(self, relationship: Relationship) -> Relationship:
        self._relationships[relationship.id] = relationship
        return relationship

    def delete_relationship(self, relationship_id: str) -> bool:
        if relationship_id in self._relationships:
            self._relationships.pop(relationship_id)
            return True
        return False

    def count_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        property_id: str | None = None,
    ) -> int:
        results = list(self._relationships.values())
        if source_id is not None:
            results = [r for r in results if r.source_id == source_id]
        if target_id is not None:
            results = [r for r in results if r.target_id == target_id]
        if property_id is not None:
            results = [r for r in results if r.property_definition_id == property_id]
        return len(results)

    # PropertyDefinition operations

    def get_property_definition(self, property_id: str) -> PropertyDefinition | None:
        return self._property_definitions.get(property_id)

    def get_property_definition_by_identifier(self, identifier: str) -> PropertyDefinition | None:
        for prop in self._property_definitions.values():
            if prop.identifier == identifier:
                return prop
        return None

    def list_property_definitions(
        self,
        is_relevant: bool | None = None,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: str = "asc",
        query: str | None = None,
    ) -> list[PropertyDefinition]:
        results = list(self._property_definitions.values())
        if is_relevant is not None:
            results = [p for p in results if p.is_relevant == is_relevant]

        if query:
            query_lower = query.lower()
            results = [p for p in results if query_lower in p.title.lower()]

        if sort_by == "title":
            results.sort(key=lambda p: p.title, reverse=(sort_order == "desc"))
        elif sort_by == "created_at" and hasattr(results[0] if results else None, "created_at"):
            results.sort(
                key=lambda p: getattr(p, "created_at", ""),
                reverse=(sort_order == "desc"),
            )

        end = None if limit is None else offset + limit
        return results[offset:end]

    def save_property_definition(self, prop: PropertyDefinition) -> PropertyDefinition:
        self._property_definitions[prop.id] = prop
        return prop

    def delete_property_definition(self, property_id: str) -> bool:
        if property_id in self._property_definitions:
            self._property_definitions.pop(property_id)
            return True
        return False

    def count_property_definitions(
        self, is_relevant: bool | None = None, query: str | None = None
    ) -> int:
        results = list(self._property_definitions.values())
        if is_relevant is not None:
            results = [p for p in results if p.is_relevant == is_relevant]
        if query:
            query_lower = query.lower()
            results = [p for p in results if query_lower in p.title.lower()]
        return len(results)

    def count_property_definitions_referencing_class(self, class_id: str) -> int:
        return sum(
            1
            for p in self._property_definitions.values()
            if p.domain_class_id == class_id or p.range_class_id == class_id
        )

    # Individual operations

    def get_individual(self, individual_id: str) -> Individual | None:
        """Retrieve an individual by ID.

        Returns None if the individual does not exist.
        """
        return self._individuals.get(individual_id)

    def list_individuals(
        self, class_id: str | None = None, limit: int | None = 100, offset: int = 0
    ) -> list[Individual]:
        """Retrieve all individuals, optionally filtered by class ID.

        Args:
            class_id: Optional class ID to filter by (matches any parent class)
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip

        Returns:
            List of individuals matching the filter
        """
        results = list(self._individuals.values())
        if class_id is not None:
            results = [ind for ind in results if class_id in ind.class_ids]
        end = None if limit is None else offset + limit
        return results[offset:end]

    def save_individual(self, individual: Individual) -> Individual:
        """Save an individual (insert or update).

        Validates that the individual's title is unique within each of its classes.

        Args:
            individual: The Individual to save

        Returns:
            The saved Individual

        Raises:
            DuplicateEntityError: If an individual with this title already exists in any of the
            classes
        """
        # Check for duplicate title within each of the individual's classes
        # (excluding the individual being updated)
        for class_id in individual.class_ids:
            for existing in self._individuals.values():
                if (
                    class_id in existing.class_ids
                    and existing.title == individual.title
                    and existing.id != individual.id
                ):
                    raise DuplicateEntityError(
                        f"Individual with title '{individual.title}' already exists in"
                        f" class '{class_id}'"
                    )
        self._individuals[individual.id] = individual
        return individual

    def delete_individual(self, individual_id: str) -> bool:
        """Delete an individual by ID.

        Args:
            individual_id: The ID of the individual to delete

        Returns:
            True if the individual was deleted, False if it did not exist
        """
        if individual_id in self._individuals:
            self._individuals.pop(individual_id)
            return True
        return False

    # Bulk operations

    def get_all_entities_and_relationships(
        self,
    ) -> tuple[list[Any], list[Relationship]]:
        """
        Retrieve all entities and relationships for graph building.

        Returns:
            Tuple of (all entities, all relationships)
        """
        all_entities = (
            list(self._taxonomies.values())
            + list(self._schemes.values())
            + list(self._classes.values())
            + list(self._individuals.values())
            + list(self._property_definitions.values())
        )
        return (all_entities, list(self._relationships.values()))

    def setup_sample_data(self) -> None:
        """
        Populate the repository with sample taxonomy, concept scheme, and classes.

        Used by e2e tests to provide initial knowledge graph context for extraction.
        """
        # Create sample taxonomy
        taxonomy = Taxonomy(
            id=str(uuid4()),
            identifier="technology_concepts",
            title="Technology Concepts",
            description="Sample taxonomy for tech-related extraction testing",
        )
        self.save_taxonomy(taxonomy)

        # Create sample concept scheme
        scheme = ConceptScheme(
            id=str(uuid4()),
            taxonomy_id=taxonomy.id,
            identifier="tech_terms",
            title="Tech Terms",
            description="Common technology terminology",
        )
        self.save_concept_scheme(scheme)

        # Create sample classes
        classes_data = [
            ("Microsoft", "American multinational software corporation", "microsoft"),
            (
                "Google",
                "American technology company specializing in search and advertising",
                "google",
            ),
            (
                "Apple",
                "American technology company known for consumer electronics",
                "apple",
            ),
            ("Database", "Organized collection of structured data", "database"),
            ("SQL", "Structured Query Language for database management", "sql"),
        ]

        for title, description, identifier in classes_data:
            cls = Class(
                id=str(uuid4()),
                concept_scheme_id=scheme.id,
                taxonomy_id=taxonomy.id,
                identifier=identifier,
                title=title,
                description=description,
            )
            self.save_class(cls)

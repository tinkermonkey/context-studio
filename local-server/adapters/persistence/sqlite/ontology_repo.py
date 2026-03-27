"""
SQLite adapter implementing the OntologyRepository port.

Provides persistence for all ontology entities: Taxonomy, ConceptScheme, Class,
Individual, Relationship, and PropertyDefinition. Uses SQLAlchemy ORM and
single-table inheritance with a node_type discriminator.

Key responsibilities:
- CRUD operations on all entity types
- Relationship management (including validation)
- Full-text and semantic search
- Hierarchical queries (parent-child relationships)
"""

from typing import Optional, Any, cast
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Individual,
    Relationship,
    PropertyDefinition,
)
from domain.ontology.value_objects import SearchCriteria, NodeType

from adapters.persistence.sqlite.models import (
    OntologyEntity,
    Relationship as RelationshipORM,
    PropertyDefinition as PropertyDefinitionORM,
)
from adapters.persistence.sqlite.mappers import (
    map_orm_to_domain,
    map_domain_to_orm,
    map_relationship_orm_to_domain,
    map_relationship_domain_to_orm,
)


class SQLiteOntologyRepository:
    """
    SQLAlchemy-based implementation of the OntologyRepository port (structural subtyping).

    Manages persistence of all ontology entities using a unified single-table
    inheritance pattern with node_type discriminator. Enforces invariants
    and maintains referential integrity.

    Attributes:
        session: SQLAlchemy session for database access
    """

    def __init__(self, session: Session) -> None:
        """
        Initialize the repository with a database session.

        Args:
            session: SQLAlchemy Session instance for this request/operation
        """
        self.session = session

    # ==================== Taxonomy CRUD ====================

    def get_taxonomy(self, taxonomy_id: str) -> Optional[Taxonomy]:
        """
        Retrieve a taxonomy by ID.

        Args:
            taxonomy_id: UUID of the taxonomy

        Returns:
            Taxonomy entity if found, None otherwise
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == taxonomy_id,
                    OntologyEntity.node_type == NodeType.TAXONOMY,
                )
            )
            .first()
        )
        if orm_entity is None:
            return None
        return cast(Taxonomy, map_orm_to_domain(orm_entity))

    def list_taxonomies(self) -> list[Taxonomy]:
        """
        Retrieve all taxonomies.

        Returns:
            Sequence of Taxonomy entities
        """
        orm_entities = (
            self.session.query(OntologyEntity)
            .filter(OntologyEntity.node_type == NodeType.TAXONOMY)
            .all()
        )
        return [cast(Taxonomy, map_orm_to_domain(e)) for e in orm_entities]

    def save_taxonomy(self, taxonomy: Taxonomy) -> Taxonomy:
        """
        Create or update a taxonomy.

        Args:
            taxonomy: Taxonomy entity to save

        Returns:
            Saved Taxonomy entity (with timestamps set)

        Raises:
            ValueError: If title is empty
        """
        if not taxonomy.title or not taxonomy.title.strip():
            raise ValueError("Taxonomy title cannot be empty")

        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == taxonomy.id,
                    OntologyEntity.node_type == NodeType.TAXONOMY,
                )
            )
            .first()
        )

        if orm_entity is None:
            # Create new
            orm_entity = OntologyEntity(
                id=taxonomy.id,
                node_type=NodeType.TAXONOMY,
                title=taxonomy.title,
                description=taxonomy.description,
                created_at=datetime.now(timezone.utc),
                last_modified=datetime.now(timezone.utc),
                version=1,
            )
            self.session.add(orm_entity)
        else:
            # Update existing
            orm_entity.title = taxonomy.title  # type: ignore[assignment]
            orm_entity.description = taxonomy.description  # type: ignore[assignment]
            orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.version = orm_entity.version + 1  # type: ignore[assignment]

        self.session.flush()
        return cast(Taxonomy, map_orm_to_domain(orm_entity))

    def delete_taxonomy(self, taxonomy_id: str) -> bool:
        """
        Delete a taxonomy and all its children (cascade).

        Args:
            taxonomy_id: UUID of the taxonomy

        Returns:
            True if deleted, False if not found
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == taxonomy_id,
                    OntologyEntity.node_type == NodeType.TAXONOMY,
                )
            )
            .first()
        )

        if orm_entity is None:
            return False

        self.session.delete(orm_entity)
        self.session.flush()
        return True

    # ==================== ConceptScheme CRUD ====================

    def get_concept_scheme(self, concept_scheme_id: str) -> Optional[ConceptScheme]:
        """
        Retrieve a concept scheme by ID.

        Args:
            concept_scheme_id: UUID of the concept scheme

        Returns:
            ConceptScheme entity if found, None otherwise
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == concept_scheme_id,
                    OntologyEntity.node_type == NodeType.CONCEPT_SCHEME,
                )
            )
            .first()
        )
        if orm_entity is None:
            return None
        return cast(ConceptScheme, map_orm_to_domain(orm_entity))

    def list_concept_schemes(
        self, taxonomy_id: Optional[str] = None
    ) -> list[ConceptScheme]:
        """
        List concept schemes, optionally filtered by taxonomy.

        Args:
            taxonomy_id: Optional taxonomy ID to filter by

        Returns:
            Sequence of ConceptScheme entities
        """
        query = self.session.query(OntologyEntity).filter(
            OntologyEntity.node_type == NodeType.CONCEPT_SCHEME
        )

        if taxonomy_id is not None:
            query = query.filter(OntologyEntity.taxonomy_id == taxonomy_id)

        orm_entities = query.all()
        return [cast(ConceptScheme, map_orm_to_domain(e)) for e in orm_entities]

    def save_concept_scheme(self, scheme: ConceptScheme) -> ConceptScheme:
        """
        Create or update a concept scheme.

        Args:
            scheme: ConceptScheme entity to save

        Returns:
            Saved ConceptScheme entity

        Raises:
            ValueError: If title is empty or parent taxonomy doesn't exist
        """
        if not scheme.title or not scheme.title.strip():
            raise ValueError("ConceptScheme title cannot be empty")

        # Verify parent taxonomy exists
        parent_taxonomy = self.get_taxonomy(scheme.taxonomy_id)
        if parent_taxonomy is None:
            raise ValueError(
                f"Parent taxonomy {scheme.taxonomy_id} does not exist"
            )

        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == scheme.id,
                    OntologyEntity.node_type == NodeType.CONCEPT_SCHEME,
                )
            )
            .first()
        )

        if orm_entity is None:
            # Create new
            orm_entity = OntologyEntity(
                id=scheme.id,
                node_type=NodeType.CONCEPT_SCHEME,
                taxonomy_id=scheme.taxonomy_id,
                title=scheme.title,
                description=scheme.description,
                created_at=datetime.now(timezone.utc),
                last_modified=datetime.now(timezone.utc),
                version=1,
            )
            self.session.add(orm_entity)
        else:
            # Update existing
            orm_entity.title = scheme.title  # type: ignore[assignment]
            orm_entity.description = scheme.description  # type: ignore[assignment]
            orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.version = orm_entity.version + 1  # type: ignore[assignment]

        self.session.flush()
        return cast(ConceptScheme, map_orm_to_domain(orm_entity))

    def delete_concept_scheme(self, concept_scheme_id: str) -> bool:
        """
        Delete a concept scheme and all its classes (cascade).

        Args:
            concept_scheme_id: UUID of the concept scheme

        Returns:
            True if deleted, False if not found
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == concept_scheme_id,
                    OntologyEntity.node_type == NodeType.CONCEPT_SCHEME,
                )
            )
            .first()
        )

        if orm_entity is None:
            return False

        self.session.delete(orm_entity)
        self.session.flush()
        return True

    # ==================== Class CRUD ====================

    def get_class(self, class_id: str) -> Optional[Class]:
        """
        Retrieve a class by ID.

        Args:
            class_id: UUID of the class

        Returns:
            Class entity if found, None otherwise
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == class_id,
                    OntologyEntity.node_type == NodeType.CLASS,
                )
            )
            .first()
        )
        if orm_entity is None:
            return None
        return cast(Class, map_orm_to_domain(orm_entity))

    def list_classes(
        self,
        concept_scheme_id: Optional[str] = None,
        parent_class_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Class]:
        """
        List classes, optionally filtered by concept scheme or parent class.

        Args:
            concept_scheme_id: Optional concept scheme ID to filter by
            parent_class_id: Optional parent class ID to filter by
            limit: Maximum number of results to return (default 100)
            offset: Number of results to skip (default 0)

        Returns:
            Sequence of Class entities
        """
        query = self.session.query(OntologyEntity).filter(
            OntologyEntity.node_type == NodeType.CLASS
        )

        if concept_scheme_id is not None:
            query = query.filter(OntologyEntity.concept_scheme_id == concept_scheme_id)

        if parent_class_id is not None:
            query = query.filter(OntologyEntity.parent_class_id == parent_class_id)

        orm_entities = query.limit(limit).offset(offset).all()
        return [cast(Class, map_orm_to_domain(e)) for e in orm_entities]

    def count_classes(
        self,
        concept_scheme_id: Optional[str] = None,
        parent_class_id: Optional[str] = None,
    ) -> int:
        """
        Count classes matching optional filters.

        Args:
            concept_scheme_id: Optional concept scheme ID to filter by
            parent_class_id: Optional parent class ID to filter by

        Returns:
            Number of matching Class entities
        """
        query = self.session.query(OntologyEntity).filter(
            OntologyEntity.node_type == NodeType.CLASS
        )

        if concept_scheme_id is not None:
            query = query.filter(OntologyEntity.concept_scheme_id == concept_scheme_id)

        if parent_class_id is not None:
            query = query.filter(OntologyEntity.parent_class_id == parent_class_id)

        return query.count()

    def save_class(self, cls: Class) -> Class:
        """
        Create or update a class.

        Validates parent class hierarchy to prevent cycles.

        Args:
            cls: Class entity to save

        Returns:
            Saved Class entity

        Raises:
            ValueError: If title is empty, parent concept scheme doesn't exist,
                       parent class doesn't exist, or would create a cycle
        """
        if not cls.title or not cls.title.strip():
            raise ValueError("Class title cannot be empty")

        # Verify parent concept scheme exists
        parent_scheme = self.get_concept_scheme(cls.concept_scheme_id)
        if parent_scheme is None:
            raise ValueError(
                f"Parent concept scheme {cls.concept_scheme_id} does not exist"
            )

        # Verify parent taxonomy exists
        parent_taxonomy = self.get_taxonomy(cls.taxonomy_id)
        if parent_taxonomy is None:
            raise ValueError(
                f"Parent taxonomy {cls.taxonomy_id} does not exist"
            )

        # If parent class is set, verify it exists and check for cycles
        if cls.parent_class_id is not None:
            if cls.parent_class_id == cls.id:
                raise ValueError("A class cannot be its own parent")

            parent_class = self.get_class(cls.parent_class_id)
            if parent_class is None:
                raise ValueError(
                    f"Parent class {cls.parent_class_id} does not exist"
                )

            # Check for cycles in hierarchy
            if self._would_create_cycle(cls.id, cls.parent_class_id):
                raise ValueError(
                    f"Setting parent class {cls.parent_class_id} would create a cycle"
                )

        # Verify structural property if set
        if cls.structural_property_id is not None:
            struct_prop = self.get_property_definition(cls.structural_property_id)
            if struct_prop is None:
                raise ValueError(
                    f"Structural property {cls.structural_property_id} does not exist"
                )

        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == cls.id,
                    OntologyEntity.node_type == NodeType.CLASS,
                )
            )
            .first()
        )

        if orm_entity is None:
            # Create new
            orm_entity = map_domain_to_orm(cls)
            orm_entity.created_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.version = 1  # type: ignore[assignment]
            self.session.add(orm_entity)
        else:
            # Update existing
            mapped_orm = map_domain_to_orm(cls)
            orm_entity.title = cls.title  # type: ignore[assignment]
            orm_entity.description = cls.description  # type: ignore[assignment]
            orm_entity.parent_class_id = cls.parent_class_id  # type: ignore[assignment]
            orm_entity.structural_property_id = cls.structural_property_id  # type: ignore[assignment]
            orm_entity.external_references = mapped_orm.external_references  # type: ignore[assignment]
            orm_entity.lexical_senses = mapped_orm.lexical_senses  # type: ignore[assignment]
            orm_entity.data_properties = mapped_orm.data_properties  # type: ignore[assignment]
            orm_entity.embedding = mapped_orm.embedding  # type: ignore[assignment]
            orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.version = orm_entity.version + 1  # type: ignore[assignment]

        self.session.flush()
        return cast(Class, map_orm_to_domain(orm_entity))

    def delete_class(self, class_id: str) -> bool:
        """
        Delete a class and all its children (cascade).

        Args:
            class_id: UUID of the class

        Returns:
            True if deleted, False if not found
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == class_id,
                    OntologyEntity.node_type == NodeType.CLASS,
                )
            )
            .first()
        )

        if orm_entity is None:
            return False

        self.session.delete(orm_entity)
        self.session.flush()
        return True

    def search_classes(self, criteria: SearchCriteria) -> list[Class]:
        """
        Search classes by text and optional filters.

        Supports full-text search on title and description, filtering by
        type, taxonomy, concept scheme, parent, and pagination.

        Args:
            criteria: SearchCriteria with query, filters, and pagination

        Returns:
            Sequence of matching Class entities
        """
        query = self.session.query(OntologyEntity).filter(
            OntologyEntity.node_type == NodeType.CLASS
        )

        # Text search
        if criteria.query:
            search_term = f"%{criteria.query}%"
            query = query.filter(
                or_(
                    OntologyEntity.title.ilike(search_term),
                    OntologyEntity.description.ilike(search_term),
                )
            )

        # Filter by node types (always CLASS for this method, but support future)
        if criteria.node_types:
            query = query.filter(
                OntologyEntity.node_type.in_(
                    [nt.value for nt in criteria.node_types]
                )
            )

        # Filter by taxonomy
        if criteria.taxonomy_id:
            query = query.filter(
                OntologyEntity.taxonomy_id == criteria.taxonomy_id
            )

        # Filter by concept scheme
        if criteria.concept_scheme_id:
            query = query.filter(
                OntologyEntity.concept_scheme_id == criteria.concept_scheme_id
            )

        # Filter by parent
        if criteria.parent_id:
            query = query.filter(
                OntologyEntity.parent_class_id == criteria.parent_id
            )

        # Apply pagination
        query = query.limit(criteria.limit).offset(criteria.offset)

        orm_entities = query.all()
        return [cast(Class, map_orm_to_domain(e)) for e in orm_entities]

    # ==================== Individual CRUD ====================

    def get_individual(self, individual_id: str) -> Optional[Individual]:
        """
        Retrieve an individual by ID.

        Args:
            individual_id: UUID of the individual

        Returns:
            Individual entity if found, None otherwise
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == individual_id,
                    OntologyEntity.node_type == NodeType.INDIVIDUAL,
                )
            )
            .first()
        )
        if orm_entity is None:
            return None
        return cast(Individual, map_orm_to_domain(orm_entity))

    def list_individuals(
        self, class_id: Optional[str] = None
    ) -> list[Individual]:
        """
        List individuals, optionally filtered by class.

        Args:
            class_id: Optional class ID to filter by (rdf:type)

        Returns:
            Sequence of Individual entities
        """
        query = self.session.query(OntologyEntity).filter(
            OntologyEntity.node_type == NodeType.INDIVIDUAL
        )

        if class_id is not None:
            query = query.filter(OntologyEntity.class_id == class_id)

        orm_entities = query.all()
        return [cast(Individual, map_orm_to_domain(e)) for e in orm_entities]

    def save_individual(self, individual: Individual) -> Individual:
        """
        Create or update an individual.

        Args:
            individual: Individual entity to save

        Returns:
            Saved Individual entity

        Raises:
            ValueError: If title is empty or parent class doesn't exist
        """
        if not individual.title or not individual.title.strip():
            raise ValueError("Individual title cannot be empty")

        # Verify parent class exists
        parent_class = self.get_class(individual.class_id)
        if parent_class is None:
            raise ValueError(
                f"Parent class {individual.class_id} does not exist"
            )

        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == individual.id,
                    OntologyEntity.node_type == NodeType.INDIVIDUAL,
                )
            )
            .first()
        )

        if orm_entity is None:
            # Create new
            orm_entity = map_domain_to_orm(individual)
            orm_entity.created_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.version = 1  # type: ignore[assignment]
            self.session.add(orm_entity)
        else:
            # Update existing
            mapped_orm = map_domain_to_orm(individual)
            orm_entity.title = individual.title  # type: ignore[assignment]
            orm_entity.description = individual.description  # type: ignore[assignment]
            orm_entity.data_properties = mapped_orm.data_properties  # type: ignore[assignment]
            orm_entity.external_references = mapped_orm.external_references  # type: ignore[assignment]
            orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.version = orm_entity.version + 1  # type: ignore[assignment]

        self.session.flush()
        return cast(Individual, map_orm_to_domain(orm_entity))

    def delete_individual(self, individual_id: str) -> bool:
        """
        Delete an individual.

        Args:
            individual_id: UUID of the individual

        Returns:
            True if deleted, False if not found
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == individual_id,
                    OntologyEntity.node_type == NodeType.INDIVIDUAL,
                )
            )
            .first()
        )

        if orm_entity is None:
            return False

        self.session.delete(orm_entity)
        self.session.flush()
        return True

    # ==================== PropertyDefinition CRUD ====================

    def get_property_definition(self, property_id: str) -> Optional[PropertyDefinition]:
        """
        Retrieve a property definition by ID.

        Args:
            property_id: UUID of the property definition

        Returns:
            PropertyDefinition entity if found, None otherwise
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == property_id,
                    OntologyEntity.node_type == NodeType.PROPERTY_DEFINITION,
                )
            )
            .first()
        )
        if orm_entity is None:
            return None
        return cast(PropertyDefinition, map_orm_to_domain(orm_entity))

    def list_property_definitions(
        self,
        is_relevant: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PropertyDefinition]:
        """
        Retrieve all property definitions with optional relevance filter.

        Args:
            is_relevant: Optional filter by relevance status
            limit: Maximum number of results to return (default 100)
            offset: Number of results to skip (default 0)

        Returns:
            Sequence of PropertyDefinition entities
        """
        query = self.session.query(OntologyEntity).filter(
            OntologyEntity.node_type == NodeType.PROPERTY_DEFINITION
        )

        if is_relevant is not None:
            query = query.filter(OntologyEntity.is_relevant == is_relevant)

        orm_entities = query.limit(limit).offset(offset).all()
        return [cast(PropertyDefinition, map_orm_to_domain(e)) for e in orm_entities]

    def get_property_definition_by_identifier(
        self, identifier: str
    ) -> Optional[PropertyDefinition]:
        """
        Retrieve a property definition by its identifier.

        Args:
            identifier: The identifier string to search for

        Returns:
            PropertyDefinition entity if found, None otherwise
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.identifier == identifier,
                    OntologyEntity.node_type == NodeType.PROPERTY_DEFINITION,
                )
            )
            .first()
        )
        if orm_entity is None:
            return None
        return cast(PropertyDefinition, map_orm_to_domain(orm_entity))

    def save_property_definition(
        self, prop: PropertyDefinition
    ) -> PropertyDefinition:
        """
        Create or update a property definition.

        Args:
            prop: PropertyDefinition entity to save

        Returns:
            Saved PropertyDefinition entity

        Raises:
            ValueError: If title is empty or identifier is not unique
        """
        if not prop.title or not prop.title.strip():
            raise ValueError("PropertyDefinition title cannot be empty")

        if not prop.identifier or not prop.identifier.strip():
            raise ValueError("PropertyDefinition identifier cannot be empty")

        # Check identifier uniqueness (excluding self in update case)
        existing = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.identifier == prop.identifier,
                    OntologyEntity.id != prop.id,
                    OntologyEntity.node_type == NodeType.PROPERTY_DEFINITION,
                )
            )
            .first()
        )
        if existing is not None:
            raise ValueError(
                f"PropertyDefinition with identifier {prop.identifier} already exists"
            )

        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == prop.id,
                    OntologyEntity.node_type == NodeType.PROPERTY_DEFINITION,
                )
            )
            .first()
        )

        if orm_entity is None:
            # Create new
            orm_entity = map_domain_to_orm(prop)
            orm_entity.created_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.version = 1  # type: ignore[assignment]
            self.session.add(orm_entity)

            # Also create in property_definitions table for optimized queries
            prop_def_orm = PropertyDefinitionORM(
                id=prop.id,
                identifier=prop.identifier,
                title=prop.title,
                description=prop.description,
                ontology_mapping=orm_entity.ontology_mapping,
                is_relevant=prop.is_relevant,
                created_at=datetime.now(timezone.utc),
                last_modified=datetime.now(timezone.utc),
                version=1,
            )
            self.session.add(prop_def_orm)
        else:
            # Update existing in both tables
            mapped_orm = map_domain_to_orm(prop)
            orm_entity.title = prop.title  # type: ignore[assignment]
            orm_entity.description = prop.description  # type: ignore[assignment]
            orm_entity.identifier = prop.identifier  # type: ignore[assignment]
            orm_entity.ontology_mapping = mapped_orm.ontology_mapping  # type: ignore[assignment]
            orm_entity.is_relevant = prop.is_relevant  # type: ignore[assignment]
            orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
            orm_entity.version = orm_entity.version + 1  # type: ignore[assignment]

            # Also update in property_definitions table
            prop_def_orm_maybe = self.session.query(PropertyDefinitionORM).filter(
                PropertyDefinitionORM.id == prop.id
            ).first()
            if prop_def_orm_maybe:
                prop_def_orm_maybe.title = prop.title  # type: ignore[assignment]
                prop_def_orm_maybe.description = prop.description  # type: ignore[assignment]
                prop_def_orm_maybe.identifier = prop.identifier  # type: ignore[assignment]
                prop_def_orm_maybe.ontology_mapping = mapped_orm.ontology_mapping  # type: ignore[assignment]
                prop_def_orm_maybe.is_relevant = prop.is_relevant  # type: ignore[assignment]
                prop_def_orm_maybe.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
                prop_def_orm_maybe.version = prop_def_orm_maybe.version + 1  # type: ignore[assignment]

        self.session.flush()
        return cast(PropertyDefinition, map_orm_to_domain(orm_entity))

    def delete_property_definition(self, property_id: str) -> bool:
        """
        Delete a property definition.

        Note: Relationships using this property cannot be created/updated after deletion
        due to foreign key constraint.

        Args:
            property_id: UUID of the property definition

        Returns:
            True if deleted, False if not found
        """
        orm_entity = (
            self.session.query(OntologyEntity)
            .filter(
                and_(
                    OntologyEntity.id == property_id,
                    OntologyEntity.node_type == NodeType.PROPERTY_DEFINITION,
                )
            )
            .first()
        )

        if orm_entity is None:
            return False

        # Also delete from property_definitions table
        self.session.query(PropertyDefinitionORM).filter(
            PropertyDefinitionORM.id == property_id
        ).delete()

        self.session.delete(orm_entity)
        self.session.flush()
        return True

    # ==================== Relationship CRUD ====================

    def get_relationship(self, relationship_id: str) -> Optional[Relationship]:
        """
        Retrieve a relationship by ID.

        Args:
            relationship_id: UUID of the relationship

        Returns:
            Relationship entity if found, None otherwise
        """
        orm_rel = self.session.query(RelationshipORM).filter(
            RelationshipORM.id == relationship_id
        ).first()

        if orm_rel is None:
            return None

        return map_relationship_orm_to_domain(orm_rel)

    def list_relationships(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        property_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Relationship]:
        """
        List relationships, optionally filtered by source, target, or property definition.

        Args:
            source_id: Optional source entity ID to filter by
            target_id: Optional target entity ID to filter by
            property_id: Optional property definition ID to filter by
            limit: Maximum number of results to return (default 100)
            offset: Number of results to skip (default 0)

        Returns:
            Sequence of Relationship entities
        """
        query = self.session.query(RelationshipORM)

        if source_id is not None:
            query = query.filter(RelationshipORM.source_id == source_id)

        if target_id is not None:
            query = query.filter(RelationshipORM.target_id == target_id)

        if property_id is not None:
            query = query.filter(RelationshipORM.property_definition_id == property_id)

        orm_rels = query.limit(limit).offset(offset).all()
        return [map_relationship_orm_to_domain(r) for r in orm_rels]

    def save_relationship(self, rel: Relationship) -> Relationship:
        """
        Create or update a relationship.

        Validates that source, target, and property definition all exist.

        Args:
            rel: Relationship entity to save

        Returns:
            Saved Relationship entity

        Raises:
            ValueError: If source, target, or property definition doesn't exist,
                       or if source == target
        """
        if rel.source_id == rel.target_id:
            raise ValueError("A relationship cannot have the same source and target")

        # Verify source exists
        source = self.session.query(OntologyEntity).filter(
            OntologyEntity.id == rel.source_id
        ).first()
        if source is None:
            raise ValueError(f"Source entity {rel.source_id} does not exist")

        # Verify target exists
        target = self.session.query(OntologyEntity).filter(
            OntologyEntity.id == rel.target_id
        ).first()
        if target is None:
            raise ValueError(f"Target entity {rel.target_id} does not exist")

        # Verify property definition exists
        prop_def = self.get_property_definition(rel.property_definition_id)
        if prop_def is None:
            raise ValueError(
                f"Property definition {rel.property_definition_id} does not exist"
            )

        orm_rel = self.session.query(RelationshipORM).filter(
            RelationshipORM.id == rel.id
        ).first()

        if orm_rel is None:
            # Create new (always create, never update, due to immutable created_at)
            orm_rel = map_relationship_domain_to_orm(rel)
            self.session.add(orm_rel)
        else:
            # Update: only update the timestamp field, everything else is immutable
            orm_rel.source_id = rel.source_id  # type: ignore[assignment]
            orm_rel.target_id = rel.target_id  # type: ignore[assignment]
            orm_rel.property_definition_id = rel.property_definition_id  # type: ignore[assignment]

        self.session.flush()
        return map_relationship_orm_to_domain(orm_rel)

    def delete_relationship(self, relationship_id: str) -> bool:
        """
        Delete a relationship.

        Args:
            relationship_id: UUID of the relationship

        Returns:
            True if deleted, False if not found
        """
        orm_rel = self.session.query(RelationshipORM).filter(
            RelationshipORM.id == relationship_id
        ).first()

        if orm_rel is None:
            return False

        self.session.delete(orm_rel)
        self.session.flush()
        return True

    # ==================== Utility Methods ====================

    def get_all_entities_and_relationships(
        self,
    ) -> tuple[list[Any], list[Relationship]]:
        """
        Retrieve all entities and relationships for graph analysis.

        Returns:
            Tuple of (entities sequence, relationships sequence)
        """
        all_orm_entities = self.session.query(OntologyEntity).all()
        entities = [map_orm_to_domain(e) for e in all_orm_entities]

        all_orm_rels = self.session.query(RelationshipORM).all()
        relationships = [map_relationship_orm_to_domain(r) for r in all_orm_rels]

        return entities, relationships

    # ==================== Helper Methods ====================

    def _would_create_cycle(self, class_id: str, potential_parent_id: str) -> bool:
        """
        Check if adding parent_id as parent of class_id would create a cycle.

        Walks up the parent chain from potential_parent to see if class_id exists.

        Args:
            class_id: ID of the class to be updated
            potential_parent_id: ID of the proposed parent

        Returns:
            True if adding this parent would create a cycle, False otherwise
        """
        visited: set[str] = set()
        current: str | None = potential_parent_id

        while current is not None:
            if current in visited:
                # Cycle detected in existing data
                return True

            if current == class_id:
                # Would create a cycle
                return True

            visited.add(current)

            # Get parent of current
            parent_class = self.get_class(current)
            if parent_class is None:
                break

            current = parent_class.parent_class_id

        return False

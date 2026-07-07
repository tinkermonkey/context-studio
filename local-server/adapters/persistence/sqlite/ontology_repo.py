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

from datetime import datetime, timezone
from typing import Any, Literal, Optional, cast

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, sessionmaker

from adapters.persistence.sqlite.mappers import (
    deserialize_data_properties,
    deserialize_external_references,
    map_domain_to_orm,
    map_orm_to_domain,
    map_relationship_domain_to_orm,
    map_relationship_orm_to_domain,
)
from adapters.persistence.sqlite.models import (
    IndividualClass,
    OntologyEntity,
)
from adapters.persistence.sqlite.models import (
    PropertyDefinition as PropertyDefinitionORM,
)
from adapters.persistence.sqlite.models import (
    Relationship as RelationshipORM,
)
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.value_objects import NodeType, SearchCriteria, Status
from utils.async_executor import run_sync_in_executor


class SQLiteOntologyRepository:
    """
    SQLAlchemy-based implementation of the OntologyRepository port (structural subtyping).

    Manages persistence of all ontology entities using a unified single-table
    inheritance pattern with node_type discriminator. Enforces invariants
    and maintains referential integrity.

    Attributes:
        session_factory: SQLAlchemy sessionmaker for creating isolated sessions
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        """
        Initialize the repository with a database session factory.

        Args:
            session_factory: SQLAlchemy sessionmaker for creating isolated sessions
        """
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        """
        Create and return a new isolated session.

        Returns:
            SQLAlchemy Session instance
        """
        return self.session_factory()

    # ==================== Taxonomy CRUD ====================

    def get_taxonomy(self, taxonomy_id: str, session: Session | None = None) -> Optional[Taxonomy]:
        """
        Retrieve a taxonomy by ID.

        Args:
            taxonomy_id: UUID of the taxonomy
            session: Optional session to reuse (for internal calls from save_* methods)

        Returns:
            Taxonomy entity if found, None otherwise
        """
        close_session = False
        if session is None:
            session = self._get_session()
            close_session = True

        try:
            orm_entity = (
                session.query(OntologyEntity)
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
        finally:
            if close_session:
                session.close()

    def list_taxonomies(
        self,
        limit: Optional[int] = 100,
        offset: int = 0,
        sort_by: Optional[str] = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: Optional[str] = None,
    ) -> list[Taxonomy]:
        """
        Retrieve taxonomies with optional pagination, sorting, and text search.

        Args:
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (title, created_at, last_modified); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query for LIKE search on title

        Returns:
            Sequence of Taxonomy entities
        """
        with self.session_factory() as session:
            q = session.query(OntologyEntity).filter(OntologyEntity.node_type == NodeType.TAXONOMY)

            if query:
                q = q.filter(OntologyEntity.title.like(f"%{query}%"))

            if sort_by == "title":
                col = OntologyEntity.title
            elif sort_by == "created_at":
                col = OntologyEntity.created_at
            elif sort_by == "last_modified":
                col = OntologyEntity.last_modified
            else:
                col = OntologyEntity.created_at

            if sort_order.lower() == "desc":
                q = q.order_by(col.desc())
            else:
                q = q.order_by(col.asc())

            if limit is not None:
                q = q.limit(limit)
            orm_entities = q.offset(offset).all()
            return [cast(Taxonomy, map_orm_to_domain(e)) for e in orm_entities]

    def count_taxonomies(self, query: Optional[str] = None) -> int:
        """
        Count taxonomies, optionally filtered by text search.

        Args:
            query: Optional text query for LIKE search on title

        Returns:
            Total count of taxonomies
        """
        with self.session_factory() as session:
            q = session.query(OntologyEntity).filter(OntologyEntity.node_type == NodeType.TAXONOMY)

            if query:
                q = q.filter(OntologyEntity.title.like(f"%{query}%"))

            return q.count()

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

        with self.session_factory() as session:
            orm_entity = (
                session.query(OntologyEntity)
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
                    identifier=taxonomy.identifier,
                    title=taxonomy.title,
                    description=taxonomy.description,
                    color=taxonomy.color,
                    created_at=datetime.now(timezone.utc),
                    last_modified=datetime.now(timezone.utc),
                    version=1,
                )
                session.add(orm_entity)
            else:
                # Update existing — identifier is immutable post-create
                orm_entity.title = taxonomy.title  # type: ignore[assignment]
                orm_entity.description = taxonomy.description  # type: ignore[assignment]
                orm_entity.color = taxonomy.color  # type: ignore[assignment]
                orm_entity.status = taxonomy.status.value  # type: ignore[assignment]
                orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
                orm_entity.version = orm_entity.version + 1  # type: ignore[assignment]

            session.commit()
            return cast(Taxonomy, map_orm_to_domain(orm_entity))

    def delete_taxonomy(self, taxonomy_id: str) -> bool:
        """
        Delete a taxonomy and all its children (cascade).

        Args:
            taxonomy_id: UUID of the taxonomy

        Returns:
            True if deleted, False if not found
        """
        with self.session_factory() as session:
            orm_entity = (
                session.query(OntologyEntity)
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

            session.delete(orm_entity)
            session.commit()
            return True

    # ==================== ConceptScheme CRUD ====================

    def get_concept_scheme(
        self, concept_scheme_id: str, session: Session | None = None
    ) -> Optional[ConceptScheme]:
        """
        Retrieve a concept scheme by ID.

        Args:
            concept_scheme_id: UUID of the concept scheme
            session: Optional session to reuse (for internal calls from save_* methods)

        Returns:
            ConceptScheme entity if found, None otherwise
        """
        close_session = False
        if session is None:
            session = self._get_session()
            close_session = True

        try:
            orm_entity = (
                session.query(OntologyEntity)
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
        finally:
            if close_session:
                session.close()

    def list_concept_schemes(
        self,
        taxonomy_id: Optional[str] = None,
        limit: Optional[int] = 100,
        offset: int = 0,
        sort_by: Optional[str] = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: Optional[str] = None,
    ) -> list[ConceptScheme]:
        """
        List concept schemes with optional filtering, pagination, sorting, and text search.

        Args:
            taxonomy_id: Optional taxonomy ID to filter by
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (title, created_at, last_modified); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query for LIKE search on title

        Returns:
            Sequence of ConceptScheme entities
        """
        with self.session_factory() as session:
            q = session.query(OntologyEntity).filter(
                OntologyEntity.node_type == NodeType.CONCEPT_SCHEME
            )

            if taxonomy_id is not None:
                q = q.filter(OntologyEntity.taxonomy_id == taxonomy_id)

            if query:
                q = q.filter(OntologyEntity.title.like(f"%{query}%"))

            if sort_by == "title":
                col = OntologyEntity.title
            elif sort_by == "created_at":
                col = OntologyEntity.created_at
            elif sort_by == "last_modified":
                col = OntologyEntity.last_modified
            else:
                col = OntologyEntity.created_at

            if sort_order.lower() == "desc":
                q = q.order_by(col.desc())
            else:
                q = q.order_by(col.asc())

            if limit is not None:
                q = q.limit(limit)
            orm_entities = q.offset(offset).all()
            return [cast(ConceptScheme, map_orm_to_domain(e)) for e in orm_entities]

    def count_concept_schemes(
        self, taxonomy_id: Optional[str] = None, query: Optional[str] = None
    ) -> int:
        """
        Count concept schemes, optionally filtered by taxonomy and text search.

        Args:
            taxonomy_id: Optional taxonomy ID to filter by
            query: Optional text query for LIKE search on title

        Returns:
            Total count of concept schemes
        """
        with self.session_factory() as session:
            q = session.query(OntologyEntity).filter(
                OntologyEntity.node_type == NodeType.CONCEPT_SCHEME
            )

            if taxonomy_id is not None:
                q = q.filter(OntologyEntity.taxonomy_id == taxonomy_id)

            if query:
                q = q.filter(OntologyEntity.title.like(f"%{query}%"))

            return q.count()

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

        with self.session_factory() as session:
            # Verify parent taxonomy exists (same session)
            parent_taxonomy = self.get_taxonomy(scheme.taxonomy_id, session)
            if parent_taxonomy is None:
                raise ValueError(f"Parent taxonomy {scheme.taxonomy_id} does not exist")

            orm_entity = (
                session.query(OntologyEntity)
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
                    identifier=scheme.identifier,
                    title=scheme.title,
                    description=scheme.description,
                    color=scheme.color,
                    created_at=datetime.now(timezone.utc),
                    last_modified=datetime.now(timezone.utc),
                    version=1,
                )
                session.add(orm_entity)
            else:
                # Update existing — identifier is immutable post-create
                orm_entity.title = scheme.title  # type: ignore[assignment]
                orm_entity.description = scheme.description  # type: ignore[assignment]
                orm_entity.color = scheme.color  # type: ignore[assignment]
                orm_entity.status = scheme.status.value  # type: ignore[assignment]
                orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
                orm_entity.version = orm_entity.version + 1  # type: ignore[assignment]

            session.commit()
            return cast(ConceptScheme, map_orm_to_domain(orm_entity))

    def delete_concept_scheme(self, concept_scheme_id: str) -> bool:
        """
        Delete a concept scheme and all its classes (cascade).

        Args:
            concept_scheme_id: UUID of the concept scheme

        Returns:
            True if deleted, False if not found
        """
        with self.session_factory() as session:
            orm_entity = (
                session.query(OntologyEntity)
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

            session.delete(orm_entity)
            session.commit()
            return True

    # ==================== Class CRUD ====================

    def get_class(self, class_id: str, session: Session | None = None) -> Optional[Class]:
        """
        Retrieve a class by ID.

        Args:
            class_id: UUID of the class
            session: Optional session to reuse (for internal calls from save_* methods)

        Returns:
            Class entity if found, None otherwise
        """
        close_session = False
        if session is None:
            session = self._get_session()
            close_session = True

        try:
            orm_entity = (
                session.query(OntologyEntity)
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
        finally:
            if close_session:
                session.close()

    def list_classes(
        self,
        concept_scheme_id: Optional[str] = None,
        parent_class_id: Optional[str] = None,
        limit: int | None = 100,
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
        with self.session_factory() as session:
            query = session.query(OntologyEntity).filter(OntologyEntity.node_type == NodeType.CLASS)

            if concept_scheme_id is not None:
                query = query.filter(OntologyEntity.concept_scheme_id == concept_scheme_id)

            if parent_class_id is not None:
                query = query.filter(OntologyEntity.parent_class_id == parent_class_id)

            if limit is not None:
                query = query.limit(limit)
            orm_entities = query.offset(offset).all()
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
        with self.session_factory() as session:
            query = session.query(OntologyEntity).filter(OntologyEntity.node_type == NodeType.CLASS)

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

        with self.session_factory() as session:
            # Verify parent concept scheme exists (same session)
            parent_scheme = self.get_concept_scheme(cls.concept_scheme_id, session)
            if parent_scheme is None:
                raise ValueError(f"Parent concept scheme {cls.concept_scheme_id} does not exist")

            # Verify parent taxonomy exists (same session)
            parent_taxonomy = self.get_taxonomy(cls.taxonomy_id, session)
            if parent_taxonomy is None:
                raise ValueError(f"Parent taxonomy {cls.taxonomy_id} does not exist")

            # If parent class is set, verify it exists and check for cycles
            if cls.parent_class_id is not None:
                if cls.parent_class_id == cls.id:
                    raise ValueError("A class cannot be its own parent")

                parent_class = self.get_class(cls.parent_class_id, session)
                if parent_class is None:
                    raise ValueError(f"Parent class {cls.parent_class_id} does not exist")

                # Check for cycles in hierarchy (same session)
                if self._would_create_cycle(cls.id, cls.parent_class_id, session):
                    raise ValueError(
                        f"Setting parent class {cls.parent_class_id} would create a" " cycle"
                    )

            # Verify structural property if set (same session)
            if cls.structural_property_id is not None:
                struct_prop = self.get_property_definition(cls.structural_property_id, session)
                if struct_prop is None:
                    raise ValueError(
                        f"Structural property {cls.structural_property_id} does not" " exist"
                    )

            orm_entity = (
                session.query(OntologyEntity)
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
                session.add(orm_entity)
            else:
                # Update existing — identifier is immutable post-create
                mapped_orm = map_domain_to_orm(cls)
                orm_entity.title = cls.title  # type: ignore[assignment]
                orm_entity.description = cls.description  # type: ignore[assignment]
                orm_entity.color = cls.color  # type: ignore[assignment]
                orm_entity.parent_class_id = cls.parent_class_id  # type: ignore[assignment]
                orm_entity.concept_scheme_id = cls.concept_scheme_id  # type: ignore[assignment]
                structural_property_id = cls.structural_property_id
                orm_entity.structural_property_id = (
                    structural_property_id  # type: ignore[assignment]
                )
                orm_entity.external_references = mapped_orm.external_references
                orm_entity.lexical_senses = mapped_orm.lexical_senses  # type: ignore[assignment]
                orm_entity.data_properties = mapped_orm.data_properties  # type: ignore[assignment]
                orm_entity.embedding = mapped_orm.embedding  # type: ignore[assignment]
                orm_entity.status = cls.status.value  # type: ignore[assignment]
                orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
                orm_entity.version = orm_entity.version + 1  # type: ignore[assignment]

            session.commit()
            return cast(Class, map_orm_to_domain(orm_entity))

    def delete_class(self, class_id: str) -> bool:
        """
        Delete a class and all its children (cascade).

        Args:
            class_id: UUID of the class

        Returns:
            True if deleted, False if not found
        """
        with self.session_factory() as session:
            orm_entity = (
                session.query(OntologyEntity)
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

            session.delete(orm_entity)
            session.commit()
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
        with self.session_factory() as session:
            query = session.query(OntologyEntity).filter(OntologyEntity.node_type == NodeType.CLASS)

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
                    OntologyEntity.node_type.in_([nt.value for nt in criteria.node_types])
                )

            # Filter by taxonomy
            if criteria.taxonomy_id:
                query = query.filter(OntologyEntity.taxonomy_id == criteria.taxonomy_id)

            # Filter by concept scheme
            if criteria.concept_scheme_id:
                query = query.filter(OntologyEntity.concept_scheme_id == criteria.concept_scheme_id)

            # Filter by parent
            if criteria.parent_id:
                query = query.filter(OntologyEntity.parent_class_id == criteria.parent_id)

            # Apply pagination
            query = query.limit(criteria.limit).offset(criteria.offset)

            orm_entities = query.all()
            return [cast(Class, map_orm_to_domain(e)) for e in orm_entities]

    # ==================== Individual CRUD ====================

    def get_individual(
        self, individual_id: str, session: Session | None = None
    ) -> Optional[Individual]:
        """
        Retrieve an individual by ID.

        Args:
            individual_id: UUID of the individual
            session: Optional session to reuse (for internal calls from save_* methods)

        Returns:
            Individual entity if found, None otherwise
        """
        close_session = False
        if session is None:
            session = self._get_session()
            close_session = True

        try:
            orm_entity = (
                session.query(OntologyEntity)
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

            return self._build_individual_from_orm(orm_entity, session)
        finally:
            if close_session:
                session.close()

    def list_individuals(
        self,
        class_id: Optional[str] = None,
        limit: int | None = 100,
        offset: int = 0,
    ) -> list[Individual]:
        """
        List individuals, optionally filtered by class.

        Args:
            class_id: Optional class ID to filter by (rdf:type) - matches any parent class
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip

        Returns:
            Sequence of Individual entities
        """
        with self.session_factory() as session:
            query = session.query(OntologyEntity).filter(
                OntologyEntity.node_type == NodeType.INDIVIDUAL
            )

            if class_id is not None:
                # Filter to individuals that have this class as a parent
                subquery = (
                    session.query(IndividualClass.individual_id)
                    .filter(IndividualClass.class_id == class_id)
                    .distinct()
                )
                query = query.filter(OntologyEntity.id.in_(subquery))

            query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            orm_entities = query.all()

            # Build individuals from ORM entities using helper
            individuals = [
                self._build_individual_from_orm(orm_entity, session) for orm_entity in orm_entities
            ]

            return individuals

    def save_individual(self, individual: Individual) -> Individual:
        """
        Create or update an individual.

        Args:
            individual: Individual entity to save

        Returns:
            Saved Individual entity

        Raises:
            ValueError: If title is empty, no parent classes, or a parent class doesn't exist
        """
        if not individual.title or not individual.title.strip():
            raise ValueError("Individual title cannot be empty")
        if not individual.class_ids:
            raise ValueError("Individual must have at least one parent class")

        with self.session_factory() as session:
            # Verify all parent classes exist
            for class_id in individual.class_ids:
                parent_class = self.get_class(class_id, session)
                if parent_class is None:
                    raise ValueError(f"Parent class {class_id} does not exist")

            orm_entity = (
                session.query(OntologyEntity)
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
                session.add(orm_entity)
                session.flush()  # Ensure ORM entity exists before adding join table records

                # Add class memberships to join table
                for position, class_id in enumerate(individual.class_ids):
                    membership = IndividualClass(
                        individual_id=individual.id,
                        class_id=class_id,
                        position=position,
                    )
                    session.add(membership)
            else:
                # Update existing
                mapped_orm = map_domain_to_orm(individual)
                orm_entity.title = individual.title  # type: ignore[assignment]
                orm_entity.description = individual.description  # type: ignore[assignment]
                orm_entity.data_properties = mapped_orm.data_properties  # type: ignore[assignment]
                orm_entity.external_references = (
                    mapped_orm.external_references
                )  # type: ignore[assignment]
                orm_entity.status = individual.status.value  # type: ignore[assignment]
                orm_entity.source_run_id = individual.source_run_id  # type: ignore[assignment]
                orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
                orm_entity.version = orm_entity.version + 1  # type: ignore[assignment]

                # Update class memberships in join table
                # Delete existing memberships
                session.query(IndividualClass).filter(
                    IndividualClass.individual_id == individual.id
                ).delete()

                # Add updated memberships
                for position, class_id in enumerate(individual.class_ids):
                    membership = IndividualClass(
                        individual_id=individual.id,
                        class_id=class_id,
                        position=position,
                    )
                    session.add(membership)

            session.commit()

            # Reload with populated class_ids
            result = self.get_individual(individual.id, session)
            if result is None:
                raise RuntimeError(f"Failed to reload individual {individual.id} after save")
            return result

    def delete_individual(self, individual_id: str) -> bool:
        """
        Delete an individual.

        Args:
            individual_id: UUID of the individual

        Returns:
            True if deleted, False if not found
        """
        with self.session_factory() as session:
            orm_entity = (
                session.query(OntologyEntity)
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

            session.delete(orm_entity)
            session.commit()
            return True

    # ==================== PropertyDefinition CRUD ====================

    def get_property_definition(
        self, property_id: str, session: Session | None = None
    ) -> Optional[PropertyDefinition]:
        """
        Retrieve a property definition by ID.

        Args:
            property_id: UUID of the property definition
            session: Optional session to reuse (for internal calls from save_* methods)

        Returns:
            PropertyDefinition entity if found, None otherwise
        """
        close_session = False
        if session is None:
            session = self._get_session()
            close_session = True

        try:
            orm_entity = (
                session.query(OntologyEntity)
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
        finally:
            if close_session:
                session.close()

    def list_property_definitions(
        self,
        is_relevant: Optional[bool] = None,
        limit: Optional[int] = 100,
        offset: int = 0,
        sort_by: Optional[str] = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: Optional[str] = None,
    ) -> list[PropertyDefinition]:
        """
        Retrieve property definitions with optional filtering, pagination, sorting, and text search.

        Args:
            is_relevant: Optional filter by relevance status
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (title, created_at, last_modified); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query for LIKE search on title

        Returns:
            Sequence of PropertyDefinition entities
        """
        with self.session_factory() as session:
            q = session.query(OntologyEntity).filter(
                OntologyEntity.node_type == NodeType.PROPERTY_DEFINITION
            )

            if is_relevant is not None:
                q = q.filter(OntologyEntity.is_relevant == is_relevant)

            if query:
                q = q.filter(OntologyEntity.title.like(f"%{query}%"))

            if sort_by == "title":
                col = OntologyEntity.title
            elif sort_by == "created_at":
                col = OntologyEntity.created_at
            elif sort_by == "last_modified":
                col = OntologyEntity.last_modified
            else:
                col = OntologyEntity.created_at

            if sort_order.lower() == "desc":
                q = q.order_by(col.desc())
            else:
                q = q.order_by(col.asc())

            if limit is not None:
                q = q.limit(limit)
            orm_entities = q.offset(offset).all()
            return [cast(PropertyDefinition, map_orm_to_domain(e)) for e in orm_entities]

    def count_property_definitions(
        self, is_relevant: Optional[bool] = None, query: Optional[str] = None
    ) -> int:
        """
        Count property definitions, optionally filtered by relevance and text search.

        Args:
            is_relevant: Optional filter for relevant property definitions
            query: Optional text query for LIKE search on title

        Returns:
            Total count of property definitions
        """
        with self.session_factory() as session:
            q = session.query(OntologyEntity).filter(
                OntologyEntity.node_type == NodeType.PROPERTY_DEFINITION
            )

            if is_relevant is not None:
                q = q.filter(OntologyEntity.is_relevant == is_relevant)

            if query:
                q = q.filter(OntologyEntity.title.like(f"%{query}%"))

            return q.count()

    def get_by_identifier(self, identifier: str) -> Optional[Taxonomy | ConceptScheme | Class]:
        """
        Retrieve a Taxonomy, ConceptScheme, or Class by its globally-unique slug.

        Property definitions are intentionally excluded; use
        ``get_property_definition_by_identifier`` for those.

        Args:
            identifier: The slug-style identifier (e.g. 'tax_life')

        Returns:
            The matching domain entity, or None if no taxonomy/scheme/class owns it.
        """
        with self.session_factory() as session:
            orm_entity = (
                session.query(OntologyEntity)
                .filter(
                    and_(
                        OntologyEntity.identifier == identifier,
                        OntologyEntity.node_type.in_(
                            (NodeType.TAXONOMY, NodeType.CONCEPT_SCHEME, NodeType.CLASS)
                        ),
                    )
                )
                .first()
            )
            if orm_entity is None:
                return None
            return cast(
                Optional[Taxonomy | ConceptScheme | Class],
                map_orm_to_domain(orm_entity),
            )

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
        with self.session_factory() as session:
            orm_entity = (
                session.query(OntologyEntity)
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

    def save_property_definition(self, prop: PropertyDefinition) -> PropertyDefinition:
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

        with self.session_factory() as session:
            # Check identifier uniqueness (same session)
            existing = (
                session.query(OntologyEntity)
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
                    f"PropertyDefinition with identifier {prop.identifier} already" " exists"
                )

            orm_entity = (
                session.query(OntologyEntity)
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
                session.add(orm_entity)

                # Also create in property_definitions table for optimized queries
                prop_def_orm = PropertyDefinitionORM(
                    id=prop.id,
                    identifier=prop.identifier,
                    title=prop.title,
                    description=prop.description,
                    ontology_mapping=orm_entity.ontology_mapping,
                    domain_class_id=prop.domain_class_id,
                    range_class_id=prop.range_class_id,
                    is_relevant=prop.is_relevant,
                    created_at=datetime.now(timezone.utc),
                    last_modified=datetime.now(timezone.utc),
                    version=1,
                )
                session.add(prop_def_orm)
            else:
                # Update existing in both tables
                mapped_orm = map_domain_to_orm(prop)
                orm_entity.title = prop.title  # type: ignore[assignment]
                orm_entity.description = prop.description  # type: ignore[assignment]
                orm_entity.identifier = prop.identifier  # type: ignore[assignment]
                orm_entity.ontology_mapping = (
                    mapped_orm.ontology_mapping
                )  # type: ignore[assignment]
                orm_entity.domain_class_id = prop.domain_class_id  # type: ignore[assignment]
                orm_entity.range_class_id = prop.range_class_id  # type: ignore[assignment]
                orm_entity.external_references = (
                    mapped_orm.external_references
                )  # type: ignore[assignment]
                orm_entity.is_relevant = prop.is_relevant  # type: ignore[assignment]
                orm_entity.lexical_senses = mapped_orm.lexical_senses  # type: ignore[assignment]
                orm_entity.status = prop.status.value  # type: ignore[assignment]
                orm_entity.last_modified = datetime.now(timezone.utc)  # type: ignore[assignment]
                orm_entity.version = orm_entity.version + 1  # type: ignore[assignment]

                # Also update in property_definitions table
                prop_def_orm_maybe = (
                    session.query(PropertyDefinitionORM)
                    .filter(PropertyDefinitionORM.id == prop.id)
                    .first()
                )
                if prop_def_orm_maybe:
                    prop_def_orm_maybe.title = prop.title  # type: ignore[assignment]
                    prop_def_orm_maybe.description = prop.description  # type: ignore[assignment]
                    prop_def_orm_maybe.identifier = prop.identifier  # type: ignore[assignment]
                    prop_def_orm_maybe.ontology_mapping = (  # type: ignore[assignment]
                        mapped_orm.ontology_mapping
                    )
                    prop_def_orm_maybe.domain_class_id = (
                        prop.domain_class_id  # type: ignore[assignment]
                    )
                    prop_def_orm_maybe.range_class_id = (
                        prop.range_class_id  # type: ignore[assignment]
                    )
                    prop_def_orm_maybe.is_relevant = prop.is_relevant  # type: ignore[assignment]
                    prop_def_orm_maybe.last_modified = datetime.now(
                        timezone.utc
                    )  # type: ignore[assignment]
                    prop_def_orm_maybe.version = (
                        prop_def_orm_maybe.version + 1  # type: ignore[assignment]
                    )

            session.commit()
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
        with self.session_factory() as session:
            orm_entity = (
                session.query(OntologyEntity)
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
            session.query(PropertyDefinitionORM).filter(
                PropertyDefinitionORM.id == property_id
            ).delete()

            session.delete(orm_entity)
            session.commit()
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
        with self.session_factory() as session:
            orm_rel = (
                session.query(RelationshipORM).filter(RelationshipORM.id == relationship_id).first()
            )

            if orm_rel is None:
                return None

            return map_relationship_orm_to_domain(orm_rel)

    def list_relationships(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        property_id: Optional[str] = None,
        limit: Optional[int] = 100,
        offset: int = 0,
        sort_by: Optional[str] = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: Optional[str] = None,
    ) -> list[Relationship]:
        """
        List relationships with optional filtering, pagination, sorting, and text search.

        Args:
            source_id: Optional source entity ID to filter by
            target_id: Optional target entity ID to filter by
            property_id: Optional property definition ID to filter by
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (created_at); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query (not used for relationships)

        Returns:
            Sequence of Relationship entities
        """
        with self.session_factory() as session:
            q = session.query(RelationshipORM)

            if source_id is not None:
                q = q.filter(RelationshipORM.source_id == source_id)

            if target_id is not None:
                q = q.filter(RelationshipORM.target_id == target_id)

            if property_id is not None:
                q = q.filter(RelationshipORM.property_definition_id == property_id)

            if sort_by == "created_at":
                col = RelationshipORM.created_at
            else:
                col = RelationshipORM.created_at

            if sort_order.lower() == "desc":
                q = q.order_by(col.desc())
            else:
                q = q.order_by(col.asc())

            if limit is not None:
                q = q.limit(limit)
            orm_rels = q.offset(offset).all()
            return [map_relationship_orm_to_domain(r) for r in orm_rels]

    def count_relationships(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        property_id: Optional[str] = None,
    ) -> int:
        """
        Count relationships, optionally filtered by source, target, or property.

        Args:
            source_id: Optional source entity ID to filter by
            target_id: Optional target entity ID to filter by
            property_id: Optional property definition ID to filter by (relationship type)

        Returns:
            Total count of relationships
        """
        with self.session_factory() as session:
            q = session.query(RelationshipORM)

            if source_id is not None:
                q = q.filter(RelationshipORM.source_id == source_id)

            if target_id is not None:
                q = q.filter(RelationshipORM.target_id == target_id)

            if property_id is not None:
                q = q.filter(RelationshipORM.property_definition_id == property_id)

            return q.count()

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

        with self.session_factory() as session:
            # Verify source exists (same session)
            source = (
                session.query(OntologyEntity).filter(OntologyEntity.id == rel.source_id).first()
            )
            if source is None:
                raise ValueError(f"Source entity {rel.source_id} does not exist")

            # Verify target exists (same session)
            target = (
                session.query(OntologyEntity).filter(OntologyEntity.id == rel.target_id).first()
            )
            if target is None:
                raise ValueError(f"Target entity {rel.target_id} does not exist")

            # Verify property definition exists (same session)
            prop_def = self.get_property_definition(rel.property_definition_id, session)
            if prop_def is None:
                raise ValueError(f"Property definition {rel.property_definition_id} does not exist")

            orm_rel = session.query(RelationshipORM).filter(RelationshipORM.id == rel.id).first()

            if orm_rel is None:
                # Create new (always create, never update, due to immutable created_at)
                orm_rel = map_relationship_domain_to_orm(rel)
                session.add(orm_rel)
            else:
                # Update: only update the timestamp field, everything else is immutable
                orm_rel.source_id = rel.source_id  # type: ignore[assignment]
                orm_rel.target_id = rel.target_id  # type: ignore[assignment]
                orm_rel.property_definition_id = (
                    rel.property_definition_id  # type: ignore[assignment]
                )

            session.commit()
            return map_relationship_orm_to_domain(orm_rel)

    def delete_relationship(self, relationship_id: str) -> bool:
        """
        Delete a relationship.

        Args:
            relationship_id: UUID of the relationship

        Returns:
            True if deleted, False if not found
        """
        with self.session_factory() as session:
            orm_rel = (
                session.query(RelationshipORM).filter(RelationshipORM.id == relationship_id).first()
            )

            if orm_rel is None:
                return False

            session.delete(orm_rel)
            session.commit()
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
        with self.session_factory() as session:
            all_orm_entities = session.query(OntologyEntity).all()
            entities: list[Any] = []
            for e in all_orm_entities:
                # Use helper for Individuals to ensure class_ids are loaded
                if e.node_type == NodeType.INDIVIDUAL:
                    entities.append(self._build_individual_from_orm(e, session))
                else:
                    entities.append(map_orm_to_domain(e))

            all_orm_rels = session.query(RelationshipORM).all()
            relationships = [map_relationship_orm_to_domain(r) for r in all_orm_rels]

            return entities, relationships

    # ==================== Helper Methods ====================

    def _build_individual_from_orm(
        self, orm_entity: OntologyEntity, session: Session
    ) -> Individual:
        """
        Build an Individual domain entity from an ORM entity and join table data.

        Loads the ordered list of parent classes from the IndividualClass join table
        and constructs the Individual entity.

        Args:
            orm_entity: The ORM OntologyEntity (must be of type INDIVIDUAL)
            session: SQLAlchemy session to use for loading join table data

        Returns:
            Individual domain entity with populated class_ids
        """
        # Load class_ids from join table in order
        class_memberships = (
            session.query(IndividualClass)
            .filter(IndividualClass.individual_id == orm_entity.id)
            .order_by(IndividualClass.position)
            .all()
        )
        class_ids: list[str] = [cast(str, membership.class_id) for membership in class_memberships]

        # Create Individual directly with loaded class_ids
        return Individual(
            id=cast(str, orm_entity.id),
            class_ids=class_ids,
            title=cast(str, orm_entity.title),
            description=cast(str | None, orm_entity.description),
            created_at=cast(datetime | None, orm_entity.created_at),
            last_modified=cast(datetime | None, orm_entity.last_modified),
            version=cast(int, orm_entity.version),
            status=Status(cast(str, orm_entity.status)),
            source_run_id=cast(str | None, orm_entity.source_run_id),
            data_properties=deserialize_data_properties(
                cast(list[dict[str, Any]], orm_entity.data_properties) or []
            ),
            external_references=deserialize_external_references(
                cast(list[dict[str, Any]], orm_entity.external_references) or []
            ),
        )

    def _would_create_cycle(
        self, class_id: str, potential_parent_id: str, session: Session
    ) -> bool:
        """
        Check if adding parent_id as parent of class_id would create a cycle.

        Walks up the parent chain from potential_parent to see if class_id exists.

        Args:
            class_id: ID of the class to be updated
            potential_parent_id: ID of the proposed parent
            session: SQLAlchemy session to use for lookups

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

            # Get parent of current (using passed session, not creating new one)
            parent_class = self.get_class(current, session)
            if parent_class is None:
                break

            current = parent_class.parent_class_id

        return False

    # ==================== Async Methods ====================

    async def get_taxonomy_async(self, taxonomy_id: str) -> Optional[Taxonomy]:
        """
        Retrieve a taxonomy by ID (async version).

        Args:
            taxonomy_id: UUID of the taxonomy

        Returns:
            Taxonomy entity if found, None otherwise
        """
        return await run_sync_in_executor(self.get_taxonomy, taxonomy_id)

    async def list_taxonomies_async(self) -> list[Taxonomy]:
        """
        Retrieve all taxonomies (async version).

        Returns:
            Sequence of Taxonomy entities
        """
        return await run_sync_in_executor(self.list_taxonomies)

    async def save_taxonomy_async(self, taxonomy: Taxonomy) -> Taxonomy:
        """
        Create or update a taxonomy (async version).

        Args:
            taxonomy: Taxonomy entity to save

        Returns:
            Saved Taxonomy entity (with timestamps set)
        """
        return await run_sync_in_executor(self.save_taxonomy, taxonomy)

    async def delete_taxonomy_async(self, taxonomy_id: str) -> bool:
        """
        Delete a taxonomy and all its children (async version).

        Args:
            taxonomy_id: UUID of the taxonomy

        Returns:
            True if deleted, False if not found
        """
        return await run_sync_in_executor(self.delete_taxonomy, taxonomy_id)

    async def get_concept_scheme_async(self, concept_scheme_id: str) -> Optional[ConceptScheme]:
        """
        Retrieve a concept scheme by ID (async version).

        Args:
            concept_scheme_id: UUID of the concept scheme

        Returns:
            ConceptScheme entity if found, None otherwise
        """
        return await run_sync_in_executor(self.get_concept_scheme, concept_scheme_id)

    async def list_concept_schemes_async(
        self, taxonomy_id: Optional[str] = None
    ) -> list[ConceptScheme]:
        """
        List concept schemes (async version).

        Args:
            taxonomy_id: Optional taxonomy ID to filter by

        Returns:
            Sequence of ConceptScheme entities
        """
        return await run_sync_in_executor(self.list_concept_schemes, taxonomy_id)

    async def save_concept_scheme_async(self, scheme: ConceptScheme) -> ConceptScheme:
        """
        Create or update a concept scheme (async version).

        Args:
            scheme: ConceptScheme entity to save

        Returns:
            Saved ConceptScheme entity
        """
        return await run_sync_in_executor(self.save_concept_scheme, scheme)

    async def delete_concept_scheme_async(self, concept_scheme_id: str) -> bool:
        """
        Delete a concept scheme and all its classes (async version).

        Args:
            concept_scheme_id: UUID of the concept scheme

        Returns:
            True if deleted, False if not found
        """
        return await run_sync_in_executor(self.delete_concept_scheme, concept_scheme_id)

    async def get_class_async(self, class_id: str) -> Optional[Class]:
        """
        Retrieve a class by ID (async version).

        Args:
            class_id: UUID of the class

        Returns:
            Class entity if found, None otherwise
        """
        return await run_sync_in_executor(self.get_class, class_id)

    async def list_classes_async(
        self,
        concept_scheme_id: Optional[str] = None,
        parent_class_id: Optional[str] = None,
        limit: int | None = 100,
        offset: int = 0,
    ) -> list[Class]:
        """
        List classes (async version).

        Args:
            concept_scheme_id: Optional concept scheme ID to filter by
            parent_class_id: Optional parent class ID to filter by
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Sequence of Class entities
        """
        return await run_sync_in_executor(
            self.list_classes, concept_scheme_id, parent_class_id, limit, offset
        )

    async def count_classes_async(
        self,
        concept_scheme_id: Optional[str] = None,
        parent_class_id: Optional[str] = None,
    ) -> int:
        """
        Count classes matching optional filters (async version).

        Args:
            concept_scheme_id: Optional concept scheme ID to filter by
            parent_class_id: Optional parent class ID to filter by

        Returns:
            Number of matching Class entities
        """
        return await run_sync_in_executor(self.count_classes, concept_scheme_id, parent_class_id)

    async def save_class_async(self, cls: Class) -> Class:
        """
        Create or update a class (async version).

        Args:
            cls: Class entity to save

        Returns:
            Saved Class entity
        """
        return await run_sync_in_executor(self.save_class, cls)

    async def delete_class_async(self, class_id: str) -> bool:
        """
        Delete a class and all its children (async version).

        Args:
            class_id: UUID of the class

        Returns:
            True if deleted, False if not found
        """
        return await run_sync_in_executor(self.delete_class, class_id)

    async def search_classes_async(self, criteria: SearchCriteria) -> list[Class]:
        """
        Search classes by text and optional filters (async version).

        Args:
            criteria: SearchCriteria with query, filters, and pagination

        Returns:
            Sequence of matching Class entities
        """
        return await run_sync_in_executor(self.search_classes, criteria)

    async def get_individual_async(self, individual_id: str) -> Optional[Individual]:
        """
        Retrieve an individual by ID (async version).

        Args:
            individual_id: UUID of the individual

        Returns:
            Individual entity if found, None otherwise
        """
        return await run_sync_in_executor(self.get_individual, individual_id)

    async def list_individuals_async(
        self,
        class_id: Optional[str] = None,
        limit: int | None = 100,
        offset: int = 0,
    ) -> list[Individual]:
        """
        List individuals (async version).

        Args:
            class_id: Optional class ID to filter by
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip

        Returns:
            Sequence of Individual entities
        """
        return await run_sync_in_executor(self.list_individuals, class_id, limit, offset)

    async def save_individual_async(self, individual: Individual) -> Individual:
        """
        Create or update an individual (async version).

        Args:
            individual: Individual entity to save

        Returns:
            Saved Individual entity
        """
        return await run_sync_in_executor(self.save_individual, individual)

    async def delete_individual_async(self, individual_id: str) -> bool:
        """
        Delete an individual (async version).

        Args:
            individual_id: UUID of the individual

        Returns:
            True if deleted, False if not found
        """
        return await run_sync_in_executor(self.delete_individual, individual_id)

    async def get_property_definition_async(self, property_id: str) -> Optional[PropertyDefinition]:
        """
        Retrieve a property definition by ID (async version).

        Args:
            property_id: UUID of the property definition

        Returns:
            PropertyDefinition entity if found, None otherwise
        """
        return await run_sync_in_executor(self.get_property_definition, property_id)

    async def list_property_definitions_async(
        self,
        is_relevant: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PropertyDefinition]:
        """
        Retrieve all property definitions (async version).

        Args:
            is_relevant: Optional filter by relevance status
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Sequence of PropertyDefinition entities
        """
        return await run_sync_in_executor(
            self.list_property_definitions, is_relevant, limit, offset
        )

    async def get_property_definition_by_identifier_async(
        self, identifier: str
    ) -> Optional[PropertyDefinition]:
        """
        Retrieve a property definition by its identifier (async version).

        Args:
            identifier: The identifier string to search for

        Returns:
            PropertyDefinition entity if found, None otherwise
        """
        return await run_sync_in_executor(self.get_property_definition_by_identifier, identifier)

    async def save_property_definition_async(self, prop: PropertyDefinition) -> PropertyDefinition:
        """
        Create or update a property definition (async version).

        Args:
            prop: PropertyDefinition entity to save

        Returns:
            Saved PropertyDefinition entity
        """
        return await run_sync_in_executor(self.save_property_definition, prop)

    async def delete_property_definition_async(self, property_id: str) -> bool:
        """
        Delete a property definition (async version).

        Args:
            property_id: UUID of the property definition

        Returns:
            True if deleted, False if not found
        """
        return await run_sync_in_executor(self.delete_property_definition, property_id)

    async def get_relationship_async(self, relationship_id: str) -> Optional[Relationship]:
        """
        Retrieve a relationship by ID (async version).

        Args:
            relationship_id: UUID of the relationship

        Returns:
            Relationship entity if found, None otherwise
        """
        return await run_sync_in_executor(self.get_relationship, relationship_id)

    async def list_relationships_async(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        property_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Relationship]:
        """
        List relationships (async version).

        Args:
            source_id: Optional source entity ID to filter by
            target_id: Optional target entity ID to filter by
            property_id: Optional property definition ID to filter by
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Sequence of Relationship entities
        """
        return await run_sync_in_executor(
            self.list_relationships, source_id, target_id, property_id, limit, offset
        )

    async def save_relationship_async(self, rel: Relationship) -> Relationship:
        """
        Create or update a relationship (async version).

        Args:
            rel: Relationship entity to save

        Returns:
            Saved Relationship entity
        """
        return await run_sync_in_executor(self.save_relationship, rel)

    async def delete_relationship_async(self, relationship_id: str) -> bool:
        """
        Delete a relationship (async version).

        Args:
            relationship_id: UUID of the relationship

        Returns:
            True if deleted, False if not found
        """
        return await run_sync_in_executor(self.delete_relationship, relationship_id)

    async def get_all_entities_and_relationships_async(
        self,
    ) -> tuple[list[Any], list[Relationship]]:
        """
        Retrieve all entities and relationships for graph analysis (async version).

        Returns:
            Tuple of (entities sequence, relationships sequence)
        """
        return await run_sync_in_executor(self.get_all_entities_and_relationships)

"""
Business logic service for the Ontology Management bounded context.

OntologyService orchestrates all operations on ontology entities, enforcing
invariants and emitting domain events. It depends on three ports: repository
for persistence, embedding service for semantic embeddings, and event publisher
for event distribution.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from domain.ports import EventPublisher
from .entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Relationship,
    PropertyDefinition,
    Individual,
)
from .value_objects import DataPropertyValue, Status
from .events import (
    TaxonomyCreated,
    TaxonomyUpdated,
    TaxonomyDeleted,
    SchemeCreated,
    SchemeUpdated,
    SchemeDeleted,
    ClassCreated,
    ClassUpdated,
    ClassDeleted,
    ClassMoved,
    RelationshipCreated,
    RelationshipDeleted,
    PropertyDefinitionCreated,
    PropertyDefinitionUpdated,
    PropertyDefinitionDeleted,
    ConceptSchemeUpdated,
    GraphInvalidated,
    IndividualCreated,
    IndividualUpdated,
    IndividualDeleted,
)
from .exceptions import (
    EntityNotFoundError,
    CircularReferenceError,
    DuplicateEntityError,
    OntologyError,
)
from .ports import OntologyRepository, EmbeddingService

_logger = logging.getLogger(__name__)


class OntologyService:
    """
    Service implementing all business rules for ontology management.

    This service accepts repository, embedding, and event publisher ports
    via constructor injection, enforcing the dependency rule (no infrastructure
    imports in this domain layer).
    """

    def __init__(
        self,
        repository: OntologyRepository,
        embedding_service: EmbeddingService,
        event_publisher: EventPublisher,
    ) -> None:
        """
        Initialize the service with port dependencies.

        Args:
            repository: Port for persisting and retrieving entities
            embedding_service: Port for generating semantic embeddings
            event_publisher: Port for publishing domain events
        """
        self._repository = repository
        self._embedding_service = embedding_service
        self._event_publisher = event_publisher

    # Taxonomy operations

    def create_taxonomy(self, title: str, description: str | None = None) -> Taxonomy:
        """
        Create a new taxonomy.

        Validates that the title is unique across all taxonomies.

        Args:
            title: Display name for the taxonomy
            description: Optional longer description

        Returns:
            The created Taxonomy

        Raises:
            DuplicateEntityError: If a taxonomy with this title already exists
            ValueError: If title is empty or whitespace
        """
        if not title or not title.strip():
            raise ValueError("Title cannot be empty")

        # Check for duplicate title
        existing = self._repository.list_taxonomies(limit=None)
        if any(t.title == title for t in existing):
            raise DuplicateEntityError(f"Taxonomy with title '{title}' already exists")

        taxonomy_id = str(uuid4())
        now = datetime.now(timezone.utc)
        taxonomy = Taxonomy(
            id=taxonomy_id,
            title=title,
            description=description,
            created_at=now,
            last_modified=now,
        )
        taxonomy = self._repository.save_taxonomy(taxonomy)

        failures = self._event_publisher.publish(
            TaxonomyCreated(
                taxonomy_id=taxonomy_id,
                title=title if title else "",
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for TaxonomyCreated (taxonomy_id=%s): %s. "
                "Taxonomy is created but audit trail may have gaps.",
                taxonomy_id,
                handler_names,
            )

        return taxonomy

    def get_taxonomy(self, taxonomy_id: str) -> Taxonomy:
        """
        Retrieve a taxonomy by ID.

        Args:
            taxonomy_id: The ID of the taxonomy

        Returns:
            The Taxonomy

        Raises:
            EntityNotFoundError: If the taxonomy does not exist
        """
        taxonomy = self._repository.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise EntityNotFoundError("Taxonomy", taxonomy_id)
        return taxonomy

    def list_taxonomies(
        self,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: str | None = None,
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
            List of Taxonomy entities
        """
        return self._repository.list_taxonomies(
            limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order, query=query
        )

    def count_taxonomies(self, query: str | None = None) -> int:
        """
        Count taxonomies, optionally filtered by text search.

        Args:
            query: Optional text query for LIKE search on title

        Returns:
            Total count of taxonomies
        """
        return self._repository.count_taxonomies(query=query)

    def update_taxonomy(
        self,
        taxonomy_id: str,
        title: str | None = None,
        description: str | None = None,
    ) -> Taxonomy:
        """
        Update a taxonomy's title and/or description.

        Args:
            taxonomy_id: The taxonomy ID
            title: New title (optional)
            description: New description (optional)

        Returns:
            The updated Taxonomy

        Raises:
            EntityNotFoundError: If the taxonomy does not exist
            DuplicateEntityError: If the title already exists
            ValueError: If the title is empty
        """
        taxonomy = self._repository.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise EntityNotFoundError("Taxonomy", taxonomy_id)

        # Capture old values before modification
        old_title = taxonomy.title
        old_description = taxonomy.description

        # Check if new title is unique
        if title is not None and title != taxonomy.title:
            if not title or not title.strip():
                raise ValueError("Title cannot be empty")
            existing = self._repository.list_taxonomies(limit=None)
            if any(t.id != taxonomy_id and t.title == title for t in existing):
                raise DuplicateEntityError(
                    f"Taxonomy with title '{title}' already exists"
                )
            taxonomy.title = title

        if description is not None:
            taxonomy.description = description

        # Guard against no-op updates
        title_changed = title is not None and title != old_title
        desc_changed = description is not None and description != old_description

        if not (title_changed or desc_changed):
            return taxonomy

        taxonomy.last_modified = datetime.now(timezone.utc)
        taxonomy = self._repository.save_taxonomy(taxonomy)

        # Emit event only if there were actual changes
        changed = tuple(
            f
            for f, was_changed in [
                ("title", title_changed),
                ("description", desc_changed),
            ]
            if was_changed
        )

        old_values: dict[str, str | None] = {}
        new_values: dict[str, str | None] = {}
        if title_changed:
            old_values["title"] = old_title
            new_values["title"] = title
        if desc_changed:
            old_values["description"] = old_description
            new_values["description"] = description

        failures = self._event_publisher.publish(
            TaxonomyUpdated(
                taxonomy_id=taxonomy_id,
                changed_fields=changed,
                old_values=old_values,
                new_values=new_values,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for TaxonomyUpdated (taxonomy_id=%s): %s. "
                "Taxonomy is updated but audit trail may have gaps.",
                taxonomy_id,
                handler_names,
            )

        return taxonomy

    def rename_taxonomy(self, taxonomy_id: str, new_title: str) -> Taxonomy:
        """
        Rename a taxonomy.

        Validates that the new title is unique across all taxonomies.

        Args:
            taxonomy_id: The ID of the taxonomy to rename
            new_title: The new title for the taxonomy

        Returns:
            The updated Taxonomy

        Raises:
            EntityNotFoundError: If the taxonomy does not exist
            DuplicateEntityError: If a taxonomy with the new title already exists
            ValueError: If new_title is empty or whitespace
        """
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")

        taxonomy = self._repository.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise EntityNotFoundError("Taxonomy", taxonomy_id)

        # Check for duplicate title (excluding the current taxonomy)
        existing = self._repository.list_taxonomies(limit=None)
        if any(t.title == new_title and t.id != taxonomy_id for t in existing):
            raise DuplicateEntityError(
                f"Taxonomy with title '{new_title}' already exists"
            )

        # Guard against no-op updates
        if new_title == taxonomy.title:
            return taxonomy

        # Capture old value before modification
        old_title = taxonomy.title

        taxonomy.rename(new_title)
        taxonomy = self._repository.save_taxonomy(taxonomy)

        failures = self._event_publisher.publish(
            TaxonomyUpdated(
                taxonomy_id=taxonomy_id,
                changed_fields=("title",),
                old_values={"title": old_title},
                new_values={"title": new_title},
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for TaxonomyUpdated (taxonomy_id=%s): %s. "
                "Taxonomy is updated but audit trail may have gaps.",
                taxonomy_id,
                handler_names,
            )

        return taxonomy

    def delete_taxonomy(self, taxonomy_id: str) -> None:
        """
        Delete a taxonomy.

        Validates that the taxonomy has no concept schemes before deletion.

        Args:
            taxonomy_id: The ID of the taxonomy to delete

        Raises:
            EntityNotFoundError: If the taxonomy does not exist
            OntologyError: If the taxonomy has concept schemes
        """
        taxonomy = self._repository.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise EntityNotFoundError("Taxonomy", taxonomy_id)

        # Check for concept schemes
        schemes = self._repository.list_concept_schemes(taxonomy_id=taxonomy_id, limit=None)
        if schemes:
            raise OntologyError(
                f"Cannot delete taxonomy {taxonomy_id}: it has {len(schemes)} concept scheme(s)"
            )

        self._repository.delete_taxonomy(taxonomy_id)

        failures = self._event_publisher.publish(
            TaxonomyDeleted(
                taxonomy_id=taxonomy_id,
                title=taxonomy.title,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for TaxonomyDeleted (taxonomy_id=%s): %s. "
                "Taxonomy is deleted but audit trail may have gaps.",
                taxonomy_id,
                handler_names,
            )

    def publish_taxonomy(self, taxonomy_id: str, commit_message: str | None = None) -> Taxonomy:
        """
        Publish a taxonomy, transitioning status from draft to published.

        Args:
            taxonomy_id: The ID of the taxonomy to publish
            commit_message: Optional commit message for the publication

        Returns:
            The updated Taxonomy with status=published

        Raises:
            EntityNotFoundError: If the taxonomy does not exist
        """
        taxonomy = self._repository.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise EntityNotFoundError("Taxonomy", taxonomy_id)

        if taxonomy.status == Status.PUBLISHED:
            return taxonomy

        old_status = taxonomy.status
        taxonomy.status = Status.PUBLISHED
        taxonomy.last_modified = datetime.now(timezone.utc)
        taxonomy = self._repository.save_taxonomy(taxonomy)

        failures = self._event_publisher.publish(
            TaxonomyUpdated(
                taxonomy_id=taxonomy_id,
                changed_fields=("status",),
                old_values={"status": old_status},
                new_values={"status": Status.PUBLISHED.value},
                commit_message=commit_message,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for TaxonomyUpdated publish (taxonomy_id=%s): %s. "
                "Taxonomy is published but audit trail may have gaps.",
                taxonomy_id,
                handler_names,
            )

        return taxonomy

    def get_publish_diff_stats(self, taxonomy_id: str) -> dict[str, int]:
        """
        Calculate diff statistics for publishing a taxonomy.

        Returns counts of classes that will be affected by the publish action.

        Args:
            taxonomy_id: The ID of the taxonomy to get publish diff stats for

        Returns:
            Dictionary with keys: 'added', 'modified', 'removed' (counts)

        Raises:
            EntityNotFoundError: If the taxonomy does not exist
        """
        taxonomy = self._repository.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise EntityNotFoundError("Taxonomy", taxonomy_id)

        # For a draft taxonomy, count all classes as "added" (they will be published)
        # In a full version history system, we would compare with the last published version
        schemes = self._repository.list_concept_schemes(taxonomy_id=taxonomy_id)
        total_classes = 0
        for scheme in schemes:
            total_classes += self.count_classes(concept_scheme_id=scheme.id)

        return {
            "added": total_classes if taxonomy.status == Status.DRAFT else 0,
            "modified": 0,
            "removed": 0,
        }

    # ConceptScheme operations

    def create_scheme(
        self, taxonomy_id: str, title: str, description: str | None = None
    ) -> ConceptScheme:
        """
        Create a new concept scheme within a taxonomy.

        Validates that:
        - The parent taxonomy exists
        - The title is unique within the taxonomy

        Args:
            taxonomy_id: ID of the parent taxonomy
            title: Display name for the scheme
            description: Optional longer description

        Returns:
            The created ConceptScheme

        Raises:
            EntityNotFoundError: If the parent taxonomy does not exist
            DuplicateEntityError: If a scheme with this title already exists in this taxonomy
            ValueError: If title is empty
        """
        if not title or not title.strip():
            raise ValueError("Title cannot be empty")

        # Validate taxonomy exists
        taxonomy = self._repository.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise EntityNotFoundError("Taxonomy", taxonomy_id)

        # Check for duplicate title within this taxonomy
        existing_schemes = self._repository.list_concept_schemes(
            taxonomy_id=taxonomy_id, limit=None
        )
        if any(s.title == title for s in existing_schemes):
            raise DuplicateEntityError(
                f"ConceptScheme with title '{title}' already exists in this taxonomy"
            )

        scheme_id = str(uuid4())
        now = datetime.now(timezone.utc)
        scheme = ConceptScheme(
            id=scheme_id,
            taxonomy_id=taxonomy_id,
            title=title,
            description=description,
            created_at=now,
            last_modified=now,
        )
        scheme = self._repository.save_concept_scheme(scheme)

        failures = self._event_publisher.publish(
            SchemeCreated(
                concept_scheme_id=scheme_id,
                title=title,
                taxonomy_id=taxonomy_id,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for SchemeCreated (concept_scheme_id=%s): %s. "
                "Scheme is created but audit trail may have gaps.",
                scheme_id,
                handler_names,
            )

        return scheme

    def get_concept_scheme(self, concept_scheme_id: str) -> ConceptScheme:
        """
        Retrieve a concept scheme by ID.

        Args:
            concept_scheme_id: The ID of the concept scheme

        Returns:
            The ConceptScheme

        Raises:
            EntityNotFoundError: If the scheme does not exist
        """
        scheme = self._repository.get_concept_scheme(concept_scheme_id)
        if scheme is None:
            raise EntityNotFoundError("ConceptScheme", concept_scheme_id)
        return scheme

    def list_concept_schemes(
        self,
        taxonomy_id: str | None = None,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: str | None = None,
    ) -> list[ConceptScheme]:
        """
        Retrieve concept schemes with optional filtering, pagination, sorting, and text search.

        Args:
            taxonomy_id: Optional ID to filter schemes to a specific taxonomy
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (title, created_at, last_modified); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query for LIKE search on title

        Returns:
            List of ConceptScheme entities
        """
        return self._repository.list_concept_schemes(
            taxonomy_id=taxonomy_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            query=query,
        )

    def count_concept_schemes(
        self, taxonomy_id: str | None = None, query: str | None = None
    ) -> int:
        """
        Count concept schemes, optionally filtered by taxonomy and text search.

        Args:
            taxonomy_id: Optional taxonomy ID to filter by
            query: Optional text query for LIKE search on title

        Returns:
            Total count of concept schemes
        """
        return self._repository.count_concept_schemes(taxonomy_id=taxonomy_id, query=query)

    def rename_scheme(self, concept_scheme_id: str, new_title: str) -> ConceptScheme:
        """
        Rename a concept scheme.

        Validates that the new title is unique within the scheme's parent taxonomy.

        Args:
            concept_scheme_id: The ID of the concept scheme to rename
            new_title: The new title for the scheme

        Returns:
            The updated ConceptScheme

        Raises:
            EntityNotFoundError: If the scheme does not exist
            DuplicateEntityError: If a scheme with the new title already exists in this taxonomy
            ValueError: If new_title is empty or whitespace
        """
        if not new_title or not new_title.strip():
            raise ValueError("Title cannot be empty")

        scheme = self._repository.get_concept_scheme(concept_scheme_id)
        if scheme is None:
            raise EntityNotFoundError("ConceptScheme", concept_scheme_id)

        # Check for duplicate title within this taxonomy (excluding the current scheme)
        existing_schemes = self._repository.list_concept_schemes(
            taxonomy_id=scheme.taxonomy_id, limit=None
        )
        if any(
            s.title == new_title and s.id != concept_scheme_id for s in existing_schemes
        ):
            raise DuplicateEntityError(
                f"ConceptScheme with title '{new_title}' already exists in this taxonomy"
            )

        # Guard against no-op updates
        if new_title == scheme.title:
            return scheme

        # Capture old value before modification
        old_title = scheme.title

        scheme.rename(new_title)
        scheme = self._repository.save_concept_scheme(scheme)

        failures = self._event_publisher.publish(
            SchemeUpdated(
                concept_scheme_id=concept_scheme_id,
                taxonomy_id=scheme.taxonomy_id,
                changed_fields=("title",),
                old_values={"title": old_title},
                new_values={"title": new_title},
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for SchemeUpdated (concept_scheme_id=%s): %s. "
                "Scheme is updated but audit trail may have gaps.",
                concept_scheme_id,
                handler_names,
            )

        return scheme

    def delete_scheme(self, concept_scheme_id: str) -> None:
        """
        Delete a concept scheme.

        Validates that the scheme has no classes before deletion.

        Args:
            concept_scheme_id: The ID of the concept scheme to delete

        Raises:
            EntityNotFoundError: If the scheme does not exist
            OntologyError: If the scheme has classes
        """
        scheme = self._repository.get_concept_scheme(concept_scheme_id)
        if scheme is None:
            raise EntityNotFoundError("ConceptScheme", concept_scheme_id)

        # Check for classes
        classes = self._repository.list_classes(concept_scheme_id=concept_scheme_id, limit=None)
        if classes:
            raise OntologyError(
                f"Cannot delete concept scheme {concept_scheme_id}: it has {len(classes)} class(es)"
            )

        self._repository.delete_concept_scheme(concept_scheme_id)

        failures = self._event_publisher.publish(
            SchemeDeleted(
                concept_scheme_id=concept_scheme_id,
                taxonomy_id=scheme.taxonomy_id,
                title=scheme.title,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for SchemeDeleted (concept_scheme_id=%s): %s. "
                "Scheme is deleted but audit trail may have gaps.",
                concept_scheme_id,
                handler_names,
            )

    # Class operations

    def create_class(
        self,
        concept_scheme_id: str,
        title: str,
        description: str | None = None,
        parent_class_id: str | None = None,
    ) -> Class:
        """
        Create a new class within a concept scheme.

        Validates that:
        - The parent scheme exists
        - The title is unique within the scheme
        - If a parent class is provided, it exists and is in the same scheme
        - The parent class ID is not the class ID (prevented in create, but checked)

        Args:
            concept_scheme_id: ID of the parent concept scheme
            title: Display name for the class
            description: Optional longer description
            parent_class_id: Optional ID of the parent class for hierarchy

        Returns:
            The created Class with generated embedding

        Raises:
            EntityNotFoundError: If scheme or parent class does not exist
            DuplicateEntityError: If a class with this title already exists in this scheme
            ValueError: If title is empty
        """
        if not title or not title.strip():
            raise ValueError("Title cannot be empty")

        # Validate scheme exists
        scheme = self._repository.get_concept_scheme(concept_scheme_id)
        if scheme is None:
            raise EntityNotFoundError("ConceptScheme", concept_scheme_id)

        # Check for duplicate title within this scheme
        existing_classes = self._repository.list_classes(
            concept_scheme_id=concept_scheme_id, limit=None
        )
        if any(c.title == title for c in existing_classes):
            raise DuplicateEntityError(
                f"Class with title '{title}' already exists in this scheme"
            )

        # Validate parent class if provided
        if parent_class_id is not None:
            parent_class = self._repository.get_class(parent_class_id)
            if parent_class is None:
                raise EntityNotFoundError("Class", parent_class_id)
            # Verify parent is in the same scheme
            if parent_class.concept_scheme_id != concept_scheme_id:
                raise ValueError(
                    f"Parent class {parent_class_id} is not in the same scheme"
                )

        class_id = str(uuid4())

        # Generate embedding for the class
        embed_text = f"{title} {description or ''}".strip()
        embedding = self._embedding_service.embed(embed_text)

        now = datetime.now(timezone.utc)
        cls = Class(
            id=class_id,
            concept_scheme_id=concept_scheme_id,
            taxonomy_id=scheme.taxonomy_id,
            title=title,
            description=description,
            parent_class_id=parent_class_id,
            embedding=embedding,
            created_at=now,
            last_modified=now,
        )
        cls = self._repository.save_class(cls)

        failures = self._event_publisher.publish(
            ClassCreated(
                class_id=class_id,
                title=title,
                concept_scheme_id=concept_scheme_id,
                taxonomy_id=scheme.taxonomy_id,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for ClassCreated (class_id=%s): %s. "
                "Class is created but audit trail may have gaps.",
                class_id,
                handler_names,
            )

        return cls

    def get_class(self, class_id: str) -> Class:
        """
        Retrieve a class by ID.

        Args:
            class_id: The ID of the class

        Returns:
            The Class

        Raises:
            EntityNotFoundError: If the class does not exist
        """
        cls = self._repository.get_class(class_id)
        if cls is None:
            raise EntityNotFoundError("Class", class_id)
        return cls

    def list_classes(
        self,
        concept_scheme_id: str | None = None,
        parent_class_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Class]:
        """
        Retrieve classes with optional filtering and pagination.

        Args:
            concept_scheme_id: Optional concept scheme ID to filter by
            parent_class_id: Optional parent class ID to filter by (for hierarchy)
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of Class entities
        """
        return self._repository.list_classes(
            concept_scheme_id=concept_scheme_id,
            parent_class_id=parent_class_id,
            limit=limit,
            offset=offset,
        )

    def update_class(
        self,
        class_id: str,
        title: str | None = None,
        description: str | None = None,
    ) -> Class:
        """
        Update a class's title and/or description.

        Validates that:
        - The class exists
        - If a new title is provided, it is unique within the scheme (excluding the current class)

        If either title or description changed, regenerates the embedding.
        If neither changed, skips embedding regeneration.

        Args:
            class_id: The ID of the class to update
            title: New title (optional)
            description: New description (optional)

        Returns:
            The updated Class

        Raises:
            EntityNotFoundError: If the class does not exist
            DuplicateEntityError: If a class with the new title already exists in this scheme
        """
        cls = self._repository.get_class(class_id)
        if cls is None:
            raise EntityNotFoundError("Class", class_id)

        # Capture old values before modification
        old_title = cls.title
        old_description = cls.description

        title_changed = title is not None and title != cls.title
        desc_changed = description is not None and description != cls.description

        # Check for empty title first if title is changing
        if title_changed:
            if not title or not title.strip():
                raise ValueError("Title cannot be empty")
            existing_classes = self._repository.list_classes(
                concept_scheme_id=cls.concept_scheme_id, limit=None
            )
            if any(c.title == title and c.id != class_id for c in existing_classes):
                raise DuplicateEntityError(
                    f"Class with title '{title}' already exists in this scheme"
                )
            cls.title = title

        if desc_changed:
            cls.description = description

        # Regenerate embedding only if title or description changed
        if title_changed or desc_changed:
            embed_text = f"{cls.title} {cls.description or ''}".strip()
            embedding = self._embedding_service.embed(embed_text)
            cls.embedding = embedding

        # Guard against no-op updates
        if not (title_changed or desc_changed):
            return cls

        cls.last_modified = datetime.now(timezone.utc)
        cls = self._repository.save_class(cls)

        changed = tuple(
            f
            for f, was_changed in [
                ("title", title_changed),
                ("description", desc_changed),
            ]
            if was_changed
        )

        old_values: dict[str, str | None] = {}
        new_values: dict[str, str | None] = {}
        if title_changed:
            old_values["title"] = old_title
            new_values["title"] = cls.title
        if desc_changed:
            old_values["description"] = old_description
            new_values["description"] = cls.description

        failures = self._event_publisher.publish(
            ClassUpdated(
                class_id=class_id,
                changed_fields=changed,
                old_values=old_values,
                new_values=new_values,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for ClassUpdated (class_id=%s): %s. "
                "Class is updated but audit trail may have gaps.",
                class_id,
                handler_names,
            )

        return cls

    def delete_class(self, class_id: str) -> None:
        """
        Delete a class.

        Validates that the class has no subclasses or individuals before deletion.
        Cleans up any orphaned relationships where the class is source or target.

        Args:
            class_id: The ID of the class to delete

        Raises:
            EntityNotFoundError: If the class does not exist
            OntologyError: If the class has subclasses or individuals
        """
        cls = self._repository.get_class(class_id)
        if cls is None:
            raise EntityNotFoundError("Class", class_id)

        # Check for subclasses
        subclasses = self._repository.list_classes(parent_class_id=class_id, limit=None)
        if subclasses:
            raise OntologyError(
                f"Cannot delete class {class_id}: it has {len(subclasses)} subclass(es)"
            )

        # Check for individuals referencing this class
        individuals = self._repository.list_individuals(class_id=class_id, limit=None)
        if individuals:
            raise OntologyError(
                f"Cannot delete class {class_id}: it has {len(individuals)} individual(s)"
            )

        # Find and delete all relationships where this class is source or target
        orphaned_relationships = self._repository.list_relationships(
            source_id=class_id, limit=None
        ) + self._repository.list_relationships(target_id=class_id, limit=None)

        for relationship in orphaned_relationships:
            self._repository.delete_relationship(relationship.id)
            failures = self._event_publisher.publish(
                RelationshipDeleted(
                    relationship_id=relationship.id,
                    source_id=relationship.source_id,
                    target_id=relationship.target_id,
                    property_definition_id=relationship.property_definition_id,
                )
            )
            if failures:
                handler_names = ", ".join(name for name, _ in failures)
                _logger.warning(
                    "Event handlers failed for RelationshipDeleted (relationship_id=%s): %s. "
                    "Relationship is deleted but audit trail may have gaps.",
                    relationship.id,
                    handler_names,
                )

        self._repository.delete_class(class_id)

        failures = self._event_publisher.publish(
            ClassDeleted(
                class_id=class_id,
                title=cls.title,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for ClassDeleted (class_id=%s): %s. "
                "Class is deleted but audit trail may have gaps.",
                class_id,
                handler_names,
            )

        failures = self._event_publisher.publish(
            GraphInvalidated(
                taxonomy_id=cls.taxonomy_id,
                reason="class_deleted",
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for GraphInvalidated: %s. "
                "Graph invalidation event may not be recorded in audit trail.",
                handler_names,
            )

    def move_class(self, class_id: str, new_parent_id: str | None) -> Class:
        """
        Move a class in the hierarchy to a new parent.

        Validates that:
        - The class exists
        - The new parent (if provided) exists and is in the same scheme
        - Moving to the new parent would not create a circular reference
          by traversing the ancestor chain of the new parent.

        Algorithm:
        1. Load the class; raise EntityNotFoundError if not found
        2. Guard against no-op: if new_parent_id == cls.parent_class_id, return unchanged
        3. If new_parent_id is None, the class becomes a root; proceed
        4. If new_parent_id == class_id, raise CircularReferenceError
        5. Load the new parent; raise EntityNotFoundError if not found
        6. Verify new parent is in the same scheme; raise ValueError if not
        7. Traverse ancestors of new_parent_id; if any ancestor equals class_id, raise CircularReferenceError
        8. Set the parent and save; publish ClassMoved and GraphInvalidated

        Args:
            class_id: The ID of the class to move
            new_parent_id: The ID of the new parent class, or None to make it a root

        Returns:
            The updated Class

        Raises:
            EntityNotFoundError: If the class, new parent, or any ancestor in the chain does not exist
            CircularReferenceError: If the move would create a circular reference
            ValueError: If new parent is in a different scheme
        """
        cls = self._repository.get_class(class_id)
        if cls is None:
            raise EntityNotFoundError("Class", class_id)

        # Guard against no-op updates
        if new_parent_id == cls.parent_class_id:
            return cls

        if new_parent_id is not None:
            # Check self-reference
            if new_parent_id == class_id:
                raise CircularReferenceError("Cannot set a class as its own parent")

            # Verify new parent exists and is in the same scheme
            new_parent = self._repository.get_class(new_parent_id)
            if new_parent is None:
                raise EntityNotFoundError("Class", new_parent_id)
            if new_parent.concept_scheme_id != cls.concept_scheme_id:
                raise ValueError(
                    f"Parent class {new_parent_id} is not in the same scheme"
                )

            # Traverse ancestor chain of new_parent_id looking for class_id
            current_id: str | None = new_parent_id
            while current_id is not None:
                ancestor = self._repository.get_class(current_id)
                if ancestor is None:
                    raise EntityNotFoundError(
                        "Class",
                        current_id,
                    )
                if ancestor.id == class_id:
                    raise CircularReferenceError(
                        "Move would create a circular reference"
                    )
                current_id = ancestor.parent_class_id

        # Safe to proceed
        old_parent_id = cls.parent_class_id

        if new_parent_id is None:
            cls.remove_subclass_of()
        else:
            cls.add_subclass_of(new_parent_id)

        cls = self._repository.save_class(cls)

        failures = self._event_publisher.publish(
            ClassMoved(
                class_id=class_id,
                old_parent_id=old_parent_id,
                new_parent_id=new_parent_id,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for ClassMoved (class_id=%s): %s. "
                "Class move is recorded but audit trail may have gaps.",
                class_id,
                handler_names,
            )

        failures = self._event_publisher.publish(
            GraphInvalidated(
                taxonomy_id=cls.taxonomy_id,
                reason="class_moved",
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for GraphInvalidated: %s. "
                "Graph invalidation event may not be recorded in audit trail.",
                handler_names,
            )

        return cls

    def move_class_to_scheme(self, class_id: str, target_scheme_id: str) -> Class:
        """
        Move a class to a different concept scheme within the same taxonomy.

        Validates that:
        - The class exists
        - The target concept scheme exists
        - Both the class and target scheme belong to the same taxonomy

        Args:
            class_id: The ID of the class to move
            target_scheme_id: The ID of the target concept scheme

        Returns:
            The updated Class

        Raises:
            EntityNotFoundError: If the class or target scheme does not exist
            ValueError: If the target scheme is in a different taxonomy than the class
        """
        cls = self._repository.get_class(class_id)
        if cls is None:
            raise EntityNotFoundError("Class", class_id)

        target_scheme = self._repository.get_concept_scheme(target_scheme_id)
        if target_scheme is None:
            raise EntityNotFoundError("ConceptScheme", target_scheme_id)

        if cls.taxonomy_id != target_scheme.taxonomy_id:
            raise ValueError(
                f"Cannot move class to scheme in different taxonomy. "
                f"Class taxonomy: {cls.taxonomy_id}, target scheme taxonomy: {target_scheme.taxonomy_id}"
            )

        # Capture old scheme ID before mutation
        old_scheme_id = cls.concept_scheme_id

        # Update the class's concept scheme
        cls.concept_scheme_id = target_scheme_id
        cls = self._repository.save_class(cls)

        # Emit event for audit trail and graph invalidation
        failures = self._event_publisher.publish(
            ClassUpdated(
                class_id=class_id,
                changed_fields=("concept_scheme_id",),
                old_values={"concept_scheme_id": old_scheme_id},
                new_values={"concept_scheme_id": target_scheme_id},
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for ClassUpdated (class_id=%s): %s. "
                "Class moved but audit trail may have gaps.",
                class_id,
                handler_names,
            )

        return cls

    # Relationship operations

    def create_relationship(
        self,
        source_id: str,
        target_id: str,
        property_definition_id: str,
    ) -> Relationship:
        """
        Create a new typed relationship between two entities (Classes or Individuals).

        Validates that:
        - source_id != target_id (no self-loops)
        - Both source and target entities exist (can be Classes or Individuals)
        - The property definition exists
        - The relationship triple (source_id, target_id, property_definition_id) is unique

        Args:
            source_id: ID of the source entity (Class or Individual)
            target_id: ID of the target entity (Class or Individual)
            property_definition_id: ID of the property definition (relationship type)

        Returns:
            The created Relationship

        Raises:
            ValueError: If source_id == target_id
            DuplicateEntityError: If the relationship triple already exists
            EntityNotFoundError: If source, target, or property definition does not exist
        """
        if source_id == target_id:
            raise ValueError("A relationship cannot have the same source and target")

        # Validate property definition exists
        prop_def = self._repository.get_property_definition(property_definition_id)
        if prop_def is None:
            raise EntityNotFoundError("PropertyDefinition", property_definition_id)

        # Validate source entity exists (try Class first, then Individual)
        source_class = self._repository.get_class(source_id)
        taxonomy_id = None
        if source_class:
            taxonomy_id = source_class.taxonomy_id
        else:
            source_individual = self._repository.get_individual(source_id)
            if source_individual:
                # Get taxonomy from first parent class
                individual_class = self._repository.get_class(
                    source_individual.class_ids[0]
                )
                if individual_class:
                    taxonomy_id = individual_class.taxonomy_id
            else:
                raise EntityNotFoundError("Entity", source_id)

        # Validate target entity exists (try Class first, then Individual)
        target_class = self._repository.get_class(target_id)
        if not target_class:
            target_individual = self._repository.get_individual(target_id)
            if not target_individual:
                raise EntityNotFoundError("Entity", target_id)

        # Check if this relationship triple already exists
        existing_relationships = self._repository.list_relationships(
            source_id=source_id,
            target_id=target_id,
            property_id=property_definition_id,
            limit=None,
        )
        if existing_relationships:
            raise DuplicateEntityError(
                f"A relationship with triple (source_id={source_id}, "
                f"target_id={target_id}, property_definition_id={property_definition_id}) "
                "already exists"
            )

        relationship_id = str(uuid4())
        relationship = Relationship(
            id=relationship_id,
            source_id=source_id,
            target_id=target_id,
            property_definition_id=property_definition_id,
        )
        relationship = self._repository.save_relationship(relationship)

        failures = self._event_publisher.publish(
            RelationshipCreated(
                relationship_id=relationship_id,
                source_id=source_id,
                target_id=target_id,
                property_definition_id=property_definition_id,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for RelationshipCreated (relationship_id=%s): %s. "
                "Relationship is created but audit trail may have gaps.",
                relationship_id,
                handler_names,
            )

        # Only emit GraphInvalidated if we found a valid taxonomy
        if taxonomy_id:
            failures = self._event_publisher.publish(
                GraphInvalidated(
                    taxonomy_id=taxonomy_id,
                    reason="relationship_created",
                )
            )
            if failures:
                handler_names = ", ".join(name for name, _ in failures)
                _logger.warning(
                    "Event handlers failed for GraphInvalidated: %s. "
                    "Graph invalidation event may not be recorded in audit trail.",
                    handler_names,
                )

        return relationship

    def get_relationship(self, relationship_id: str) -> Relationship:
        """
        Retrieve a relationship by ID.

        Args:
            relationship_id: The ID of the relationship

        Returns:
            The Relationship

        Raises:
            EntityNotFoundError: If the relationship does not exist
        """
        relationship = self._repository.get_relationship(relationship_id)
        if relationship is None:
            raise EntityNotFoundError("Relationship", relationship_id)
        return relationship

    def list_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        property_id: str | None = None,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: str | None = None,
    ) -> list[Relationship]:
        """
        Retrieve relationships with optional filtering, pagination, sorting, and text search.

        Args:
            source_id: Optional source entity ID to filter by
            target_id: Optional target entity ID to filter by
            property_id: Optional property definition ID to filter by (relationship type)
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (created_at); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query (not used for relationships)

        Returns:
            List of Relationship entities
        """
        return self._repository.list_relationships(
            source_id=source_id,
            target_id=target_id,
            property_id=property_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            query=query,
        )

    def count_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        property_id: str | None = None,
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
        return self._repository.count_relationships(
            source_id=source_id, target_id=target_id, property_id=property_id
        )

    def delete_relationship(self, relationship_id: str) -> None:
        """
        Delete a relationship.

        Args:
            relationship_id: The ID of the relationship to delete

        Raises:
            EntityNotFoundError: If the relationship does not exist
        """
        relationship = self._repository.get_relationship(relationship_id)
        if relationship is None:
            raise EntityNotFoundError("Relationship", relationship_id)

        self._repository.delete_relationship(relationship_id)

        failures = self._event_publisher.publish(
            RelationshipDeleted(
                relationship_id=relationship_id,
                source_id=relationship.source_id,
                target_id=relationship.target_id,
                property_definition_id=relationship.property_definition_id,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for RelationshipDeleted (relationship_id=%s): %s. "
                "Relationship is deleted but audit trail may have gaps.",
                relationship_id,
                handler_names,
            )

        # Determine which taxonomy this relationship belonged to (for graph invalidation)
        # Try source: first as a Class, then as an Individual (get its class then taxonomy)
        taxonomy_id = None

        # Try source as a Class
        source_class = self._repository.get_class(relationship.source_id)
        if source_class:
            taxonomy_id = source_class.taxonomy_id
        else:
            # Try source as an Individual - resolve its parent class to find taxonomy
            source_individual = self._repository.get_individual(relationship.source_id)
            if source_individual and source_individual.class_ids:
                individual_class = self._repository.get_class(
                    source_individual.class_ids[0]
                )
                if individual_class:
                    taxonomy_id = individual_class.taxonomy_id

        # If source didn't yield taxonomy, try target the same way
        if not taxonomy_id:
            target_class = self._repository.get_class(relationship.target_id)
            if target_class:
                taxonomy_id = target_class.taxonomy_id
            else:
                # Try target as an Individual - resolve its parent class to find taxonomy
                target_individual = self._repository.get_individual(
                    relationship.target_id
                )
                if target_individual and target_individual.class_ids:
                    individual_class = self._repository.get_class(
                        target_individual.class_ids[0]
                    )
                    if individual_class:
                        taxonomy_id = individual_class.taxonomy_id

        # Only emit GraphInvalidated if we found a valid taxonomy
        if taxonomy_id:
            failures = self._event_publisher.publish(
                GraphInvalidated(
                    taxonomy_id=taxonomy_id,
                    reason="relationship_deleted",
                )
            )
            if failures:
                handler_names = ", ".join(name for name, _ in failures)
                _logger.warning(
                    "Event handlers failed for GraphInvalidated: %s. "
                    "Graph invalidation event may not be recorded in audit trail.",
                    handler_names,
                )
        else:
            _logger.warning(
                "Could not determine taxonomy for relationship deletion (relationship_id=%s): "
                "source_id=%s and target_id=%s could not be resolved. "
                "Graph cache may be stale. Consider investigating deleted classes or individuals.",
                relationship_id,
                relationship.source_id,
                relationship.target_id,
            )

    # PropertyDefinition operations

    def create_property_definition(
        self,
        identifier: str,
        title: str,
        description: str | None = None,
    ) -> PropertyDefinition:
        """
        Create a new property definition (relationship type).

        Validates that:
        - The identifier is unique across all property definitions
        - The title is unique across all property definitions

        Args:
            identifier: Machine-readable identifier for the property
            title: Display name for the property
            description: Optional longer description

        Returns:
            The created PropertyDefinition

        Raises:
            DuplicateEntityError: If a property with this identifier or title already exists
            ValueError: If identifier or title is empty
        """
        if not identifier or not identifier.strip():
            raise ValueError("Identifier cannot be empty")
        if not title or not title.strip():
            raise ValueError("Title cannot be empty")

        # Check for duplicate identifier and title
        existing_props = self._repository.list_property_definitions(limit=None)
        if any(p.identifier == identifier for p in existing_props):
            raise DuplicateEntityError(
                f"PropertyDefinition with identifier '{identifier}' already exists"
            )
        if any(p.title == title for p in existing_props):
            raise DuplicateEntityError(
                f"PropertyDefinition with title '{title}' already exists"
            )

        property_id = str(uuid4())
        now = datetime.now(timezone.utc)
        prop_def = PropertyDefinition(
            id=property_id,
            identifier=identifier,
            title=title,
            description=description,
            created_at=now,
            last_modified=now,
        )
        prop_def = self._repository.save_property_definition(prop_def)

        failures = self._event_publisher.publish(
            PropertyDefinitionCreated(
                property_id=property_id,
                identifier=identifier,
                title=title,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for PropertyDefinitionCreated (property_id=%s): %s. "
                "Property definition is created but audit trail may have gaps.",
                property_id,
                handler_names,
            )

        return prop_def

    def get_property_definition(self, property_id: str) -> PropertyDefinition:
        """
        Retrieve a property definition by ID.

        Args:
            property_id: The ID of the property definition

        Returns:
            The PropertyDefinition

        Raises:
            EntityNotFoundError: If the property does not exist
        """
        prop_def = self._repository.get_property_definition(property_id)
        if prop_def is None:
            raise EntityNotFoundError("PropertyDefinition", property_id)
        return prop_def

    def get_or_create_property_definition_by_identifier(
        self,
        identifier: str,
        title: str | None = None,
        description: str | None = None,
    ) -> PropertyDefinition:
        """
        Get an existing property definition by identifier, or create it if not found.

        This method provides idempotent creation: if a property definition with this
        identifier already exists, it is returned; otherwise a new one is created with
        the provided title and description.

        Args:
            identifier: Machine-readable identifier to lookup/create
            title: Display name for the property (required if creating new)
            description: Optional longer description (for creation only)

        Returns:
            The PropertyDefinition (either existing or newly created)

        Raises:
            ValueError: If identifier is empty, or if creating and title is empty
            DuplicateEntityError: If a property with this identifier exists but title
                conflicts with an existing different property (title uniqueness constraint)

        Note:
            Atomicity relies on the repository implementation providing transaction
            semantics. If the caller operation fails after this method returns,
            the caller is responsible for cleanup or explicit rollback.
        """
        if not identifier or not identifier.strip():
            raise ValueError("Identifier cannot be empty")

        # Check if property definition already exists by identifier
        existing = self._repository.get_property_definition_by_identifier(identifier)
        if existing:
            return existing

        # Create new property definition with provided title
        if not title or not title.strip():
            raise ValueError(
                "Title cannot be empty when creating a new property definition"
            )

        return self.create_property_definition(
            identifier=identifier,
            title=title,
            description=description,
        )

    def list_property_definitions(
        self,
        is_relevant: bool | None = None,
        limit: int | None = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "asc",
        query: str | None = None,
    ) -> list[PropertyDefinition]:
        """
        Retrieve property definitions with optional filtering, pagination, sorting, and text search.

        Args:
            is_relevant: Optional filter for relevant property definitions
            limit: Maximum number of results to return; None means no limit
            offset: Number of results to skip
            sort_by: Field to sort by (title, created_at, last_modified); None for default
            sort_order: Sort direction (asc or desc)
            query: Text query for LIKE search on title

        Returns:
            List of PropertyDefinition entities
        """
        return self._repository.list_property_definitions(
            is_relevant=is_relevant,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            query=query,
        )

    def count_property_definitions(
        self, is_relevant: bool | None = None, query: str | None = None
    ) -> int:
        """
        Count property definitions, optionally filtered by relevance and text search.

        Args:
            is_relevant: Optional filter for relevant property definitions
            query: Optional text query for LIKE search on title

        Returns:
            Total count of property definitions
        """
        return self._repository.count_property_definitions(is_relevant=is_relevant, query=query)

    def update_property_definition(
        self,
        property_id: str,
        title: str | None = None,
        description: str | None = None,
    ) -> PropertyDefinition:
        """
        Update a property definition's title and/or description.

        Note: identifier cannot be changed after creation.

        Args:
            property_id: The property definition ID
            title: New title (optional)
            description: New description (optional)

        Returns:
            The updated PropertyDefinition

        Raises:
            EntityNotFoundError: If the property does not exist
            DuplicateEntityError: If the new title already exists
            ValueError: If the new title is empty
        """
        prop_def = self._repository.get_property_definition(property_id)
        if prop_def is None:
            raise EntityNotFoundError("PropertyDefinition", property_id)

        # Check if new title is unique
        if title is not None and title != prop_def.title:
            if not title or not title.strip():
                raise ValueError("Title cannot be empty")
            existing_props = self._repository.list_property_definitions(limit=None)
            if any(p.id != property_id and p.title == title for p in existing_props):
                raise DuplicateEntityError(
                    f"PropertyDefinition with title '{title}' already exists"
                )
            prop_def.title = title

        if description is not None:
            prop_def.description = description

        prop_def.last_modified = datetime.now(timezone.utc)
        prop_def = self._repository.save_property_definition(prop_def)

        failures = self._event_publisher.publish(
            PropertyDefinitionUpdated(
                property_id=property_id,
                title=prop_def.title,
                description=prop_def.description,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for PropertyDefinitionUpdated (property_id=%s): %s. "
                "Property definition is updated but audit trail may have gaps.",
                property_id,
                handler_names,
            )

        return prop_def

    def delete_property_definition(self, property_id: str) -> None:
        """
        Delete a property definition.

        Args:
            property_id: The property definition ID

        Raises:
            EntityNotFoundError: If the property does not exist
            OntologyError: If the property is in use by relationships
        """
        prop_def = self._repository.get_property_definition(property_id)
        if prop_def is None:
            raise EntityNotFoundError("PropertyDefinition", property_id)

        # Check if property is in use
        relationships = self._repository.list_relationships(property_id=property_id, limit=None)
        if relationships:
            raise OntologyError(
                f"PropertyDefinition '{property_id}' is in use by {len(relationships)} relationship(s)"
            )

        self._repository.delete_property_definition(property_id)

        failures = self._event_publisher.publish(
            PropertyDefinitionDeleted(
                property_id=property_id,
                identifier=prop_def.identifier,
                title=prop_def.title,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for PropertyDefinitionDeleted (property_id=%s): %s. "
                "Property definition is deleted but audit trail may have gaps.",
                property_id,
                handler_names,
            )

    def update_concept_scheme(
        self,
        concept_scheme_id: str,
        title: str | None = None,
        description: str | None = None,
    ) -> ConceptScheme:
        """
        Update a concept scheme's title and/or description.

        Args:
            concept_scheme_id: The concept scheme ID
            title: New title (optional)
            description: New description (optional)

        Returns:
            The updated ConceptScheme

        Raises:
            EntityNotFoundError: If the concept scheme does not exist
            DuplicateEntityError: If the title already exists
            ValueError: If the title is empty
        """
        scheme = self._repository.get_concept_scheme(concept_scheme_id)
        if scheme is None:
            raise EntityNotFoundError("ConceptScheme", concept_scheme_id)

        # Check if new title is unique
        if title is not None and title != scheme.title:
            if not title or not title.strip():
                raise ValueError("Title cannot be empty")
            existing_schemes = self._repository.list_concept_schemes(
                taxonomy_id=scheme.taxonomy_id, limit=None
            )
            if any(
                s.id != concept_scheme_id and s.title == title for s in existing_schemes
            ):
                raise DuplicateEntityError(
                    f"ConceptScheme with title '{title}' already exists in this taxonomy"
                )
            scheme.title = title

        if description is not None:
            scheme.description = description

        scheme.last_modified = datetime.now(timezone.utc)
        scheme = self._repository.save_concept_scheme(scheme)

        failures = self._event_publisher.publish(
            ConceptSchemeUpdated(
                concept_scheme_id=concept_scheme_id,
                title=scheme.title,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for ConceptSchemeUpdated (concept_scheme_id=%s): %s. "
                "Scheme is updated but audit trail may have gaps.",
                concept_scheme_id,
                handler_names,
            )

        return scheme

    def count_classes(self, concept_scheme_id: str | None = None) -> int:
        """
        Count the number of classes, optionally filtered by concept scheme.

        Args:
            concept_scheme_id: Optional concept scheme ID to filter by

        Returns:
            The count of classes
        """
        classes = self._repository.list_classes(concept_scheme_id=concept_scheme_id)
        return len(classes)

    # Individual operations

    def create_individual(
        self,
        class_ids: str | list[str],
        title: str,
        description: str | None = None,
    ) -> Individual:
        """
        Create a new individual instance of one or more classes.

        Validates that:
        - All classes exist
        - The title is unique within each class
        - At least one class is provided

        Args:
            class_ids: ID(s) of the class(es) this individual instantiates (string or list)
            title: Display name for the individual
            description: Optional longer description

        Returns:
            The created Individual

        Raises:
            EntityNotFoundError: If any class does not exist
            DuplicateEntityError: If an individual with this title already exists in any class
            ValueError: If title is empty, whitespace, or no classes provided
        """
        if not title or not title.strip():
            raise ValueError("Title cannot be empty")

        # Normalize class_ids to a list
        if isinstance(class_ids, str):
            class_ids_list = [class_ids]
        else:
            class_ids_list = class_ids

        if not class_ids_list:
            raise ValueError("Individual must belong to at least one class")

        # Verify all classes exist and get taxonomy from first class
        parent_classes = []
        for class_id in class_ids_list:
            cls = self._repository.get_class(class_id)
            if cls is None:
                raise EntityNotFoundError("Class", class_id)
            parent_classes.append(cls)

        # Check for duplicate title within each class
        for class_id in class_ids_list:
            existing = self._repository.list_individuals(class_id=class_id, limit=None)
            if any(ind.title == title for ind in existing):
                raise DuplicateEntityError(
                    f"Individual with title '{title}' already exists in class '{class_id}'"
                )

        individual_id = str(uuid4())
        now = datetime.now(timezone.utc)
        individual = Individual(
            id=individual_id,
            class_ids=class_ids_list,
            title=title,
            description=description,
            created_at=now,
            last_modified=now,
        )
        individual = self._repository.save_individual(individual)

        # Emit IndividualCreated event
        failures = self._event_publisher.publish(
            IndividualCreated(
                individual_id=individual_id,
                title=title,
                class_ids=class_ids_list,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for IndividualCreated (individual_id=%s): %s. "
                "Individual is created but audit trail may have gaps.",
                individual_id,
                handler_names,
            )

        # Emit GraphInvalidated event using taxonomy from first parent class
        taxonomy_id = parent_classes[0].taxonomy_id
        failures = self._event_publisher.publish(
            GraphInvalidated(
                taxonomy_id=taxonomy_id,
                reason="individual_created",
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for GraphInvalidated: %s. "
                "Graph invalidation event may not be recorded in audit trail.",
                handler_names,
            )

        return individual

    def get_individual(self, individual_id: str) -> Individual:
        """
        Retrieve an individual by ID.

        Args:
            individual_id: The ID of the individual

        Returns:
            The Individual

        Raises:
            EntityNotFoundError: If the individual does not exist
        """
        individual = self._repository.get_individual(individual_id)
        if individual is None:
            raise EntityNotFoundError("Individual", individual_id)
        return individual

    def list_individuals(self, class_id: str | None = None) -> list[Individual]:
        """
        Retrieve all individuals, optionally filtered by class.

        Args:
            class_id: Optional class ID to filter by

        Returns:
            List of individuals matching the filter
        """
        return self._repository.list_individuals(class_id=class_id)

    def update_individual(
        self,
        individual_id: str,
        title: str | None = None,
        description: str | None = None,
    ) -> Individual:
        """
        Update an individual's title and/or description.

        Validates that:
        - The individual exists
        - If title is updated, it is unique within all of the individual's parent classes

        Args:
            individual_id: The ID of the individual to update
            title: New title (optional)
            description: New description (optional)

        Returns:
            The updated Individual

        Raises:
            EntityNotFoundError: If the individual does not exist
            DuplicateEntityError: If title is updated to a value that already exists in any parent class
        """
        individual = self._repository.get_individual(individual_id)
        if individual is None:
            raise EntityNotFoundError("Individual", individual_id)

        # Capture old values
        old_title = individual.title
        old_description = individual.description

        # Track what actually changed
        title_changed = title is not None and title != individual.title
        desc_changed = description is not None and description != individual.description

        # If title is provided, validate emptiness first, then uniqueness
        if title is not None:
            if not title or not title.strip():
                raise ValueError("Title cannot be empty")
            if title_changed:
                # Check uniqueness within each parent class
                for class_id in individual.class_ids:
                    existing = self._repository.list_individuals(class_id=class_id, limit=None)
                    if any(
                        ind.title == title and ind.id != individual_id
                        for ind in existing
                    ):
                        raise DuplicateEntityError(
                            f"Individual with title '{title}' already exists in class '{class_id}'"
                        )
                individual.title = title

        # Update description if provided
        if description is not None:
            individual.description = description

        # Guard against no-op updates
        if not (title_changed or desc_changed):
            return individual

        # Update timestamp and save only if something actually changed
        individual.last_modified = datetime.now(timezone.utc)

        individual = self._repository.save_individual(individual)

        # Emit IndividualUpdated event
        changed_fields = tuple(
            f
            for f, was_changed in [
                ("title", title_changed),
                ("description", desc_changed),
            ]
            if was_changed
        )
        old_values: dict[str, object] = {}
        new_values: dict[str, object] = {}
        if title_changed:
            old_values["title"] = old_title
            new_values["title"] = individual.title
        if desc_changed:
            old_values["description"] = old_description
            new_values["description"] = individual.description

        failures = self._event_publisher.publish(
            IndividualUpdated(
                individual_id=individual_id,
                changed_fields=changed_fields,
                old_values=old_values,
                new_values=new_values,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for IndividualUpdated (individual_id=%s): %s. "
                "Individual is updated but audit trail may have gaps.",
                individual_id,
                handler_names,
            )

        # Emit GraphInvalidated event using taxonomy from first parent class
        parent_class = self._repository.get_class(individual.class_ids[0])
        if parent_class:
            failures = self._event_publisher.publish(
                GraphInvalidated(
                    taxonomy_id=parent_class.taxonomy_id,
                    reason="individual_updated",
                )
            )
            if failures:
                handler_names = ", ".join(name for name, _ in failures)
                _logger.warning(
                    "Event handlers failed for GraphInvalidated: %s. "
                    "Graph invalidation event may not be recorded in audit trail.",
                    handler_names,
                )

        return individual

    def delete_individual(self, individual_id: str) -> None:
        """
        Delete an individual.

        Args:
            individual_id: The ID of the individual to delete

        Raises:
            EntityNotFoundError: If the individual does not exist
        """
        individual = self._repository.get_individual(individual_id)
        if individual is None:
            raise EntityNotFoundError("Individual", individual_id)

        # Find and delete all relationships where this individual is source or target
        orphaned_relationships = self._repository.list_relationships(
            source_id=individual_id, limit=None
        ) + self._repository.list_relationships(target_id=individual_id, limit=None)

        for relationship in orphaned_relationships:
            self._repository.delete_relationship(relationship.id)
            failures = self._event_publisher.publish(
                RelationshipDeleted(
                    relationship_id=relationship.id,
                    source_id=relationship.source_id,
                    target_id=relationship.target_id,
                    property_definition_id=relationship.property_definition_id,
                )
            )
            if failures:
                handler_names = ", ".join(name for name, _ in failures)
                _logger.warning(
                    "Event handlers failed for RelationshipDeleted (relationship_id=%s): %s. "
                    "Relationship is deleted but audit trail may have gaps.",
                    relationship.id,
                    handler_names,
                )

        self._repository.delete_individual(individual_id)

        # Emit IndividualDeleted event
        failures = self._event_publisher.publish(
            IndividualDeleted(
                individual_id=individual_id,
                title=individual.title,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for IndividualDeleted (individual_id=%s): %s. "
                "Individual is deleted but audit trail may have gaps.",
                individual_id,
                handler_names,
            )

        # Emit GraphInvalidated event using taxonomy from first parent class
        parent_class = self._repository.get_class(individual.class_ids[0])
        if parent_class:
            failures = self._event_publisher.publish(
                GraphInvalidated(
                    taxonomy_id=parent_class.taxonomy_id,
                    reason="individual_deleted",
                )
            )
            if failures:
                handler_names = ", ".join(name for name, _ in failures)
                _logger.warning(
                    "Event handlers failed for GraphInvalidated: %s. "
                    "Graph invalidation event may not be recorded in audit trail.",
                    handler_names,
                )

    def add_class_to_individual(self, individual_id: str, class_id: str) -> Individual:
        """
        Add a parent class to an individual (appended to the end).

        Validates that:
        - The individual exists
        - The class exists
        - The class is not already a parent of the individual
        - The individual's title is unique within the target class

        Args:
            individual_id: The ID of the individual
            class_id: The ID of the class to add

        Returns:
            The updated Individual

        Raises:
            EntityNotFoundError: If the individual or class does not exist
            ValueError: If the class is already a parent of the individual
            DuplicateEntityError: If an individual with this title already exists in the target class
        """
        individual = self._repository.get_individual(individual_id)
        if individual is None:
            raise EntityNotFoundError("Individual", individual_id)

        # Verify class exists
        cls = self._repository.get_class(class_id)
        if cls is None:
            raise EntityNotFoundError("Class", class_id)

        # Check if class is already a parent (will raise ValueError if present)
        if class_id in individual.class_ids:
            raise ValueError(f"Class {class_id} is already a parent of this individual")

        # Check for duplicate title within the target class before modifying the individual
        existing = self._repository.list_individuals(class_id=class_id, limit=None)
        if any(ind.title == individual.title for ind in existing):
            raise DuplicateEntityError(
                f"Individual with title '{individual.title}' already exists in class '{class_id}'"
            )

        # Capture old state for event (before mutation)
        old_class_ids = list(individual.class_ids)

        # Add the class to the individual and save
        individual.add_parent_class(class_id)
        individual = self._repository.save_individual(individual)

        # Emit IndividualUpdated event
        failures = self._event_publisher.publish(
            IndividualUpdated(
                individual_id=individual_id,
                changed_fields=("class_ids",),
                old_values={"class_ids": old_class_ids},
                new_values={"class_ids": individual.class_ids},
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for IndividualUpdated (individual_id=%s): %s. "
                "Class added to individual but audit trail may have gaps.",
                individual_id,
                handler_names,
            )

        # Emit GraphInvalidated event
        failures = self._event_publisher.publish(
            GraphInvalidated(
                taxonomy_id=cls.taxonomy_id,
                reason="individual_class_added",
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for GraphInvalidated: %s. "
                "Graph invalidation event may not be recorded in audit trail.",
                handler_names,
            )

        return individual

    def remove_class_from_individual(
        self, individual_id: str, class_id: str
    ) -> Individual:
        """
        Remove a parent class from an individual.

        Args:
            individual_id: The ID of the individual
            class_id: The ID of the class to remove

        Returns:
            The updated Individual

        Raises:
            EntityNotFoundError: If the individual does not exist
            ValueError: If the class is not a parent, or if it's the last parent class
        """
        individual = self._repository.get_individual(individual_id)
        if individual is None:
            raise EntityNotFoundError("Individual", individual_id)

        # Capture old state for event
        old_class_ids = list(individual.class_ids)

        # Remove the class (will raise ValueError if not present or if last)
        individual.remove_parent_class(class_id)
        individual = self._repository.save_individual(individual)

        # Emit IndividualUpdated event (unconditionally - it records individual state change)
        failures = self._event_publisher.publish(
            IndividualUpdated(
                individual_id=individual_id,
                changed_fields=("class_ids",),
                old_values={"class_ids": old_class_ids},
                new_values={"class_ids": individual.class_ids},
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for IndividualUpdated (individual_id=%s): %s. "
                "Class removed from individual but audit trail may have gaps.",
                individual_id,
                handler_names,
            )

        # Get the taxonomy from the removed class for GraphInvalidated event
        cls = self._repository.get_class(class_id)
        if cls:
            # Emit GraphInvalidated event
            failures = self._event_publisher.publish(
                GraphInvalidated(
                    taxonomy_id=cls.taxonomy_id,
                    reason="individual_class_removed",
                )
            )
            if failures:
                handler_names = ", ".join(name for name, _ in failures)
                _logger.warning(
                    "Event handlers failed for GraphInvalidated: %s. "
                    "Graph invalidation event may not be recorded in audit trail.",
                    handler_names,
                )
        else:
            _logger.warning(
                "Could not determine taxonomy for class removal (individual_id=%s, class_id=%s): "
                "class could not be resolved. "
                "Graph cache may be stale. Consider investigating deleted classes.",
                individual_id,
                class_id,
            )

        return individual

    def reorder_individual_classes(
        self, individual_id: str, ordered_class_ids: list[str]
    ) -> Individual:
        """
        Reorder the parent classes for an individual.

        The order matters for property attribute inheritance: when two parent Classes
        declare a property with the same name but conflicting type/constraints, the
        first parent (by class membership order) wins.

        Args:
            individual_id: The ID of the individual
            ordered_class_ids: The new ordered list of class IDs

        Returns:
            The updated Individual

        Raises:
            EntityNotFoundError: If the individual does not exist
            ValueError: If the list is empty, contains duplicates, or doesn't match current classes
        """
        individual = self._repository.get_individual(individual_id)
        if individual is None:
            raise EntityNotFoundError("Individual", individual_id)

        # Capture old state for event
        old_class_ids = list(individual.class_ids)

        # Reorder (will raise ValueError if invalid)
        individual.reorder_parent_classes(ordered_class_ids)
        individual = self._repository.save_individual(individual)

        # Emit IndividualUpdated event
        failures = self._event_publisher.publish(
            IndividualUpdated(
                individual_id=individual_id,
                changed_fields=("class_ids",),
                old_values={"class_ids": old_class_ids},
                new_values={"class_ids": individual.class_ids},
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for IndividualUpdated (individual_id=%s): %s. "
                "Individual classes reordered but audit trail may have gaps.",
                individual_id,
                handler_names,
            )

        # Emit GraphInvalidated event using taxonomy from first parent class
        parent_class = self._repository.get_class(individual.class_ids[0])
        if parent_class:
            failures = self._event_publisher.publish(
                GraphInvalidated(
                    taxonomy_id=parent_class.taxonomy_id,
                    reason="individual_classes_reordered",
                )
            )
            if failures:
                handler_names = ", ".join(name for name, _ in failures)
                _logger.warning(
                    "Event handlers failed for GraphInvalidated: %s. "
                    "Graph invalidation event may not be recorded in audit trail.",
                    handler_names,
                )

        return individual

    def get_individual_properties(self, individual_id: str) -> list[DataPropertyValue]:
        """
        Get the deduplicated property attribute list for an individual.

        Returns the superset of data_properties declared on all parent Classes,
        with first-class-wins precedence on name collisions: when two parent Classes
        declare a property with the same name but conflicting type/constraints,
        the property from the first parent (by class membership order) wins.

        Args:
            individual_id: The ID of the individual

        Returns:
            Deduplicated list of DataPropertyValue with first-class-wins for conflicts

        Raises:
            EntityNotFoundError: If the individual does not exist
        """
        individual = self._repository.get_individual(individual_id)
        if individual is None:
            raise EntityNotFoundError("Individual", individual_id)

        # Collect properties from all parent classes in order
        seen_property_names: set[str] = set()
        deduplicated_properties: list[DataPropertyValue] = []

        for class_id in individual.class_ids:
            cls = self._repository.get_class(class_id)
            if cls is None:
                # Skip if class was deleted (should rarely happen due to FK constraints)
                continue

            for prop in cls.data_properties:
                # First definition of this property name wins
                if prop.property_identifier not in seen_property_names:
                    deduplicated_properties.append(prop)
                    seen_property_names.add(prop.property_identifier)

        return deduplicated_properties

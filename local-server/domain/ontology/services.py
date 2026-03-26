"""
Business logic service for the Ontology Management bounded context.

OntologyService orchestrates all operations on ontology entities, enforcing
invariants and emitting domain events. It depends on three ports: repository
for persistence, embedding service for semantic embeddings, and event publisher
for event distribution.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from typing import Optional

from domain.ontology.entities import Taxonomy, ConceptScheme, Class, Relationship, PropertyDefinition
from domain.ontology.events import (
    TaxonomyCreated, TaxonomyUpdated, TaxonomyDeleted,
    SchemeCreated, SchemeUpdated, SchemeDeleted,
    ClassCreated, ClassUpdated, ClassDeleted,
    ClassMoved, RelationshipCreated, RelationshipDeleted,
    PropertyDefinitionCreated, GraphInvalidated
)
from domain.ontology.exceptions import EntityNotFoundError, CircularReferenceError, DuplicateEntityError, OntologyError
from domain.ontology.ports import OntologyRepository, EmbeddingService, EventPublisher


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

    def create_taxonomy(self, title: str, description: Optional[str] = None) -> Taxonomy:
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
        existing = self._repository.list_taxonomies()
        if any(t.title == title for t in existing):
            raise DuplicateEntityError(f"Taxonomy with title '{title}' already exists")

        taxonomy_id = str(uuid4())
        taxonomy = Taxonomy(
            id=taxonomy_id,
            title=title,
            description=description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._repository.save_taxonomy(taxonomy)

        self._event_publisher.publish(TaxonomyCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=taxonomy_id,
            taxonomy_id=taxonomy_id,
            title=title,
        ))

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

    def list_taxonomies(self) -> list[Taxonomy]:
        """
        Retrieve all taxonomies.

        Returns:
            List of all Taxonomy entities
        """
        return self._repository.list_taxonomies()

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
        existing = self._repository.list_taxonomies()
        if any(t.title == new_title and t.id != taxonomy_id for t in existing):
            raise DuplicateEntityError(f"Taxonomy with title '{new_title}' already exists")

        # Guard against no-op updates
        if new_title == taxonomy.title:
            return taxonomy

        # Capture old value before modification
        old_title = taxonomy.title

        taxonomy.rename(new_title)
        self._repository.save_taxonomy(taxonomy)

        self._event_publisher.publish(TaxonomyUpdated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=taxonomy_id,
            taxonomy_id=taxonomy_id,
            changed_fields=("title",),
            old_values={"title": old_title},
            new_values={"title": new_title},
        ))

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
        schemes = self._repository.list_concept_schemes(taxonomy_id=taxonomy_id)
        if schemes:
            raise OntologyError(f"Cannot delete taxonomy {taxonomy_id}: it has {len(schemes)} concept scheme(s)")

        self._repository.delete_taxonomy(taxonomy_id)

        self._event_publisher.publish(TaxonomyDeleted(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=taxonomy_id,
            taxonomy_id=taxonomy_id,
            title=taxonomy.title,
        ))

    # ConceptScheme operations

    def create_scheme(self, taxonomy_id: str, title: str, description: Optional[str] = None) -> ConceptScheme:
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
        existing_schemes = self._repository.list_concept_schemes(taxonomy_id=taxonomy_id)
        if any(s.title == title for s in existing_schemes):
            raise DuplicateEntityError(f"ConceptScheme with title '{title}' already exists in this taxonomy")

        scheme_id = str(uuid4())
        scheme = ConceptScheme(
            id=scheme_id,
            taxonomy_id=taxonomy_id,
            title=title,
            description=description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._repository.save_concept_scheme(scheme)

        self._event_publisher.publish(SchemeCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=scheme_id,
            scheme_id=scheme_id,
            title=title,
            taxonomy_id=taxonomy_id,
        ))

        return scheme

    def get_concept_scheme(self, scheme_id: str) -> ConceptScheme:
        """
        Retrieve a concept scheme by ID.

        Args:
            scheme_id: The ID of the concept scheme

        Returns:
            The ConceptScheme

        Raises:
            EntityNotFoundError: If the scheme does not exist
        """
        scheme = self._repository.get_concept_scheme(scheme_id)
        if scheme is None:
            raise EntityNotFoundError("ConceptScheme", scheme_id)
        return scheme

    def list_concept_schemes(self, taxonomy_id: Optional[str] = None) -> list[ConceptScheme]:
        """
        Retrieve concept schemes, optionally filtered by taxonomy.

        Args:
            taxonomy_id: Optional ID to filter schemes to a specific taxonomy

        Returns:
            List of ConceptScheme entities
        """
        return self._repository.list_concept_schemes(taxonomy_id=taxonomy_id)

    def rename_scheme(self, scheme_id: str, new_title: str) -> ConceptScheme:
        """
        Rename a concept scheme.

        Validates that the new title is unique within the scheme's parent taxonomy.

        Args:
            scheme_id: The ID of the concept scheme to rename
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

        scheme = self._repository.get_concept_scheme(scheme_id)
        if scheme is None:
            raise EntityNotFoundError("ConceptScheme", scheme_id)

        # Check for duplicate title within this taxonomy (excluding the current scheme)
        existing_schemes = self._repository.list_concept_schemes(taxonomy_id=scheme.taxonomy_id)
        if any(s.title == new_title and s.id != scheme_id for s in existing_schemes):
            raise DuplicateEntityError(f"ConceptScheme with title '{new_title}' already exists in this taxonomy")

        # Guard against no-op updates
        if new_title == scheme.title:
            return scheme

        # Capture old value before modification
        old_title = scheme.title

        scheme.rename(new_title)
        self._repository.save_concept_scheme(scheme)

        self._event_publisher.publish(SchemeUpdated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=scheme_id,
            scheme_id=scheme_id,
            taxonomy_id=scheme.taxonomy_id,
            changed_fields=("title",),
            old_values={"title": old_title},
            new_values={"title": new_title},
        ))

        return scheme

    def delete_scheme(self, scheme_id: str) -> None:
        """
        Delete a concept scheme.

        Validates that the scheme has no classes before deletion.

        Args:
            scheme_id: The ID of the concept scheme to delete

        Raises:
            EntityNotFoundError: If the scheme does not exist
            OntologyError: If the scheme has classes
        """
        scheme = self._repository.get_concept_scheme(scheme_id)
        if scheme is None:
            raise EntityNotFoundError("ConceptScheme", scheme_id)

        # Check for classes
        classes = self._repository.list_classes(scheme_id=scheme_id)
        if classes:
            raise OntologyError(f"Cannot delete concept scheme {scheme_id}: it has {len(classes)} class(es)")

        self._repository.delete_concept_scheme(scheme_id)

        self._event_publisher.publish(SchemeDeleted(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=scheme_id,
            scheme_id=scheme_id,
            taxonomy_id=scheme.taxonomy_id,
            title=scheme.title,
        ))

    # Class operations

    def create_class(
        self,
        scheme_id: str,
        title: str,
        description: Optional[str] = None,
        parent_class_id: Optional[str] = None,
    ) -> Class:
        """
        Create a new class within a concept scheme.

        Validates that:
        - The parent scheme exists
        - The title is unique within the scheme
        - If a parent class is provided, it exists and is in the same scheme
        - The parent class ID is not the class ID (prevented in create, but checked)

        Args:
            scheme_id: ID of the parent concept scheme
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
        scheme = self._repository.get_concept_scheme(scheme_id)
        if scheme is None:
            raise EntityNotFoundError("ConceptScheme", scheme_id)

        # Check for duplicate title within this scheme
        existing_classes = self._repository.list_classes(scheme_id=scheme_id)
        if any(c.title == title for c in existing_classes):
            raise DuplicateEntityError(f"Class with title '{title}' already exists in this scheme")

        # Validate parent class if provided
        if parent_class_id is not None:
            parent_class = self._repository.get_class(parent_class_id)
            if parent_class is None:
                raise EntityNotFoundError("Class", parent_class_id)
            # Verify parent is in the same scheme
            if parent_class.scheme_id != scheme_id:
                raise ValueError(f"Parent class {parent_class_id} is not in the same scheme")

        class_id = str(uuid4())

        # Generate embedding for the class
        embed_text = f"{title} {description or ''}".strip()
        embedding = self._embedding_service.embed_text(embed_text)

        cls = Class(
            id=class_id,
            scheme_id=scheme_id,
            taxonomy_id=scheme.taxonomy_id,
            title=title,
            description=description,
            parent_class_id=parent_class_id,
            title_embedding=embedding,
            definition_embedding=embedding,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._repository.save_class(cls)

        self._event_publisher.publish(ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=class_id,
            class_id=class_id,
            title=title,
            scheme_id=scheme_id,
            taxonomy_id=scheme.taxonomy_id,
        ))

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
        return self._repository.list_classes(
            scheme_id=scheme_id,
            parent_class_id=parent_class_id,
            limit=limit,
            offset=offset,
        )

    def update_class(
        self,
        class_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
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

        # Check for duplicate title within this scheme if title is changing
        if title_changed:
            existing_classes = self._repository.list_classes(scheme_id=cls.scheme_id)
            if any(c.title == title and c.id != class_id for c in existing_classes):
                raise DuplicateEntityError(f"Class with title '{title}' already exists in this scheme")

        if title is not None:
            cls.rename(title)
        if description is not None:
            cls.description = description

        # Regenerate embedding only if title or description changed
        if title_changed or desc_changed:
            embed_text = f"{cls.title} {cls.description or ''}".strip()
            embedding = self._embedding_service.embed_text(embed_text)
            cls.title_embedding = embedding
            cls.definition_embedding = embedding

        # Guard against no-op updates
        if not (title_changed or desc_changed):
            return cls

        cls.updated_at = datetime.utcnow()
        self._repository.save_class(cls)

        changed = tuple(f for f, was_changed in [("title", title_changed), ("description", desc_changed)] if was_changed)

        old_values: dict[str, str | None] = {}
        new_values: dict[str, str | None] = {}
        if title_changed:
            old_values["title"] = old_title
            new_values["title"] = cls.title
        if desc_changed:
            old_values["description"] = old_description
            new_values["description"] = cls.description

        self._event_publisher.publish(ClassUpdated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=class_id,
            class_id=class_id,
            changed_fields=changed,
            old_values=old_values,
            new_values=new_values,
        ))

        return cls

    def delete_class(self, class_id: str) -> None:
        """
        Delete a class.

        Validates that the class has no subclasses before deletion.
        Cleans up any orphaned relationships where the class is source or target.

        Args:
            class_id: The ID of the class to delete

        Raises:
            EntityNotFoundError: If the class does not exist
            OntologyError: If the class has subclasses
        """
        cls = self._repository.get_class(class_id)
        if cls is None:
            raise EntityNotFoundError("Class", class_id)

        # Check for subclasses
        subclasses = self._repository.list_classes(parent_class_id=class_id)
        if subclasses:
            raise OntologyError(f"Cannot delete class {class_id}: it has {len(subclasses)} subclass(es)")

        # Find and delete all relationships where this class is source or target
        orphaned_relationships = self._repository.list_relationships(
            source_id=class_id
        ) + self._repository.list_relationships(target_id=class_id)

        for relationship in orphaned_relationships:
            self._repository.delete_relationship(relationship.id)
            self._event_publisher.publish(RelationshipDeleted(
                event_id=str(uuid4()),
                occurred_at=datetime.utcnow(),
                aggregate_id=relationship.id,
                relationship_id=relationship.id,
                source_id=relationship.source_id,
                target_id=relationship.target_id,
                property_definition_id=relationship.property_definition_id,
            ))

        self._repository.delete_class(class_id)

        self._event_publisher.publish(ClassDeleted(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=class_id,
            class_id=class_id,
            title=cls.title,
        ))

        self._event_publisher.publish(GraphInvalidated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=cls.taxonomy_id,
            taxonomy_id=cls.taxonomy_id,
            reason="class_deleted",
        ))

    def move_class(self, class_id: str, new_parent_id: Optional[str]) -> Class:
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
            EntityNotFoundError: If the class or new parent does not exist
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
            if new_parent.scheme_id != cls.scheme_id:
                raise ValueError(f"Parent class {new_parent_id} is not in the same scheme")

            # Traverse ancestor chain of new_parent_id looking for class_id
            current_id: str | None = new_parent_id
            while current_id is not None:
                ancestor = self._repository.get_class(current_id)
                if ancestor is None:
                    raise CircularReferenceError(
                        f"Corrupted hierarchy: ancestor class {current_id} does not exist; "
                        f"cannot complete circular reference detection"
                    )
                if ancestor.id == class_id:
                    raise CircularReferenceError("Move would create a circular reference")
                current_id = ancestor.parent_class_id

        # Safe to proceed
        old_parent_id = cls.parent_class_id

        if new_parent_id is None:
            cls.remove_subclass_of()
        else:
            cls.add_subclass_of(new_parent_id)

        self._repository.save_class(cls)

        self._event_publisher.publish(ClassMoved(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=class_id,
            class_id=class_id,
            old_parent_id=old_parent_id,
            new_parent_id=new_parent_id,
        ))

        self._event_publisher.publish(GraphInvalidated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=cls.taxonomy_id,
            taxonomy_id=cls.taxonomy_id,
            reason="class_moved",
        ))

        return cls

    # Relationship operations

    def create_relationship(
        self,
        source_id: str,
        target_id: str,
        property_definition_id: str,
    ) -> Relationship:
        """
        Create a new typed relationship between two entities.

        Validates that:
        - source_id != target_id (no self-loops)
        - Both source and target entities exist
        - The property definition exists
        - The relationship triple (source_id, target_id, property_definition_id) is unique

        Args:
            source_id: ID of the source entity
            target_id: ID of the target entity
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

        # Validate source entity exists
        source_class = self._repository.get_class(source_id)
        if source_class is None:
            raise EntityNotFoundError("Class", source_id)

        # Validate target entity exists
        target_class = self._repository.get_class(target_id)
        if target_class is None:
            raise EntityNotFoundError("Class", target_id)

        # Check if this relationship triple already exists
        existing_relationships = self._repository.list_relationships(
            source_id=source_id,
            target_id=target_id,
            property_id=property_definition_id,
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
            property_label=prop_def.title,
            created_at=datetime.utcnow(),
        )
        self._repository.save_relationship(relationship)

        # Determine which taxonomy this relationship belongs to using the source class
        taxonomy_id = source_class.taxonomy_id

        self._event_publisher.publish(RelationshipCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=relationship_id,
            relationship_id=relationship_id,
            source_id=source_id,
            target_id=target_id,
            property_definition_id=property_definition_id,
        ))

        self._event_publisher.publish(GraphInvalidated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=taxonomy_id,
            taxonomy_id=taxonomy_id,
            reason="relationship_created",
        ))

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
        return self._repository.list_relationships(source_id=source_id, target_id=target_id, property_id=property_id)

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

        self._event_publisher.publish(RelationshipDeleted(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=relationship_id,
            relationship_id=relationship_id,
            source_id=relationship.source_id,
            target_id=relationship.target_id,
            property_definition_id=relationship.property_definition_id,
        ))

        # Determine which taxonomy this relationship belonged to (for graph invalidation)
        # Try source: first as a Class, then as an Individual (get its class then taxonomy)
        taxonomy_id = None

        # Try source as a Class
        source_class = self._repository.get_class(relationship.source_id)
        if source_class:
            taxonomy_id = source_class.taxonomy_id
        else:
            # Try source as an Individual
            source_individual = self._repository.get_individual(relationship.source_id)
            if source_individual:
                individual_class = self._repository.get_class(source_individual.class_id)
                if individual_class:
                    taxonomy_id = individual_class.taxonomy_id

        # If source didn't yield taxonomy, try target the same way
        if not taxonomy_id:
            target_class = self._repository.get_class(relationship.target_id)
            if target_class:
                taxonomy_id = target_class.taxonomy_id
            else:
                target_individual = self._repository.get_individual(relationship.target_id)
                if target_individual:
                    individual_class = self._repository.get_class(target_individual.class_id)
                    if individual_class:
                        taxonomy_id = individual_class.taxonomy_id

        # Only emit GraphInvalidated if we found a valid taxonomy
        if taxonomy_id:
            self._event_publisher.publish(GraphInvalidated(
                event_id=str(uuid4()),
                occurred_at=datetime.utcnow(),
                aggregate_id=taxonomy_id,
                taxonomy_id=taxonomy_id,
                reason="relationship_deleted",
            ))

    # PropertyDefinition operations

    def create_property_definition(
        self,
        identifier: str,
        title: str,
        description: Optional[str] = None,
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
        existing_props = self._repository.list_property_definitions()
        if any(p.identifier == identifier for p in existing_props):
            raise DuplicateEntityError(f"PropertyDefinition with identifier '{identifier}' already exists")
        if any(p.title == title for p in existing_props):
            raise DuplicateEntityError(f"PropertyDefinition with title '{title}' already exists")

        property_id = str(uuid4())
        prop_def = PropertyDefinition(
            id=property_id,
            identifier=identifier,
            title=title,
            description=description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._repository.save_property_definition(prop_def)

        self._event_publisher.publish(PropertyDefinitionCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id=property_id,
            property_id=property_id,
            title=title,
        ))

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

    def list_property_definitions(self, is_relevant: Optional[bool] = None) -> list[PropertyDefinition]:
        """
        Retrieve property definitions, optionally filtered by relevance.

        Args:
            is_relevant: Optional filter for relevant property definitions

        Returns:
            List of PropertyDefinition entities
        """
        return self._repository.list_property_definitions(is_relevant=is_relevant)

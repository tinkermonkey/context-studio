"""
Change event recorder adapter.

Subscribes to domain events and persists them as change records for auditing
and versioning. Implements the pattern where domain events are consumed by
dedicated handlers outside the domain layer.

This keeps event persistence concerns out of the domain and makes it easy to
add other event consumers (e.g., notifications, graph cache invalidation)
without modifying domain code.
"""

from enum import Enum
from typing import Any, Optional

from domain.extraction.events import ExtractionCompleted
from domain.interchange.services import get_current_batch_run_id
from domain.ontology.events import (
    AttributeDefinitionCreated,
    AttributeDefinitionDeleted,
    AttributeDefinitionUpdated,
    ClassCreated,
    ClassDeleted,
    ClassMoved,
    ClassUpdated,
    IndividualCreated,
    IndividualDeleted,
    IndividualUpdated,
    PropertyDefinitionCreated,
    PropertyDefinitionDeleted,
    PropertyDefinitionUpdated,
    RelationshipCreated,
    RelationshipDeleted,
    RelationshipUpdated,
    SchemeCreated,
    SchemeDeleted,
    SchemeUpdated,
    TaxonomyCreated,
    TaxonomyDeleted,
    TaxonomyUpdated,
)
from domain.ports import ChangeRecordPort, EventPublisher
from domain.versioning.value_objects import ChangeOperation
from utils.logger import get_logger

logger = get_logger(__name__)


def _json_safe(values: dict[str, Any]) -> dict[str, Any]:
    """Event values with enums (e.g. an attribute's DataType) stored as their plain value."""
    return {k: v.value if isinstance(v, Enum) else v for k, v in values.items()}


class ChangeEventRecorder:
    """
    Records domain events to the change audit trail.

    Subscribes to domain events and persists them as change records using
    a change record port. Designed to be registered with the event
    publisher during application startup.
    """

    def __init__(self, change_repo: ChangeRecordPort) -> None:
        """
        Initialize the recorder with a change repository.

        Args:
            change_repo: Port implementation for persisting changes
        """
        self.change_repo = change_repo

    def subscribe_ontology_events(self, publisher: EventPublisher) -> None:
        """Subscribe this recorder to every ontology event it records (for scripts)."""
        for event, handler in (
            (TaxonomyCreated, self.on_taxonomy_created),
            (TaxonomyUpdated, self.on_taxonomy_updated),
            (TaxonomyDeleted, self.on_taxonomy_deleted),
            (SchemeCreated, self.on_scheme_created),
            (SchemeUpdated, self.on_scheme_updated),
            (SchemeDeleted, self.on_scheme_deleted),
            (ClassCreated, self.on_class_created),
            (ClassUpdated, self.on_class_updated),
            (ClassMoved, self.on_class_moved),
            (ClassDeleted, self.on_class_deleted),
            (PropertyDefinitionCreated, self.on_property_definition_created),
            (PropertyDefinitionUpdated, self.on_property_definition_updated),
            (PropertyDefinitionDeleted, self.on_property_definition_deleted),
            (AttributeDefinitionCreated, self.on_attribute_definition_created),
            (AttributeDefinitionUpdated, self.on_attribute_definition_updated),
            (AttributeDefinitionDeleted, self.on_attribute_definition_deleted),
            (IndividualCreated, self.on_individual_created),
            (IndividualUpdated, self.on_individual_updated),
            (IndividualDeleted, self.on_individual_deleted),
            (RelationshipCreated, self.on_relationship_created),
            (RelationshipUpdated, self.on_relationship_updated),
            (RelationshipDeleted, self.on_relationship_deleted),
        ):
            publisher.subscribe(event, handler)

    def on_extraction_completed(self, event: ExtractionCompleted) -> None:
        """
        Handle ExtractionCompleted events.

        Records extraction completion to the audit trail, capturing the
        result ID, entity count, and duration.

        Exceptions are allowed to propagate to the event publisher so they
        can be reported to the caller for visibility and recovery.

        Args:
            event: The ExtractionCompleted event to record

        Raises:
            Any exception from the change repository is propagated to allow
            the event publisher to include it in the failures list.
        """
        batch_run_id = get_current_batch_run_id()
        change_id = self.change_repo.record_change(
            entity_id=event.result_id,
            entity_type="extraction_result",
            operation=ChangeOperation.CREATE,
            new_state={
                "result_id": event.result_id,
                "entity_count": event.entity_count,
                "duration_ms": event.duration_ms,
            },
            change_reason="Extraction processing completed",
            batch_run_id=batch_run_id,
        )
        logger.debug(
            f"Recorded extraction completion: result_id={event.result_id}, "
            f"change_event_id={change_id}"
            + (f", batch_run_id={batch_run_id}" if batch_run_id else "")
        )

    # ==================== Ontology Event Handlers ====================

    def _record(
        self,
        entity_id: str,
        entity_type: str,
        operation: ChangeOperation,
        new_state: Optional[dict] = None,
        previous_state: Optional[dict] = None,
        change_reason: str = "",
    ) -> str:
        """
        Helper method to record a change event.

        Reduces boilerplate for recording ontology mutations with consistent
        logging and error propagation. Automatically includes batch_run_id
        from the correlation context if a batch operation (import or extraction) is in progress.

        Args:
            entity_id: ID of the entity that changed
            entity_type: Type of entity (e.g., "taxonomy", "class", "relationship")
            operation: Type of operation (CREATE, UPDATE, DELETE)
            new_state: New state of the entity. None is converted to {} before recording.
            previous_state: Previous state of the entity (None for CREATE)
            change_reason: Human-readable reason for the change

        Returns:
            The ID of the recorded change event

        Raises:
            Any exception from the change repository is propagated to allow
            the event publisher to include it in the failures list.
        """
        # Get current batch_run_id from correlation context if set
        batch_run_id = get_current_batch_run_id()

        # The correlation context holds either an import or extraction run ID
        # The change repository will persist this as batch_run_id
        change_id = self.change_repo.record_change(
            entity_id=entity_id,
            entity_type=entity_type,
            operation=operation,
            new_state=new_state or {},
            previous_state=previous_state,
            change_reason=change_reason,
            batch_run_id=batch_run_id,
        )
        logger.debug(
            f"Recorded ontology change: entity_id={entity_id}, "
            f"entity_type={entity_type}, operation={operation}, "
            f"change_event_id={change_id}"
            + (f", batch_run_id={batch_run_id}" if batch_run_id else "")
        )
        return change_id

    # --- CREATE Pattern Handlers ---

    def on_taxonomy_created(self, event: TaxonomyCreated) -> None:
        """Handle TaxonomyCreated events."""
        self._record(
            entity_id=event.taxonomy_id,
            entity_type="taxonomy",
            operation=ChangeOperation.CREATE,
            new_state={"taxonomy_id": event.taxonomy_id, "title": event.title},
            change_reason="Taxonomy created",
        )

    def on_scheme_created(self, event: SchemeCreated) -> None:
        """Handle SchemeCreated events."""
        self._record(
            entity_id=event.concept_scheme_id,
            entity_type="concept_scheme",
            operation=ChangeOperation.CREATE,
            new_state={
                "concept_scheme_id": event.concept_scheme_id,
                "title": event.title,
                "taxonomy_id": event.taxonomy_id,
            },
            change_reason="Concept scheme created",
        )

    def on_class_created(self, event: ClassCreated) -> None:
        """Handle ClassCreated events."""
        self._record(
            entity_id=event.class_id,
            entity_type="class",
            operation=ChangeOperation.CREATE,
            new_state={
                "class_id": event.class_id,
                "title": event.title,
                "concept_scheme_id": event.concept_scheme_id,
                "taxonomy_id": event.taxonomy_id,
            },
            change_reason="Class created",
        )

    def on_relationship_created(self, event: RelationshipCreated) -> None:
        """Handle RelationshipCreated events."""
        self._record(
            entity_id=event.relationship_id,
            entity_type="relationship",
            operation=ChangeOperation.CREATE,
            new_state={
                "relationship_id": event.relationship_id,
                "source_id": event.source_id,
                "target_id": event.target_id,
                "property_definition_id": event.property_definition_id,
                "attributes": event.attributes,
            },
            change_reason="Relationship created",
        )

    def on_property_definition_created(self, event: PropertyDefinitionCreated) -> None:
        """Handle PropertyDefinitionCreated events."""
        self._record(
            entity_id=event.property_id,
            entity_type="property_definition",
            operation=ChangeOperation.CREATE,
            new_state={
                "property_id": event.property_id,
                "identifier": event.identifier,
                "title": event.title,
            },
            change_reason="Property definition created",
        )

    # --- UPDATE Pattern Handlers ---

    def on_taxonomy_updated(self, event: TaxonomyUpdated) -> None:
        """Handle TaxonomyUpdated events."""
        self._record(
            entity_id=event.taxonomy_id,
            entity_type="taxonomy",
            operation=ChangeOperation.UPDATE,
            new_state=event.new_values,
            previous_state=event.old_values,
            change_reason=f"Taxonomy updated: {', '.join(event.changed_fields)}",
        )

    def on_scheme_updated(self, event: SchemeUpdated) -> None:
        """Handle SchemeUpdated events."""
        self._record(
            entity_id=event.concept_scheme_id,
            entity_type="concept_scheme",
            operation=ChangeOperation.UPDATE,
            new_state=event.new_values,
            previous_state=event.old_values,
            change_reason=f"Concept scheme updated: {', '.join(event.changed_fields)}",
        )

    def on_class_updated(self, event: ClassUpdated) -> None:
        """Handle ClassUpdated events."""
        self._record(
            entity_id=event.class_id,
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state=event.new_values,
            previous_state=event.old_values,
            change_reason=f"Class updated: {', '.join(event.changed_fields)}",
        )

    def on_class_moved(self, event: ClassMoved) -> None:
        """Handle ClassMoved events."""
        self._record(
            entity_id=event.class_id,
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            new_state={
                "parent_class_id": event.new_parent_id,
            },
            previous_state={
                "parent_class_id": event.old_parent_id,
            },
            change_reason=(
                f"Class moved from parent {event.old_parent_id} to" f" {event.new_parent_id}"
            ),
        )

    def on_property_definition_updated(self, event: PropertyDefinitionUpdated) -> None:
        """Handle PropertyDefinitionUpdated events."""
        self._record(
            entity_id=event.property_id,
            entity_type="property_definition",
            operation=ChangeOperation.UPDATE,
            new_state=event.new_values,
            previous_state=event.old_values,
            change_reason=f"Property definition updated: {', '.join(event.changed_fields)}",
        )

    def on_relationship_updated(self, event: RelationshipUpdated) -> None:
        """Handle RelationshipUpdated events (attributes only)."""
        self._record(
            entity_id=event.relationship_id,
            entity_type="relationship",
            operation=ChangeOperation.UPDATE,
            new_state=event.new_values,
            previous_state=event.old_values,
            change_reason=f"Relationship updated: {', '.join(event.changed_fields)}",
        )

    # --- DELETE Pattern Handlers ---

    def on_taxonomy_deleted(self, event: TaxonomyDeleted) -> None:
        """Handle TaxonomyDeleted events."""
        self._record(
            entity_id=event.taxonomy_id,
            entity_type="taxonomy",
            operation=ChangeOperation.DELETE,
            previous_state=event.snapshot,
            change_reason="Taxonomy deleted",
        )

    def on_scheme_deleted(self, event: SchemeDeleted) -> None:
        """Handle SchemeDeleted events."""
        self._record(
            entity_id=event.concept_scheme_id,
            entity_type="concept_scheme",
            operation=ChangeOperation.DELETE,
            previous_state=event.snapshot,
            change_reason="Concept scheme deleted",
        )

    def on_class_deleted(self, event: ClassDeleted) -> None:
        """Handle ClassDeleted events."""
        self._record(
            entity_id=event.class_id,
            entity_type="class",
            operation=ChangeOperation.DELETE,
            previous_state=event.snapshot,
            change_reason="Class deleted",
        )

    def on_relationship_deleted(self, event: RelationshipDeleted) -> None:
        """Handle RelationshipDeleted events."""
        self._record(
            entity_id=event.relationship_id,
            entity_type="relationship",
            operation=ChangeOperation.DELETE,
            previous_state=event.snapshot,
            change_reason="Relationship deleted",
        )

    def on_property_definition_deleted(self, event: PropertyDefinitionDeleted) -> None:
        """Handle PropertyDefinitionDeleted events."""
        self._record(
            entity_id=event.property_id,
            entity_type="property_definition",
            operation=ChangeOperation.DELETE,
            previous_state=event.snapshot,
            change_reason="Property definition deleted",
        )

    def on_attribute_definition_created(self, event: AttributeDefinitionCreated) -> None:
        """Handle AttributeDefinitionCreated events."""
        self._record(
            entity_id=event.attribute_definition_id,
            entity_type="attribute_definition",
            operation=ChangeOperation.CREATE,
            new_state={
                "attribute_definition_id": event.attribute_definition_id,
                "class_id": event.class_id,
                "identifier": event.identifier,
                "title": event.title,
            },
            change_reason="Attribute definition created",
        )

    def on_attribute_definition_updated(self, event: AttributeDefinitionUpdated) -> None:
        """Handle AttributeDefinitionUpdated events."""
        self._record(
            entity_id=event.attribute_definition_id,
            entity_type="attribute_definition",
            operation=ChangeOperation.UPDATE,
            new_state=_json_safe(event.new_values),
            previous_state=_json_safe(event.old_values),
            change_reason=f"Attribute definition updated: {', '.join(event.changed_fields)}",
        )

    def on_attribute_definition_deleted(self, event: AttributeDefinitionDeleted) -> None:
        """Handle AttributeDefinitionDeleted events."""
        self._record(
            entity_id=event.attribute_definition_id,
            entity_type="attribute_definition",
            operation=ChangeOperation.DELETE,
            previous_state=event.snapshot,
            change_reason="Attribute definition deleted",
        )

    # --- Individual Event Handlers ---

    def on_individual_created(self, event: IndividualCreated) -> None:
        """Handle IndividualCreated events."""
        self._record(
            entity_id=event.individual_id,
            entity_type="individual",
            operation=ChangeOperation.CREATE,
            new_state={
                "individual_id": event.individual_id,
                "title": event.title,
                "class_ids": event.class_ids,
                "external_references": event.external_references,
            },
            change_reason="Individual created",
        )

    def on_individual_updated(self, event: IndividualUpdated) -> None:
        """Handle IndividualUpdated events."""
        self._record(
            entity_id=event.individual_id,
            entity_type="individual",
            operation=ChangeOperation.UPDATE,
            new_state=event.new_values,
            previous_state=event.old_values,
            change_reason=f"Individual updated: {', '.join(event.changed_fields)}",
        )

    def on_individual_deleted(self, event: IndividualDeleted) -> None:
        """Handle IndividualDeleted events."""
        self._record(
            entity_id=event.individual_id,
            entity_type="individual",
            operation=ChangeOperation.DELETE,
            previous_state=event.snapshot,
            change_reason="Individual deleted",
        )

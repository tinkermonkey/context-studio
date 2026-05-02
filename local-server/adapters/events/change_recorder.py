"""
Change event recorder adapter.

Subscribes to domain events and persists them as change records for auditing
and versioning. Implements the pattern where domain events are consumed by
dedicated handlers outside the domain layer.

This keeps event persistence concerns out of the domain and makes it easy to
add other event consumers (e.g., notifications, graph cache invalidation)
without modifying domain code.
"""

from typing import Optional

from domain.ports import ChangeRecordPort
from domain.extraction.events import ExtractionCompleted
from domain.pipeline.events import PipelineExecuted
from domain.ontology.events import (
    TaxonomyCreated,
    SchemeCreated,
    ClassCreated,
    ClassUpdated,
    ClassDeleted,
    ClassMoved,
    RelationshipCreated,
    RelationshipDeleted,
    PropertyDefinitionCreated,
    PropertyDefinitionUpdated,
    PropertyDefinitionDeleted,
    TaxonomyUpdated,
    TaxonomyDeleted,
    SchemeUpdated,
    SchemeDeleted,
    ConceptSchemeUpdated,
    IndividualCreated,
    IndividualUpdated,
    IndividualDeleted,
)
from domain.versioning.value_objects import ChangeOperation
from utils.logger import get_logger


logger = get_logger(__name__)


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
        )
        logger.debug(
            f"Recorded extraction completion: result_id={event.result_id}, "
            f"change_event_id={change_id}"
        )

    def on_pipeline_executed(self, event: PipelineExecuted) -> None:
        """
        Handle PipelineExecuted events.

        Records pipeline execution completion to the audit trail, capturing
        the execution ID, pipeline ID, and status.

        Exceptions are allowed to propagate to the event publisher so they
        can be reported to the caller for visibility and recovery.

        Args:
            event: The PipelineExecuted event to record

        Raises:
            Any exception from the change repository is propagated to allow
            the event publisher to include it in the failures list.
        """
        change_id = self.change_repo.record_change(
            entity_id=event.execution_id,
            entity_type="pipeline_execution",
            operation=ChangeOperation.CREATE,
            new_state={
                "execution_id": event.execution_id,
                "pipeline_id": event.pipeline_id,
                "status": event.status,
            },
            change_reason="Pipeline execution completed",
        )
        logger.debug(
            f"Recorded pipeline execution: execution_id={event.execution_id}, "
            f"pipeline_id={event.pipeline_id}, status={event.status}, "
            f"change_event_id={change_id}"
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
        logging and error propagation.

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
        change_id = self.change_repo.record_change(
            entity_id=entity_id,
            entity_type=entity_type,
            operation=operation,
            new_state=new_state or {},
            previous_state=previous_state,
            change_reason=change_reason,
        )
        logger.debug(
            f"Recorded ontology change: entity_id={entity_id}, "
            f"entity_type={entity_type}, operation={operation}, "
            f"change_event_id={change_id}"
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
                "parent_id": event.new_parent_id,
            },
            previous_state={
                "parent_id": event.old_parent_id,
            },
            change_reason=f"Class moved from parent {event.old_parent_id} to {event.new_parent_id}",
        )

    def on_property_definition_updated(
        self, event: PropertyDefinitionUpdated
    ) -> None:
        """Handle PropertyDefinitionUpdated events."""
        self._record(
            entity_id=event.property_id,
            entity_type="property_definition",
            operation=ChangeOperation.UPDATE,
            new_state={
                "title": event.title,
                "description": event.description,
            },
            change_reason="Property definition updated: title, description",
        )

    def on_concept_scheme_updated(self, event: ConceptSchemeUpdated) -> None:
        """Handle ConceptSchemeUpdated events."""
        self._record(
            entity_id=event.concept_scheme_id,
            entity_type="concept_scheme",
            operation=ChangeOperation.UPDATE,
            new_state={
                "title": event.title,
            },
            change_reason="Concept scheme updated: title",
        )

    # --- DELETE Pattern Handlers ---

    def on_taxonomy_deleted(self, event: TaxonomyDeleted) -> None:
        """Handle TaxonomyDeleted events."""
        self._record(
            entity_id=event.taxonomy_id,
            entity_type="taxonomy",
            operation=ChangeOperation.DELETE,
            previous_state={"taxonomy_id": event.taxonomy_id, "title": event.title},
            change_reason="Taxonomy deleted",
        )

    def on_scheme_deleted(self, event: SchemeDeleted) -> None:
        """Handle SchemeDeleted events."""
        self._record(
            entity_id=event.concept_scheme_id,
            entity_type="concept_scheme",
            operation=ChangeOperation.DELETE,
            previous_state={
                "concept_scheme_id": event.concept_scheme_id,
                "title": event.title,
                "taxonomy_id": event.taxonomy_id,
            },
            change_reason="Concept scheme deleted",
        )

    def on_class_deleted(self, event: ClassDeleted) -> None:
        """Handle ClassDeleted events."""
        self._record(
            entity_id=event.class_id,
            entity_type="class",
            operation=ChangeOperation.DELETE,
            previous_state={"class_id": event.class_id, "title": event.title},
            change_reason="Class deleted",
        )

    def on_relationship_deleted(self, event: RelationshipDeleted) -> None:
        """Handle RelationshipDeleted events."""
        self._record(
            entity_id=event.relationship_id,
            entity_type="relationship",
            operation=ChangeOperation.DELETE,
            previous_state={
                "relationship_id": event.relationship_id,
                "source_id": event.source_id,
                "target_id": event.target_id,
                "property_definition_id": event.property_definition_id,
            },
            change_reason="Relationship deleted",
        )

    def on_property_definition_deleted(
        self, event: PropertyDefinitionDeleted
    ) -> None:
        """Handle PropertyDefinitionDeleted events."""
        self._record(
            entity_id=event.property_id,
            entity_type="property_definition",
            operation=ChangeOperation.DELETE,
            previous_state={
                "property_id": event.property_id,
                "identifier": event.identifier,
                "title": event.title,
            },
            change_reason="Property definition deleted",
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
            previous_state={
                "individual_id": event.individual_id,
                "title": event.title,
            },
            change_reason="Individual deleted",
        )

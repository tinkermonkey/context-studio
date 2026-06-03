"""
RevertService for the Versioning context.

Walks change_events for a given batch_run_id in reverse and applies the inverse of each event.
Already-reverted events are skipped (idempotent). Emits new change_events tagged with
the originating batch_run_id for auditability.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from domain.versioning.value_objects import ChangeOperation

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.versioning.ports import ChangeRepository

_logger = logging.getLogger(__name__)


class RevertService:
    """
    Reverts the effects of a batch run by inverting change events.

    Given a batch_run_id, walks change_events for that batch in reverse and applies
    the inverse of each event. Already-reverted events are skipped (idempotent).
    Emits new change_events tagged with the originating batch_run_id for auditability.
    """

    def __init__(
        self, change_repo: ChangeRepository, ontology_repo: OntologyRepository
    ) -> None:
        """
        Initialize the RevertService.

        Args:
            change_repo: Repository for persisting and retrieving change events
            ontology_repo: Repository for ontology entities
        """
        self._change_repo = change_repo
        self._ontology_repo = ontology_repo

    def revert(self, batch_run_id: str) -> int:
        """
        Revert all changes made by a specific batch run.

        Walks the change_events for the given batch_run_id in reverse chronological order
        and applies the inverse of each operation. Already-reverted events are skipped.

        Args:
            batch_run_id: ID of the batch run to revert

        Returns:
            Count of events successfully reverted

        Raises:
            ValueError: If batch_run_id is empty
        """
        if not batch_run_id:
            raise ValueError("batch_run_id is required for revert")

        # Filter by batch_run_id at query level to avoid memory overhead
        events_result = self._change_repo.get_changes(
            batch_run_id=batch_run_id, limit=None
        )
        events = list(events_result.events)

        if not events:
            _logger.info(f"No events found for batch run {batch_run_id}")
            return 0

        reverted_count = 0
        for event in reversed(events):
            if self._should_skip_revert(event, events):
                continue

            if self._apply_inverse(event, batch_run_id):
                reverted_count += 1

        _logger.info(f"Reverted {reverted_count} events for batch run {batch_run_id}")
        return reverted_count

    def _should_skip_revert(self, event, all_events) -> bool:
        """Check if an event should be skipped during revert (already reverted)."""
        # Skip if this event is itself a revert event (has _reverted_ in change_reason)
        if "_reverted_" in (event.change_reason or ""):
            return True

        # Check if a corresponding revert event already exists for this original event
        # by looking for a revert event for the same entity with the inverse operation
        inverse_op = self._inverse_operation(event.operation)
        normalized_entity_type = self._normalize_entity_type(event.entity_type)

        for existing_event in all_events:
            normalized_existing_type = self._normalize_entity_type(
                existing_event.entity_type
            )
            if (
                existing_event.entity_id == event.entity_id
                and existing_event.operation == inverse_op
                and normalized_existing_type == normalized_entity_type
                and "_reverted_" in (existing_event.change_reason or "")
            ):
                return True

        return False

    def _apply_inverse(self, event, batch_run_id: str) -> bool:
        """
        Apply the inverse operation for a change event.

        Returns:
            True if applied, False if skipped due to missing entity
        """
        entity_id = event.entity_id
        entity_type = self._normalize_entity_type(event.entity_type)
        operation = event.operation

        try:
            operation_applied = False
            if operation == ChangeOperation.CREATE:
                operation_applied = self._inverse_create(entity_id, entity_type)
            elif operation == ChangeOperation.UPDATE:
                operation_applied = self._inverse_update(
                    entity_id, entity_type, event.previous_state
                )
            elif operation == ChangeOperation.DELETE:
                operation_applied = self._inverse_delete(
                    entity_id, entity_type, event.new_state
                )

            if operation_applied:
                self._change_repo.record_change(
                    entity_id=entity_id,
                    entity_type=event.entity_type,
                    operation=self._inverse_operation(operation),
                    new_state={},
                    previous_state=event.new_state,
                    change_reason=f"_reverted_from_{batch_run_id}",
                    batch_run_id=batch_run_id,
                )
            return operation_applied
        except Exception as exc:
            _logger.error(
                f"Failed to revert event {event.id} for entity {entity_id}: {exc}",
                exc_info=exc,
            )
            raise

    def _inverse_create(self, entity_id: str, entity_type: str) -> bool:
        """
        Inverse of CREATE: delete the entity.

        Returns:
            True if the entity was found and deleted, False if entity no longer exists
        """
        if entity_type == "taxonomy":
            tax = self._ontology_repo.get_taxonomy(entity_id)
            if tax:
                self._ontology_repo.delete_taxonomy(entity_id)
                return True
        elif entity_type == "concept_scheme":
            scheme = self._ontology_repo.get_concept_scheme(entity_id)
            if scheme:
                self._ontology_repo.delete_concept_scheme(entity_id)
                return True
        elif entity_type == "class":
            cls = self._ontology_repo.get_class(entity_id)
            if cls:
                self._ontology_repo.delete_class(entity_id)
                return True
        elif entity_type == "individual":
            ind = self._ontology_repo.get_individual(entity_id)
            if ind:
                self._ontology_repo.delete_individual(entity_id)
                return True
        elif entity_type == "relationship":
            rel = self._ontology_repo.get_relationship(entity_id)
            if rel:
                self._ontology_repo.delete_relationship(entity_id)
                return True
        elif entity_type == "property_definition":
            prop = self._ontology_repo.get_property_definition(entity_id)
            if prop:
                self._ontology_repo.delete_property_definition(entity_id)
                return True
        else:
            raise ValueError(f"Unknown entity type for create revert: {entity_type}")
        return False

    def _inverse_update(
        self, entity_id: str, entity_type: str, previous_state: Optional[dict]
    ) -> bool:
        """
        Inverse of UPDATE: restore previous state.

        Returns:
            True if the entity was found and restored, False if entity no longer exists
        """
        if not previous_state:
            raise ValueError(
                f"Cannot revert UPDATE for {entity_type} {entity_id}: "
                "previous_state is missing from change event"
            )

        if entity_type == "taxonomy":
            tax = self._ontology_repo.get_taxonomy(entity_id)
            if tax:
                self._restore_entity_state(tax, previous_state)
                self._ontology_repo.save_taxonomy(tax)
                return True
        elif entity_type == "concept_scheme":
            scheme = self._ontology_repo.get_concept_scheme(entity_id)
            if scheme:
                self._restore_entity_state(scheme, previous_state)
                self._ontology_repo.save_concept_scheme(scheme)
                return True
        elif entity_type == "class":
            cls = self._ontology_repo.get_class(entity_id)
            if cls:
                self._restore_entity_state(cls, previous_state)
                self._ontology_repo.save_class(cls)
                return True
        elif entity_type == "individual":
            ind = self._ontology_repo.get_individual(entity_id)
            if ind:
                self._restore_entity_state(ind, previous_state)
                self._ontology_repo.save_individual(ind)
                return True
        elif entity_type == "relationship":
            rel = self._ontology_repo.get_relationship(entity_id)
            if rel:
                self._restore_entity_state(rel, previous_state)
                self._ontology_repo.save_relationship(rel)
                return True
        elif entity_type == "property_definition":
            prop = self._ontology_repo.get_property_definition(entity_id)
            if prop:
                self._restore_entity_state(prop, previous_state)
                self._ontology_repo.save_property_definition(prop)
                return True
        else:
            raise ValueError(f"Unknown entity type for update revert: {entity_type}")
        return False

    def _inverse_delete(
        self, entity_id: str, entity_type: str, new_state: dict
    ) -> bool:
        """
        Inverse of DELETE: recreate the entity from new_state.

        Returns:
            True if the entity was successfully recreated
        """
        if not new_state:
            raise ValueError(
                f"Cannot revert DELETE for {entity_type} {entity_id}: "
                "new_state is missing from change event"
            )

        from domain.ontology.entities import (
            Class,
            ConceptScheme,
            Individual,
            PropertyDefinition,
            Relationship,
            Taxonomy,
        )
        from domain.ontology.value_objects import Status

        try:
            if entity_type == "taxonomy":
                tax = Taxonomy(
                    id=new_state.get("id", entity_id),
                    title=new_state.get("title", ""),
                    identifier=new_state.get("identifier"),
                    description=new_state.get("description"),
                    color=new_state.get("color"),
                    status=Status(new_state.get("status", "draft")),
                )
                self._ontology_repo.save_taxonomy(tax)
            elif entity_type == "concept_scheme":
                scheme = ConceptScheme(
                    id=new_state.get("id", entity_id),
                    taxonomy_id=new_state.get("taxonomy_id", ""),
                    title=new_state.get("title", ""),
                    identifier=new_state.get("identifier"),
                    description=new_state.get("description"),
                    status=Status(new_state.get("status", "draft")),
                )
                self._ontology_repo.save_concept_scheme(scheme)
            elif entity_type == "class":
                cls = Class(
                    id=new_state.get("id", entity_id),
                    taxonomy_id=new_state.get("taxonomy_id", ""),
                    concept_scheme_id=new_state.get("concept_scheme_id", ""),
                    title=new_state.get("title", ""),
                    description=new_state.get("description"),
                    status=Status(new_state.get("status", "draft")),
                )
                self._ontology_repo.save_class(cls)
            elif entity_type == "individual":
                ind = Individual(
                    id=new_state.get("id", entity_id),
                    class_ids=new_state.get("class_ids", []),
                    title=new_state.get("title", ""),
                    status=Status(new_state.get("status", "draft")),
                )
                self._ontology_repo.save_individual(ind)
            elif entity_type == "relationship":
                rel = Relationship(
                    id=new_state.get("id", entity_id),
                    source_id=new_state.get("source_id", ""),
                    target_id=new_state.get("target_id", ""),
                    property_definition_id=new_state.get("property_definition_id", ""),
                )
                self._ontology_repo.save_relationship(rel)
            elif entity_type == "property_definition":
                prop = PropertyDefinition(
                    id=new_state.get("id", entity_id),
                    identifier=new_state.get("identifier", ""),
                    title=new_state.get("title", ""),
                    description=new_state.get("description"),
                    status=Status(new_state.get("status", "draft")),
                )
                self._ontology_repo.save_property_definition(prop)
            else:
                raise ValueError(
                    f"Unknown entity type for delete revert: {entity_type}"
                )
            return True
        except Exception as exc:
            _logger.error(
                f"Failed to recreate {entity_type} {entity_id}: {exc}", exc_info=exc
            )
            raise

    def _restore_entity_state(self, entity, state: dict) -> None:
        """Restore an entity's fields from a previous state dict."""
        for key, value in state.items():
            if not hasattr(entity, key):
                raise ValueError(f"Entity {type(entity).__name__} has no field {key}")
            try:
                setattr(entity, key, value)
            except Exception as exc:
                entity_type = type(entity).__name__
                raise ValueError(
                    f"Could not restore field {key} on {entity_type}: {exc}"
                ) from exc

    @staticmethod
    def _normalize_entity_type(entity_type: str) -> str:
        """Normalize entity type to lowercase snake_case for comparison."""
        if not entity_type:
            return entity_type
        normalized = entity_type.lower()
        normalized = normalized.replace("conceptscheme", "concept_scheme")
        normalized = normalized.replace("propertydefinition", "property_definition")
        return normalized

    @staticmethod
    def _inverse_operation(operation: ChangeOperation) -> ChangeOperation:
        """Return the inverse operation."""
        if operation == ChangeOperation.CREATE:
            return ChangeOperation.DELETE
        elif operation == ChangeOperation.DELETE:
            return ChangeOperation.CREATE
        else:
            return ChangeOperation.UPDATE

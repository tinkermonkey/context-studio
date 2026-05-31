"""
RevertService for the Versioning context.

Walks change_events for a given run_id in reverse and applies the inverse of each event.
Already-reverted events are skipped (idempotent). Emits new change_events tagged with
the originating run_id for auditability.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4
from typing import TYPE_CHECKING, Optional

from domain.versioning.value_objects import ChangeOperation

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.versioning.ports import ChangeRepository

_logger = logging.getLogger(__name__)


class RevertService:
    """
    Reverts the effects of a pipeline run by inverting change events.

    Given a run_id, walks change_events for that run in reverse and applies
    the inverse of each event. Already-reverted events are skipped (idempotent).
    Emits new change_events tagged with the originating run_id for auditability.
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

    def revert(self, run_id: str) -> int:
        """
        Revert all changes made by a specific pipeline run.

        Walks the change_events for the given run_id in reverse chronological order
        and applies the inverse of each operation. Already-reverted events are skipped.

        Args:
            run_id: ID of the pipeline run to revert

        Returns:
            Count of events successfully reverted

        Raises:
            ValueError: If run_id is empty
        """
        if not run_id:
            raise ValueError("run_id is required for revert")

        history = self._change_repo.get_changes(limit=None)
        events = [e for e in history.events if e.batch_run_id == run_id]

        if not events:
            _logger.info(f"No events found for run {run_id}")
            return 0

        reverted_count = 0
        for event in reversed(events):
            if self._should_skip_revert(event):
                continue

            self._apply_inverse(event, run_id)
            reverted_count += 1

        _logger.info(f"Reverted {reverted_count} events for run {run_id}")
        return reverted_count

    def _should_skip_revert(self, event) -> bool:
        """Check if an event should be skipped during revert (already reverted)."""
        # Skip if this event is itself a revert event (has _reverted_ in change_reason)
        if "_reverted_" in (event.change_reason or ""):
            return True
        return False

    def _apply_inverse(self, event, originating_run_id: str) -> None:
        """Apply the inverse operation for a change event."""
        entity_id = event.entity_id
        entity_type = event.entity_type
        operation = event.operation

        try:
            if operation == ChangeOperation.CREATE:
                self._inverse_create(entity_id, entity_type)
            elif operation == ChangeOperation.UPDATE:
                self._inverse_update(entity_id, entity_type, event.previous_state)
            elif operation == ChangeOperation.DELETE:
                self._inverse_delete(entity_id, entity_type, event.new_state)

            self._change_repo.record_change(
                entity_id=entity_id,
                entity_type=entity_type,
                operation=self._inverse_operation(operation),
                new_state={},
                previous_state=event.new_state,
                change_reason=f"_reverted_from_{originating_run_id}",
                batch_run_id=originating_run_id,
            )
        except Exception as exc:
            _logger.error(
                f"Failed to revert event {event.id} for entity {entity_id}: {exc}",
                exc_info=exc,
            )
            raise

    def _inverse_create(self, entity_id: str, entity_type: str) -> None:
        """Inverse of CREATE: delete the entity."""
        if entity_type == "Class":
            cls = self._ontology_repo.get_class(entity_id)
            if cls:
                self._ontology_repo.delete_class(entity_id)
        elif entity_type == "Individual":
            ind = self._ontology_repo.get_individual(entity_id)
            if ind:
                self._ontology_repo.delete_individual(entity_id)
        elif entity_type == "Relationship":
            rel = self._ontology_repo.get_relationship(entity_id)
            if rel:
                self._ontology_repo.delete_relationship(entity_id)
        elif entity_type == "PropertyDefinition":
            prop = self._ontology_repo.get_property_definition(entity_id)
            if prop:
                self._ontology_repo.delete_property_definition(entity_id)

    def _inverse_update(
        self, entity_id: str, entity_type: str, previous_state: Optional[dict]
    ) -> None:
        """Inverse of UPDATE: restore previous state."""
        if not previous_state:
            return

        if entity_type == "Class":
            cls = self._ontology_repo.get_class(entity_id)
            if cls:
                self._restore_entity_state(cls, previous_state)
                self._ontology_repo.save_class(cls)
        elif entity_type == "Individual":
            ind = self._ontology_repo.get_individual(entity_id)
            if ind:
                self._restore_entity_state(ind, previous_state)
                self._ontology_repo.save_individual(ind)
        elif entity_type == "PropertyDefinition":
            prop = self._ontology_repo.get_property_definition(entity_id)
            if prop:
                self._restore_entity_state(prop, previous_state)
                self._ontology_repo.save_property_definition(prop)

    def _inverse_delete(
        self, entity_id: str, entity_type: str, new_state: dict
    ) -> None:
        """Inverse of DELETE: recreate the entity from new_state."""
        if not new_state:
            return

        from domain.ontology.entities import Class, Individual, PropertyDefinition, Relationship
        from domain.ontology.value_objects import Status

        try:
            if entity_type == "Class":
                cls = Class(
                    id=new_state.get("id", entity_id),
                    taxonomy_id=new_state.get("taxonomy_id", ""),
                    concept_scheme_id=new_state.get("concept_scheme_id", ""),
                    title=new_state.get("title", ""),
                    description=new_state.get("description"),
                    status=Status(new_state.get("status", "draft")),
                )
                self._ontology_repo.save_class(cls)
            elif entity_type == "Individual":
                ind = Individual(
                    id=new_state.get("id", entity_id),
                    class_ids=new_state.get("class_ids", []),
                    title=new_state.get("title", ""),
                    status=Status(new_state.get("status", "draft")),
                )
                self._ontology_repo.save_individual(ind)
            elif entity_type == "Relationship":
                rel = Relationship(
                    id=new_state.get("id", entity_id),
                    source_id=new_state.get("source_id", ""),
                    target_id=new_state.get("target_id", ""),
                    property_definition_id=new_state.get("property_definition_id", ""),
                )
                self._ontology_repo.save_relationship(rel)
            elif entity_type == "PropertyDefinition":
                prop = PropertyDefinition(
                    id=new_state.get("id", entity_id),
                    identifier=new_state.get("identifier", ""),
                    title=new_state.get("title", ""),
                    description=new_state.get("description"),
                    status=Status(new_state.get("status", "draft")),
                )
                self._ontology_repo.save_property_definition(prop)
        except Exception as exc:
            _logger.error(f"Failed to recreate {entity_type} {entity_id}: {exc}", exc_info=exc)
            raise

    def _restore_entity_state(self, entity, state: dict) -> None:
        """Restore an entity's fields from a previous state dict."""
        for key, value in state.items():
            if hasattr(entity, key):
                try:
                    setattr(entity, key, value)
                except Exception as exc:
                    _logger.warning(f"Could not restore field {key}: {exc}")

    @staticmethod
    def _inverse_operation(operation: ChangeOperation) -> ChangeOperation:
        """Return the inverse operation."""
        if operation == ChangeOperation.CREATE:
            return ChangeOperation.DELETE
        elif operation == ChangeOperation.DELETE:
            return ChangeOperation.CREATE
        else:
            return ChangeOperation.UPDATE

"""
RevertService for the Versioning context.

Walks change_events for a given batch_run_id in reverse and applies the inverse of each event.
Already-reverted events are skipped (idempotent). Emits new change_events tagged with
the originating batch_run_id for auditability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from domain.ontology.value_objects import ExternalReference
from domain.versioning.exceptions import RevertConflictError
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

    def __init__(self, change_repo: ChangeRepository, ontology_repo: OntologyRepository) -> None:
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
        result = self.revert_with_summary(batch_run_id)
        return result.events_reverted

    def revert_with_summary(self, batch_run_id: str) -> RevertResult:
        """
        Revert all changes made by a specific batch run and return detailed summary.

        Walks the change_events for the given batch_run_id in reverse chronological order
        and applies the inverse of each operation. Already-reverted events are skipped.

        Args:
            batch_run_id: ID of the batch run to revert

        Returns:
            RevertResult with event count and detailed breakdown by entity type

        Raises:
            ValueError: If batch_run_id is empty
            RevertConflictError: If entities outside the run depend on entities it
                created; nothing is changed
        """
        if not batch_run_id:
            raise ValueError("batch_run_id is required for revert")

        # Filter by batch_run_id at query level to avoid memory overhead
        events_result = self._change_repo.get_changes(batch_run_id=batch_run_id, limit=None)
        events = list(events_result.events)

        if not events:
            _logger.info(f"No events found for batch run {batch_run_id}")
            return RevertResult(run_id=batch_run_id, events_reverted=0)

        pending = [event for event in events if not self._should_skip_revert(event, events)]
        self._check_no_outside_dependents(batch_run_id, pending)

        reverted_count = 0
        summary = {
            "classes_deleted": 0,
            "individuals_deleted": 0,
            "relationships_deleted": 0,
            "properties_deleted": 0,
            "taxonomies_deleted": 0,
            "concept_schemes_deleted": 0,
            "entities_restored": 0,
        }

        # get_changes returns newest first, which is the order to undo in: a
        # relationship is removed before the property it uses, and chained
        # updates unwind back to the oldest previous state.
        for event in pending:
            try:
                if self._apply_inverse(event, batch_run_id):
                    reverted_count += 1
                    self._update_summary(event, summary)
            except Exception as exc:
                _logger.error(
                    f"Failed to revert event {event.id} for entity {event.entity_id}. "
                    f"Partially reverted {reverted_count} events before failure.",
                    exc_info=exc,
                )
                raise

        _logger.info(f"Reverted {reverted_count} events for batch run {batch_run_id}")
        return RevertResult(
            run_id=batch_run_id,
            events_reverted=reverted_count,
            classes_deleted=summary["classes_deleted"],
            individuals_deleted=summary["individuals_deleted"],
            relationships_deleted=summary["relationships_deleted"],
            properties_deleted=summary["properties_deleted"],
            taxonomies_deleted=summary["taxonomies_deleted"],
            concept_schemes_deleted=summary["concept_schemes_deleted"],
            entities_restored=summary["entities_restored"],
        )

    def _should_skip_revert(self, event, all_events) -> bool:
        """
        Check if an event should be skipped during revert.

        Revert events themselves are skipped. An original event is skipped when a
        revert event names it (``_reverted_from_<run>:<event id>``). Older revert
        events carry no event id; one of those only covers original events recorded
        before it, so re-applying a run after a revert (which records new events on
        the same entities) and reverting again still undoes the new events.
        """
        if self._REVERT_MARKER in (event.change_reason or ""):
            return True

        inverse_op = self._inverse_operation(event.operation)
        normalized_entity_type = self._normalize_entity_type(event.entity_type)

        for existing_event in all_events:
            reason = existing_event.change_reason or ""
            if (
                self._REVERT_MARKER not in reason
                or existing_event.entity_id != event.entity_id
                or existing_event.operation != inverse_op
                or self._normalize_entity_type(existing_event.entity_type)
                != normalized_entity_type
            ):
                continue
            reverted_event_id = self._reverted_event_id(reason)
            if reverted_event_id is not None:
                if reverted_event_id == event.id:
                    return True
            elif existing_event.timestamp >= event.timestamp:
                return True

        return False

    def _check_no_outside_dependents(self, batch_run_id: str, pending: list) -> None:
        """
        Refuse the revert if it would delete entities that others depend on.

        Undoing a CREATE deletes the entity, and the database's foreign keys then
        CASCADE, SET NULL or RESTRICT every row that references it. Rows created by
        this same run are fine (the revert removes them too). Anything else, such as
        individuals another run typed into a class this run created, would be
        silently deleted or detached, so nothing is changed and the conflict is raised.

        Raises:
            RevertConflictError: listing each dependent outside the run
        """
        deleted_ids = {
            event.entity_id for event in pending if event.operation == ChangeOperation.CREATE
        }
        if not deleted_ids:
            return
        blocking = [
            (ref.dependent_kind, ref.dependent_id, ref.referenced_id)
            for ref in self._ontology_repo.find_references(sorted(deleted_ids))
            if ref.dependent_id not in deleted_ids
        ]
        if blocking:
            raise RevertConflictError(batch_run_id, blocking)

    _REVERT_MARKER = "_reverted_"

    @staticmethod
    def _revert_reason(batch_run_id: str, event_id: str) -> str:
        """change_reason for the inverse of ``event_id`` recorded by a revert of a run."""
        return f"_reverted_from_{batch_run_id}:{event_id}"

    @staticmethod
    def _reverted_event_id(change_reason: str) -> str | None:
        """The original event id a revert's change_reason names, or None for older reverts."""
        _, sep, event_id = change_reason.rpartition(":")
        return event_id if sep and event_id else None

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
                    entity_id, entity_type, self._deleted_state(event)
                )

            if operation_applied:
                self._change_repo.record_change(
                    entity_id=entity_id,
                    entity_type=event.entity_type,
                    operation=self._inverse_operation(operation),
                    new_state={},
                    previous_state=(
                        self._deleted_state(event)
                        if operation == ChangeOperation.DELETE
                        else event.new_state
                    ),
                    change_reason=self._revert_reason(batch_run_id, event.id),
                    batch_run_id=batch_run_id,
                )
            return operation_applied
        except Exception as exc:
            _logger.error(
                f"Failed to revert event {event.id} for entity {entity_id}: {exc}",
                exc_info=exc,
            )
            raise

    @staticmethod
    def _deleted_state(event) -> dict:
        """
        Return the snapshot of a deleted entity.

        The ChangeEventRecorder stores a deletion's snapshot in ``previous_state``
        (``new_state`` is empty); older or hand-recorded events carry it in
        ``new_state``. Note the recorder's snapshots are minimal (e.g. a relationship
        keeps only its id, endpoints and property definition), so restores are lossy.
        """
        return event.new_state or event.previous_state or {}

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

    def _inverse_delete(self, entity_id: str, entity_type: str, new_state: dict) -> bool:
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
                raise ValueError(f"Unknown entity type for delete revert: {entity_type}")
            return True
        except Exception as exc:
            _logger.error(f"Failed to recreate {entity_type} {entity_id}: {exc}", exc_info=exc)
            raise

    def _restore_entity_state(self, entity, state: dict) -> None:
        """Restore an entity's fields from a previous state dict."""
        for key, value in state.items():
            if not hasattr(entity, key):
                raise ValueError(f"Entity {type(entity).__name__} has no field {key}")
            if key == "external_references":
                # Change events carry references as JSON dicts (see ClassUpdated).
                value = [ExternalReference.from_dict(ref) for ref in value or []]
            try:
                setattr(entity, key, value)
            except Exception as exc:
                entity_type = type(entity).__name__
                raise ValueError(f"Could not restore field {key} on {entity_type}: {exc}") from exc

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

    @staticmethod
    def _update_summary(event, summary: dict) -> None:
        """Update summary counts based on the event being reverted."""
        entity_type = RevertService._normalize_entity_type(event.entity_type)
        operation = event.operation

        if operation == ChangeOperation.CREATE:
            if entity_type == "taxonomy":
                summary["taxonomies_deleted"] += 1
            elif entity_type == "concept_scheme":
                summary["concept_schemes_deleted"] += 1
            elif entity_type == "class":
                summary["classes_deleted"] += 1
            elif entity_type == "individual":
                summary["individuals_deleted"] += 1
            elif entity_type == "relationship":
                summary["relationships_deleted"] += 1
            elif entity_type == "property_definition":
                summary["properties_deleted"] += 1
        elif operation == ChangeOperation.DELETE:
            summary["entities_restored"] += 1
        elif operation == ChangeOperation.UPDATE:
            summary["entities_restored"] += 1


@dataclass
class RevertResult:
    """Result of a revert operation with detailed summary."""

    run_id: str
    events_reverted: int
    classes_deleted: int = 0
    individuals_deleted: int = 0
    relationships_deleted: int = 0
    properties_deleted: int = 0
    taxonomies_deleted: int = 0
    concept_schemes_deleted: int = 0
    entities_restored: int = 0

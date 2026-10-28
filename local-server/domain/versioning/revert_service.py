"""
RevertService for the Versioning context.

Walks change_events for a given batch_run_id in reverse and applies the inverse of each event.
Already-reverted events are skipped (idempotent). Emits new change_events tagged with
the originating batch_run_id for auditability.
"""

from __future__ import annotations

import logging
from contextlib import nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from domain.ontology.events import GraphInvalidated
from domain.ontology.snapshots import entity_field_names, entity_from_snapshot, entity_snapshot
from domain.ontology.value_objects import DataType, ExternalReference
from domain.versioning.exceptions import RevertConflictError
from domain.versioning.value_objects import ChangeOperation

if TYPE_CHECKING:
    from domain.ontology.ports import (
        IndividualVectorIndex,
        OntologyRepository,
        SchemaVectorIndex,
    )
    from domain.ports import EventPublisher, TransactionScope
    from domain.versioning.ports import ChangeRepository

_logger = logging.getLogger(__name__)


def _mentions(values, entity_id: str) -> bool:
    """Whether any of these field values is, or is a list containing, the entity id."""
    return any(
        value == entity_id or (isinstance(value, list) and entity_id in value) for value in values
    )


class RevertService:
    """
    Reverts the effects of a batch run by inverting change events.

    Given a batch_run_id, walks change_events for that batch in reverse and applies
    the inverse of each event. Already-reverted events are skipped (idempotent), as
    are events that only record the run's output (an extraction run's
    extraction_result). Emits new change_events tagged with the originating
    batch_run_id for auditability, and invalidates the graph caches when anything
    changed.
    """

    def __init__(
        self,
        change_repo: ChangeRepository,
        ontology_repo: OntologyRepository,
        schema_index: SchemaVectorIndex | None = None,
        individual_index: IndividualVectorIndex | None = None,
        event_publisher: EventPublisher | None = None,
        transaction_scope: TransactionScope | None = None,
    ) -> None:
        """
        Initialize the RevertService.

        Args:
            change_repo: Repository for persisting and retrieving change events
            ontology_repo: Repository for ontology entities
            schema_index: Optional schema vector index, re-synced for every class,
                property definition and individual the revert restores or modifies
            individual_index: Optional recognition index, re-synced for every
                individual the revert restores or modifies and cleared for every
                individual it deletes
            event_publisher: Optional publisher; GraphInvalidated is published for
                every taxonomy whenever the revert changes anything
            transaction_scope: Makes the revert atomic: every inverse and the
                change events recording them commit together, or none do. Both
                repositories must take part in it. Without one, a revert that
                fails partway keeps what it already undid.
        """
        self._change_repo = change_repo
        self._ontology_repo = ontology_repo
        self._schema_index = schema_index
        self._individual_index = individual_index
        self._event_publisher = event_publisher
        self._transaction_scope = transaction_scope

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
            ValueError: If batch_run_id is empty, or an event can't be undone; nothing
                is changed
            RevertConflictError: If entities outside the run depend on entities it
                created; nothing is changed
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
            ValueError: If batch_run_id is empty, or an event can't be undone (no
                previous state, an unknown field, no snapshot); nothing is changed
            RevertConflictError: If entities outside the run depend on entities it
                created; nothing is changed
        """
        if not batch_run_id:
            raise ValueError("batch_run_id is required for revert")

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
        touched: dict[str, str] = {}
        pending: list = []
        committed = False

        scope = self._transaction_scope.atomic() if self._transaction_scope else nullcontext()
        try:
            with scope:
                # Filter by batch_run_id at query level to avoid memory overhead
                events_result = self._change_repo.get_changes(batch_run_id=batch_run_id, limit=None)
                events = list(events_result.events)

                if not events:
                    _logger.info(f"No events found for batch run {batch_run_id}")
                    return RevertResult(run_id=batch_run_id, events_reverted=0)

                pending = [
                    event
                    for event in events
                    if self._normalize_entity_type(event.entity_type) not in self._RECORD_ONLY_TYPES
                    and not self._should_skip_revert(event, events)
                ]
                self._check_restorable(batch_run_id, pending)
                self._check_no_outside_dependents(batch_run_id, pending)

                # get_changes returns newest first, which is the order to undo in: a
                # relationship is removed before the property it uses, and chained
                # updates unwind back to the oldest previous state.
                for event in pending:
                    try:
                        if self._apply_inverse(event, batch_run_id):
                            reverted_count += 1
                            self._update_summary(event, summary)
                            touched[event.entity_id] = self._normalize_entity_type(
                                event.entity_type
                            )
                    except Exception as exc:
                        _logger.error(
                            f"Failed to revert event {event.id} for entity {event.entity_id} "
                            f"after undoing {reverted_count} events"
                            + (
                                "; the revert is rolled back."
                                if self._transaction_scope
                                else "; those stay undone."
                            ),
                            exc_info=exc,
                        )
                        raise
            committed = True
        finally:
            # Index writes and graph invalidation stay out of the transaction, after
            # the commit. In a transaction scope a failed revert changed nothing, so
            # there is nothing to follow; without one each inverse is committed as it
            # is applied, so they follow even a revert that failed partway.
            if committed or self._transaction_scope is None:
                for entity_id, entity_type in touched.items():
                    self._sync_indexes(entity_id, entity_type)
                if reverted_count:
                    self._invalidate_graphs(pending)

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
                or self._normalize_entity_type(existing_event.entity_type) != normalized_entity_type
            ):
                continue
            reverted_event_id = self._reverted_event_id(reason)
            if reverted_event_id is not None:
                if reverted_event_id == event.id:
                    return True
            elif existing_event.timestamp >= event.timestamp:
                return True

        return False

    def _check_restorable(self, batch_run_id: str, pending: list) -> None:
        """
        Refuse the revert, before changing anything, if an event can't be undone.

        Every event must name a known ontology entity type, an update needs its
        previous state, naming only fields of its entity, and a delete needs a
        snapshot complete enough to rebuild the entity. Checking up front keeps a
        bad event from stopping the revert partway through the run.

        Raises:
            ValueError: listing each event that can't be undone
        """
        problems = []
        for event in pending:
            entity_type = self._normalize_entity_type(event.entity_type)
            label = f"{entity_type} {event.entity_id} (event {event.id})"
            try:
                field_names = entity_field_names(entity_type)
            except ValueError:
                problems.append(f"{label}: unknown entity type")
                continue
            if event.operation == ChangeOperation.UPDATE:
                if not event.previous_state:
                    problems.append(f"{label}: no previous state")
                    continue
                unknown = sorted(set(event.previous_state) - field_names)
                if unknown:
                    problems.append(f"{label}: unknown fields {unknown}")
            elif event.operation == ChangeOperation.DELETE:
                snapshot = self._deleted_state(event)
                if not snapshot:
                    problems.append(f"{label}: no snapshot of the deleted entity")
                    continue
                try:
                    entity_from_snapshot(entity_type, snapshot, event.entity_id)
                except ValueError as exc:
                    problems.append(f"{label}: {exc}")
        if problems:
            raise ValueError(
                f"Cannot revert batch run {batch_run_id}; nothing was changed. "
                + "; ".join(problems)
            )

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
        outside: dict[str, list] = {}
        for ref in self._ontology_repo.find_references(sorted(deleted_ids)):
            if ref.dependent_id not in deleted_ids:
                outside.setdefault(ref.referenced_id, []).append(ref)

        # Walk the events in the order their inverses run (newest first). When a
        # create is reached its entity gets deleted, so by then nothing may point
        # at it: neither an outside dependent that the updates undone so far
        # haven't detached, nor anything the revert itself has put back (fields
        # restored by an undone update, an entity recreated from its snapshot).
        restored: dict[str, dict] = {}  # entity -> fields the undone updates put back
        restored_type: dict[str, str] = {}
        gone: set[str] = set()  # run-created entities deleted so far
        blocking: list[tuple[str, str, str]] = []
        for event in pending:
            entity_type = self._normalize_entity_type(event.entity_type)
            if event.operation == ChangeOperation.UPDATE and event.previous_state:
                restored.setdefault(event.entity_id, {}).update(event.previous_state)
                restored_type[event.entity_id] = entity_type
            elif event.operation == ChangeOperation.DELETE:
                snapshot = dict(self._deleted_state(event))
                snapshot.pop("id", None)
                if entity_type == "class":
                    snapshot.pop("taxonomy_id", None)  # follows the scheme when restored
                restored[event.entity_id] = snapshot
                restored_type[event.entity_id] = entity_type
            elif event.operation == ChangeOperation.CREATE:
                created = event.entity_id
                for ref in outside.pop(created, []):
                    if self._still_references(ref, restored):
                        blocking.append((ref.dependent_kind, ref.dependent_id, ref.referenced_id))
                for holder, fields in restored.items():
                    if holder == created or holder in gone:
                        continue
                    if _mentions(fields.values(), created):
                        entry = (restored_type[holder], holder, created)
                        if entry not in blocking:
                            blocking.append(entry)
                gone.add(created)
        if blocking:
            raise RevertConflictError(batch_run_id, blocking)

    def _still_references(self, ref, restored: dict[str, dict]) -> bool:
        """
        Whether the dependent still points at the referenced entity once the
        updates in `restored` are undone. A run that typed an existing individual
        into a class it created, say, takes that membership away again first.

        A class's taxonomy_id follows its scheme: undoing a scheme's move takes
        the scheme's classes back with it.
        """
        getter = {
            "taxonomy": self._ontology_repo.get_taxonomy,
            "concept_scheme": self._ontology_repo.get_concept_scheme,
            "class": self._ontology_repo.get_class,
            "individual": self._ontology_repo.get_individual,
            "property_definition": self._ontology_repo.get_property_definition,
            "attribute_definition": self._ontology_repo.get_attribute_definition,
        }.get(ref.dependent_kind)
        entity = getter(ref.dependent_id) if getter is not None else None
        if entity is None:
            return True
        state = {**entity_snapshot(entity), **restored.get(ref.dependent_id, {})}
        if ref.dependent_kind == "class":
            scheme_fields = restored.get(state.get("concept_scheme_id"), {})
            if "taxonomy_id" in scheme_fields:
                state["taxonomy_id"] = scheme_fields["taxonomy_id"]
        state.pop("id", None)
        return _mentions(state.values(), ref.referenced_id)

    def _sync_indexes(self, entity_id: str, entity_type: str) -> None:
        """
        Bring the vector indexes in line with an entity's state after the revert.

        The revert writes through the repository, which stores text but not the
        embeddings derived from it, so (as OntologyService does after its writes)
        each surviving class, property definition and individual is re-embedded
        from its current title/description, and a deleted individual is dropped
        from the recognition index. Called once per entity after all its events
        are undone, so the final state is what gets indexed.

        Best-effort with the same contract as OntologyService's index sync: a
        failure is logged and does not fail the already-applied revert; the
        entity is unsearchable until the next reindex.
        """
        try:
            if entity_type == "individual":
                individual = self._ontology_repo.get_individual(entity_id)
                if individual is None:
                    if self._individual_index is not None:
                        self._individual_index.remove_individual(entity_id)
                    return
                if self._individual_index is not None:
                    self._individual_index.index_individual(
                        entity_id, individual.title, individual.description
                    )
                entity = individual
            elif entity_type == "class":
                entity = self._ontology_repo.get_class(entity_id)
            elif entity_type == "property_definition":
                entity = self._ontology_repo.get_property_definition(entity_id)
            else:
                return
            if entity is not None and self._schema_index is not None:
                self._schema_index.index_entity(entity_id, entity.title, entity.description)
        except Exception:  # noqa: BLE001 - index sync must not fail the revert
            _logger.error(
                "Vector index sync failed for %s %s after revert; not searchable until reindex.",
                entity_type,
                entity_id,
                exc_info=True,
            )

    def _invalidate_graphs(self, reverted: list) -> None:
        """
        Publish GraphInvalidated for every taxonomy after a revert that changed something.

        Every taxonomy is invalidated rather than only the ones the reverted
        entities belong to: working out an entity's taxonomy after the revert has
        deleted it (and maybe the class it hung off) would mean reading each
        entity before undoing it, and a property definition need not belong to
        any taxonomy yet its relationships appear in every graph. The graph and
        RDF caches are rebuilt for the whole workspace on any GraphInvalidated
        anyway, and a workspace has few taxonomies. Taxonomies the reverted
        events name are included too, so one the revert deleted (or a scheme's
        old home) is invalidated as well.
        """
        if self._event_publisher is None:
            return
        taxonomy_ids = {t.id for t in self._ontology_repo.list_taxonomies(limit=None)}
        for event in reverted:
            if self._normalize_entity_type(event.entity_type) == "taxonomy":
                taxonomy_ids.add(event.entity_id)
            for state in (event.previous_state, event.new_state):
                if (state or {}).get("taxonomy_id"):
                    taxonomy_ids.add(state["taxonomy_id"])
        for taxonomy_id in sorted(taxonomy_ids):
            failures = self._event_publisher.publish(
                GraphInvalidated(taxonomy_id=taxonomy_id, reason="batch_run_reverted")
            )
            if failures:
                _logger.warning(
                    "Event handlers failed for GraphInvalidated (taxonomy_id=%s): %s. "
                    "Graph caches may be stale until the next invalidation.",
                    taxonomy_id,
                    ", ".join(name for name, _ in failures),
                )

    # Entity types whose change events record a run's output rather than an
    # ontology entity. An extraction run's only event is an extraction_result
    # CREATE naming the run itself; the run record is history, so a revert
    # leaves it in place.
    _RECORD_ONLY_TYPES = frozenset({"extraction_result"})

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
                self._refuse_if_referenced(batch_run_id, entity_id)
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

        The ChangeEventRecorder stores a deletion's full snapshot in
        ``previous_state`` (``new_state`` is empty); older or hand-recorded events
        carry it in ``new_state``.
        """
        return event.new_state or event.previous_state or {}

    def _refuse_if_referenced(self, batch_run_id: str, entity_id: str) -> None:
        """
        Right before undoing a create, nothing may point at the entity any more:
        inverses run newest first, so whatever the run made or changed to point
        at it has been undone already, and anything still pointing at it is
        outside the run. Deleting it would cascade into that, so the revert is
        refused (and, in a transaction scope, rolled back).
        """
        refs = self._ontology_repo.find_references([entity_id])
        if refs:
            raise RevertConflictError(
                batch_run_id, [(r.dependent_kind, r.dependent_id, r.referenced_id) for r in refs]
            )

    def _with_scheme_taxonomy(self, cls):  # type: ignore[no-untyped-def]
        """A class's taxonomy_id follows its scheme as it stands now, not as recorded."""
        scheme = self._ontology_repo.get_concept_scheme(cls.concept_scheme_id)
        if scheme is not None:
            cls.taxonomy_id = scheme.taxonomy_id
        return cls

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
        elif entity_type == "attribute_definition":
            if self._ontology_repo.get_attribute_definition(entity_id):
                self._ontology_repo.delete_attribute_definition(entity_id)
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
                self._ontology_repo.save_class(self._with_scheme_taxonomy(cls))
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
        elif entity_type == "attribute_definition":
            attr = self._ontology_repo.get_attribute_definition(entity_id)
            if attr:
                self._restore_entity_state(attr, previous_state)
                self._ontology_repo.save_attribute_definition(attr)
                return True
        else:
            raise ValueError(f"Unknown entity type for update revert: {entity_type}")
        return False

    def _inverse_delete(self, entity_id: str, entity_type: str, snapshot: dict) -> bool:
        """
        Inverse of DELETE: recreate the entity, with the same id, from its snapshot.

        Returns:
            True if the entity was successfully recreated

        Raises:
            ValueError: If the snapshot is missing, or too incomplete to rebuild
                the entity (e.g. an older minimal snapshot without class_ids)
        """
        if not snapshot:
            raise ValueError(
                f"Cannot revert DELETE for {entity_type} {entity_id}: "
                "no snapshot of the deleted entity in the change event"
            )
        savers = {
            "taxonomy": self._ontology_repo.save_taxonomy,
            "concept_scheme": self._ontology_repo.save_concept_scheme,
            "class": self._ontology_repo.save_class,
            "individual": self._ontology_repo.save_individual,
            "relationship": self._ontology_repo.save_relationship,
            "property_definition": self._ontology_repo.save_property_definition,
            "attribute_definition": self._ontology_repo.save_attribute_definition,
        }
        save = savers.get(entity_type)
        if save is None:
            raise ValueError(f"Unknown entity type for delete revert: {entity_type}")
        try:
            entity = entity_from_snapshot(entity_type, snapshot, entity_id)
            if entity_type == "class":
                entity = self._with_scheme_taxonomy(entity)
            save(entity)
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
            elif key == "datatype" and value is not None:
                # An attribute's datatype is stored in the change event as its plain value.
                value = DataType(value)
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
        normalized = normalized.replace("attributedefinition", "attribute_definition")
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

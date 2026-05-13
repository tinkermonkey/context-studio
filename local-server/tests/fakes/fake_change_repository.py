"""
In-memory fake implementation of the ChangeRepository protocol for testing.

Provides a simple dict-based storage for testing domain logic without
database dependencies.
"""

from datetime import datetime, timezone
from typing import Optional
from copy import deepcopy

from domain.versioning.entities import (
    ChangeEvent,
    EntityVersion,
    Changeset,
    Proposal,
)
from domain.versioning.value_objects import ChangeOperation, ChangeHistoryResult
from domain.versioning.exceptions import VersionNotFoundError


class FakeChangeRepository:
    """
    In-memory implementation of the ChangeRepository protocol.

    Uses dictionaries to store entities in memory, useful for unit testing
    domain logic without database dependencies.
    """

    def __init__(self) -> None:
        """Initialize the fake repository with empty storage."""
        self._change_events: dict[str, ChangeEvent] = {}
        self._entity_versions: dict[tuple[str, int], EntityVersion] = {}
        self._changesets: dict[str, Changeset] = {}
        self._changeset_events: dict[tuple[str, str], bool] = {}
        self._proposals: dict[str, Proposal] = {}
        self._conflict_resolutions: dict[str, dict[str, dict[str, object]]] = {}

    # ChangeEvent operations

    def record_change(
        self,
        entity_id: str,
        entity_type: str,
        operation: ChangeOperation,
        new_state: dict,
        previous_state: Optional[dict] = None,
        user_id: Optional[str] = None,
        change_reason: Optional[str] = None,
        changeset_id: Optional[str] = None,
        batch_run_id: Optional[str] = None,
    ) -> str:
        """Record a change event and return its ID."""
        import uuid

        event_id = str(uuid.uuid4())
        event = ChangeEvent(
            id=event_id,
            entity_id=entity_id,
            entity_type=entity_type,
            operation=operation,
            new_state=new_state,
            timestamp=datetime.now(timezone.utc),
            previous_state=previous_state,
            user_id=user_id,
            change_reason=change_reason,
            changeset_id=changeset_id,
            batch_run_id=batch_run_id,
            processed=False,
        )
        self._change_events[event_id] = event
        return event_id

    def get_changes(
        self,
        entity_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> ChangeHistoryResult:
        """Retrieve change events with optional filters and return total count."""
        events = list(self._change_events.values())

        if entity_id:
            events = [e for e in events if e.entity_id == entity_id]

        if since:
            events = [e for e in events if e.timestamp >= since]

        total_count = len(events)
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return ChangeHistoryResult(events=tuple(events[:limit]), total=total_count)

    def get_changes_by_ids(self, event_ids: list[str]) -> list[ChangeEvent]:
        """Retrieve change events by their IDs."""
        return [
            self._change_events[eid] for eid in event_ids if eid in self._change_events
        ]

    def mark_processed(self, event_ids: list[str]) -> None:
        """
        Mark change events as processed.

        Raises:
            VersionNotFoundError: If any event IDs don't exist
        """
        if not event_ids:
            return

        # Check all IDs exist first
        missing_ids = [eid for eid in event_ids if eid not in self._change_events]
        if missing_ids:
            raise VersionNotFoundError(
                f"Change events not found: {', '.join(sorted(missing_ids))}"
            )

        # Mark all as processed
        for event_id in event_ids:
            self._change_events[event_id].processed = True

    def delete_changes(self, event_ids: list[str]) -> None:
        """
        Delete change events by their IDs (used for rollback on pull failure).

        Raises:
            VersionNotFoundError: If any event IDs don't exist
        """
        if not event_ids:
            return

        # Check all IDs exist first
        missing_ids = [eid for eid in event_ids if eid not in self._change_events]
        if missing_ids:
            raise VersionNotFoundError(
                f"Change events not found: {', '.join(sorted(missing_ids))}"
            )

        # Delete all
        for event_id in event_ids:
            self._change_events.pop(event_id)

    def get_unprocessed(self, limit: int = 500) -> list[ChangeEvent]:
        """Retrieve unprocessed change events."""
        unprocessed = [e for e in self._change_events.values() if not e.processed]
        unprocessed.sort(key=lambda e: e.timestamp)
        return unprocessed[:limit]

    def count_unprocessed(self) -> int:
        """Count total unprocessed change events without loading them."""
        return sum(1 for e in self._change_events.values() if not e.processed)

    # EntityVersion operations

    def save_version(self, version: EntityVersion) -> None:
        """Save an entity version."""
        key = (version.entity_id, version.version)
        self._entity_versions[key] = version

    def get_version(self, entity_id: str, version: int) -> Optional[EntityVersion]:
        """Retrieve a specific version."""
        return self._entity_versions.get((entity_id, version))

    def get_latest_version(self, entity_id: str) -> Optional[EntityVersion]:
        """Retrieve the latest version of an entity."""
        matching = [
            v for (eid, _), v in self._entity_versions.items() if eid == entity_id
        ]
        if not matching:
            return None
        return max(matching, key=lambda v: v.version)

    def list_versions(self, entity_id: str) -> list[EntityVersion]:
        """Retrieve all versions of an entity."""
        versions = [
            v for (eid, _), v in self._entity_versions.items() if eid == entity_id
        ]
        versions.sort(key=lambda v: v.version)
        return versions

    # Changeset operations

    def create_changeset(self, changeset: Changeset) -> Changeset:
        """
        Create a new changeset.

        Stores a copy to prevent tests from relying on by-reference mutations.
        """
        self._changesets[changeset.id] = deepcopy(changeset)
        return changeset

    def get_changeset(self, changeset_id: str) -> Optional[Changeset]:
        """Retrieve a changeset by ID."""
        stored = self._changesets.get(changeset_id)
        if stored is not None:
            return deepcopy(stored)
        return None

    def list_changesets(self, limit: int = 100) -> list[Changeset]:
        """List all changesets."""
        changesets = list(self._changesets.values())
        changesets.sort(key=lambda c: c.created_at, reverse=True)
        return [deepcopy(c) for c in changesets[:limit]]

    def update_changeset(self, changeset: Changeset) -> Changeset:
        """
        Update an existing changeset.

        Stores a copy to prevent tests from relying on by-reference mutations.
        """
        self._changesets[changeset.id] = deepcopy(changeset)
        return changeset

    # Proposal operations

    def create_proposal(self, proposal: Proposal) -> Proposal:
        """
        Create a new proposal.

        Stores a copy to prevent tests from relying on by-reference mutations.
        """
        self._proposals[proposal.id] = deepcopy(proposal)
        return proposal

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """Retrieve a proposal by ID."""
        stored = self._proposals.get(proposal_id)
        if stored is not None:
            return deepcopy(stored)
        return None

    def update_proposal(self, proposal: Proposal) -> Proposal:
        """
        Update an existing proposal.

        Stores a copy to prevent tests from relying on by-reference mutations.
        """
        self._proposals[proposal.id] = deepcopy(proposal)
        return proposal

    def update_changeset_and_proposal_on_submit(
        self, changeset: Changeset, proposal: Proposal
    ) -> tuple[Changeset, Proposal]:
        """
        Atomically update changeset and create proposal on submit.

        Stores copies to prevent tests from relying on by-reference mutations.
        """
        self._changesets[changeset.id] = deepcopy(changeset)
        self._proposals[proposal.id] = deepcopy(proposal)
        return deepcopy(changeset), deepcopy(proposal)

    def atomic_update_changeset_and_proposal(
        self, changeset: Changeset, proposal: Proposal
    ) -> tuple[Changeset, Proposal]:
        """
        Atomically update changeset and proposal on approve, reject, or merge.

        Stores copies to prevent tests from relying on by-reference mutations.
        """
        self._changesets[changeset.id] = deepcopy(changeset)
        self._proposals[proposal.id] = deepcopy(proposal)
        return deepcopy(changeset), deepcopy(proposal)

    def atomic_update_on_merge(
        self,
        changeset: Changeset,
        proposal: Proposal,
        versions: list[EntityVersion],
    ) -> tuple[Changeset, Proposal]:
        """
        Atomically update changeset, proposal, and save entity versions on merge.

        Stores copies to prevent tests from relying on by-reference mutations.
        """
        self._changesets[changeset.id] = deepcopy(changeset)
        self._proposals[proposal.id] = deepcopy(proposal)
        for version in versions:
            self._entity_versions[(version.entity_id, version.version)] = deepcopy(
                version
            )
        return deepcopy(changeset), deepcopy(proposal)

    def save_conflict_resolutions(
        self, proposal_id: str, resolutions: dict[str, dict[str, object]]
    ) -> None:
        """
        Persist conflict resolutions for a proposal.

        Args:
            proposal_id: ID of the proposal
            resolutions: Dict mapping entity_id -> {field_name: resolved_value}
        """
        self._conflict_resolutions[proposal_id] = deepcopy(resolutions)

    def get_conflict_resolutions(
        self, proposal_id: str
    ) -> dict[str, dict[str, object]]:
        """
        Retrieve persisted conflict resolutions for a proposal.

        Args:
            proposal_id: ID of the proposal

        Returns:
            Dict mapping entity_id -> {field_name: resolved_value}
        """
        return deepcopy(self._conflict_resolutions.get(proposal_id, {}))

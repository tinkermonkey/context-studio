"""
Domain service for changeset management in the versioning context.

Encapsulates changeset creation, retrieval, and staging logic.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from .entities import Changeset
from .exceptions import VersionNotFoundError, ChangesetStateError
from .ports import ChangeRepository
from .value_objects import ChangeState, ChangeOperation

_logger = logging.getLogger(__name__)


class ChangesetManagementService:
    """
    Domain service for changeset management.

    Coordinates changeset creation, retrieval, and staging operations.
    """

    def __init__(self, change_repo: ChangeRepository) -> None:
        """
        Initialize the ChangesetManagementService.

        Args:
            change_repo: Repository for persisting changeset entities
        """
        self._repo = change_repo

    def get_changeset(self, changeset_id: str) -> Changeset:
        """
        Retrieve a changeset by ID.

        Args:
            changeset_id: ID of the changeset to retrieve

        Returns:
            The Changeset entity

        Raises:
            VersionNotFoundError: If the changeset does not exist
        """
        changeset = self._repo.get_changeset(changeset_id)
        if changeset is None:
            raise VersionNotFoundError(f"Changeset {changeset_id} not found")
        return changeset

    def create_changeset(
        self,
        name: str,
        description: Optional[str] = None,
        event_ids: Optional[list[str]] = None,
    ) -> Changeset:
        """
        Create a new changeset in WORKING state.

        A changeset is a named collection of change events that can be
        reviewed and merged as a unit. Changesets progress through states:
        WORKING → STAGED → PROPOSED → APPROVED → MERGED

        Args:
            name: Name of the changeset
            description: Optional detailed description of the changeset
            event_ids: Optional list of existing change event IDs to include

        Returns:
            The persisted Changeset entity in WORKING state
        """
        now = datetime.now(timezone.utc)
        changeset = Changeset(
            id=str(uuid.uuid4()),
            name=name,
            state=ChangeState.WORKING,
            created_at=now,
            updated_at=now,
            description=description,
            event_ids=event_ids or [],
        )
        persisted = self._repo.create_changeset(changeset)
        _logger.info(
            "Changeset created (changeset_id=%s, name=%s, state=%s)",
            persisted.id,
            persisted.name,
            persisted.state,
        )
        return persisted

    def stage_changeset(self, changeset_id: str) -> Changeset:
        """
        Transition a changeset from WORKING to STAGED.

        Args:
            changeset_id: ID of the changeset to stage

        Returns:
            The updated Changeset entity in STAGED state

        Raises:
            ChangesetStateError: If the changeset cannot transition to STAGED
            VersionNotFoundError: If the changeset does not exist
        """
        changeset = self._repo.get_changeset(changeset_id)
        if changeset is None:
            raise VersionNotFoundError(f"Changeset {changeset_id} not found")

        changeset.transition_to(ChangeState.STAGED)
        changeset.updated_at = datetime.now(timezone.utc)
        updated = self._repo.update_changeset(changeset)
        _logger.info(
            "Changeset staged (changeset_id=%s, state=%s)",
            updated.id,
            updated.state,
        )
        return updated

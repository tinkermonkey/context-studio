"""
VersionManager Service - Centralized business logic for entity versioning operations

This service implements the core versioning logic for the change management system,
handling version creation, tracking, and retrieval with SQLite storage.
"""

import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import text

from utils.logger import get_logger

logger = get_logger(__name__)


class ChangeState(Enum):
    """State enumeration for entity versions."""

    WORKING = "WORKING"
    STAGED = "STAGED"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    MERGED = "MERGED"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"


@dataclass
class EntityVersion:
    """Data class representing an entity version."""

    id: str
    entity_type: str
    entity_id: str
    version_number: int
    content: Dict[str, Any]
    state: ChangeState
    parent_version_id: Optional[str]
    changeset_id: Optional[str]
    author_id: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class VersionManager:
    """Centralized business logic for entity versioning operations."""

    def __init__(self, db: Session):
        """
        Initialize the VersionManager.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        logger.info("VersionManager initialized")

    def create_version(
        self,
        entity_type: str,
        entity_id: str,
        content: Dict[str, Any],
        author_id: str,
        state: ChangeState = ChangeState.WORKING,
        parent_version_id: Optional[str] = None,
        changeset_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EntityVersion:
        """
        Create a new version of an entity.

        Args:
            entity_type: Type of entity ('structure_node', 'structure_node_link')
            entity_id: ID of the entity being versioned
            content: Full entity snapshot as dictionary
            author_id: User identifier who created this version
            state: Version state (default: WORKING)
            parent_version_id: Optional parent version reference
            changeset_id: Optional changeset identifier
            metadata: Optional additional metadata

        Returns:
            EntityVersion instance

        Raises:
            ValueError: If validation fails
            RuntimeError: If database operation fails
        """
        logger.debug(f"Creating version for {entity_type}:{entity_id} by {author_id}")

        # Validate inputs
        if entity_type not in ("structure_node", "structure_node_link"):
            raise ValueError(f"Invalid entity_type: {entity_type}")

        if not entity_id or not author_id:
            raise ValueError("entity_id and author_id are required")

        if not content:
            raise ValueError("content cannot be empty")

        # Validate parent version exists if specified
        if parent_version_id:
            parent_exists = self.db.execute(
                text(
                    """
                SELECT 1 FROM entity_versions WHERE id = :parent_id
            """
                ),
                {"parent_id": parent_version_id},
            ).fetchone()

            if not parent_exists:
                raise ValueError(f"Parent version {parent_version_id} does not exist")

        # Get next version number for this entity
        next_version = self._get_next_version_number(entity_type, entity_id)

        # Generate version ID
        version_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)

        try:
            # Insert version record
            self.db.execute(
                text(
                    """
                INSERT INTO entity_versions (
                    id, entity_type, entity_id, version_number, content, state,
                    parent_version_id, changeset_id, author_id, created_at, metadata
                ) VALUES (
                    :id, :entity_type, :entity_id, :version_number, :content, :state,
                    :parent_version_id, :changeset_id, :author_id, :created_at, :metadata
                )
            """
                ),
                {
                    "id": version_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "version_number": next_version,
                    "content": json.dumps(content),
                    "state": state.value,
                    "parent_version_id": parent_version_id,
                    "changeset_id": changeset_id,
                    "author_id": author_id,
                    "created_at": created_at.isoformat(),
                    "metadata": json.dumps(metadata) if metadata else None,
                },
            )

            self.db.commit()

            logger.debug(
                f"Created version {next_version} for {entity_type}:{entity_id} (id: {version_id})"
            )

            return EntityVersion(
                id=version_id,
                entity_type=entity_type,
                entity_id=entity_id,
                version_number=next_version,
                content=content,
                state=state,
                parent_version_id=parent_version_id,
                changeset_id=changeset_id,
                author_id=author_id,
                created_at=created_at,
                metadata=metadata,
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create version for {entity_type}:{entity_id}: {e}")
            raise RuntimeError(f"Database error during version creation: {e}") from e

    def get_entity_versions(
        self, entity_type: str, entity_id: str
    ) -> List[EntityVersion]:
        """
        Get all versions of an entity ordered by version number.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            List of EntityVersion instances sorted by version number
        """
        logger.debug(f"Retrieving versions for {entity_type}:{entity_id}")

        try:
            results = self.db.execute(
                text(
                    """
                SELECT id, entity_type, entity_id, version_number, content, state,
                       parent_version_id, changeset_id, author_id, created_at, metadata
                FROM entity_versions 
                WHERE entity_type = :entity_type AND entity_id = :entity_id
                ORDER BY version_number ASC
            """
                ),
                {"entity_type": entity_type, "entity_id": entity_id},
            ).fetchall()

            versions = []
            for row in results:
                versions.append(self._row_to_entity_version(row))

            logger.debug(
                f"Retrieved {len(versions)} versions for {entity_type}:{entity_id}"
            )
            return versions

        except Exception as e:
            logger.error(
                f"Failed to retrieve versions for {entity_type}:{entity_id}: {e}"
            )
            raise RuntimeError(f"Database error during version retrieval: {e}") from e

    def get_version_by_number(
        self, entity_type: str, entity_id: str, version_number: int
    ) -> Optional[EntityVersion]:
        """
        Get a specific version of an entity by version number.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            version_number: Version number to retrieve

        Returns:
            EntityVersion instance or None if not found
        """
        logger.debug(
            f"Retrieving version {version_number} for {entity_type}:{entity_id}"
        )

        try:
            result = self.db.execute(
                text(
                    """
                SELECT id, entity_type, entity_id, version_number, content, state,
                       parent_version_id, changeset_id, author_id, created_at, metadata
                FROM entity_versions 
                WHERE entity_type = :entity_type AND entity_id = :entity_id 
                  AND version_number = :version_number
            """
                ),
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "version_number": version_number,
                },
            ).fetchone()

            if result:
                return self._row_to_entity_version(result)

            logger.debug(
                f"Version {version_number} not found for {entity_type}:{entity_id}"
            )
            return None

        except Exception as e:
            logger.error(
                f"Failed to retrieve version {version_number} for {entity_type}:{entity_id}: {e}"
            )
            raise RuntimeError(f"Database error during version retrieval: {e}") from e

    def get_current_version(
        self, entity_type: str, entity_id: str
    ) -> Optional[EntityVersion]:
        """
        Get the latest version of an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            EntityVersion instance or None if no versions exist
        """
        logger.debug(f"Retrieving current version for {entity_type}:{entity_id}")

        try:
            result = self.db.execute(
                text(
                    """
                SELECT id, entity_type, entity_id, version_number, content, state,
                       parent_version_id, changeset_id, author_id, created_at, metadata
                FROM entity_versions 
                WHERE entity_type = :entity_type AND entity_id = :entity_id
                ORDER BY version_number DESC 
                LIMIT 1
            """
                ),
                {"entity_type": entity_type, "entity_id": entity_id},
            ).fetchone()

            if result:
                return self._row_to_entity_version(result)

            logger.debug(f"No versions found for {entity_type}:{entity_id}")
            return None

        except Exception as e:
            logger.error(
                f"Failed to retrieve current version for {entity_type}:{entity_id}: {e}"
            )
            raise RuntimeError(f"Database error during version retrieval: {e}") from e

    def rollback_to_version(
        self,
        entity_type: str,
        entity_id: str,
        target_version_number: int,
        author_id: str,
    ) -> EntityVersion:
        """
        Rollback entity to a specific version by creating a new version with target content.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            target_version_number: Version number to rollback to
            author_id: User identifier performing the rollback

        Returns:
            New EntityVersion instance representing the rollback

        Raises:
            ValueError: If target version doesn't exist
            RuntimeError: If database operation fails
        """
        logger.info(
            f"Rolling back {entity_type}:{entity_id} to version {target_version_number}"
        )

        # Get target version
        target_version = self.get_version_by_number(
            entity_type, entity_id, target_version_number
        )
        if not target_version:
            raise ValueError(f"Target version {target_version_number} does not exist")

        # Create new version with target content
        rollback_metadata = {
            "operation": "rollback",
            "target_version": target_version_number,
            "rollback_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self.create_version(
            entity_type=entity_type,
            entity_id=entity_id,
            content=target_version.content,
            author_id=author_id,
            state=ChangeState.WORKING,
            parent_version_id=target_version.id,
            metadata=rollback_metadata,
        )

    def update_version_state(
        self, version_id: str, new_state: ChangeState, author_id: str
    ) -> bool:
        """
        Update the state of an existing version.

        Args:
            version_id: ID of the version to update
            new_state: New state to set
            author_id: User identifier performing the update

        Returns:
            True if update was successful, False if version not found

        Raises:
            RuntimeError: If database operation fails
        """
        logger.info(f"Updating version {version_id} state to {new_state.value}")

        try:
            result = self.db.execute(
                text(
                    """
                UPDATE entity_versions 
                SET state = :new_state 
                WHERE id = :version_id
            """
                ),
                {"new_state": new_state.value, "version_id": version_id},
            )

            if result.rowcount > 0:
                self.db.commit()
                logger.info(f"Updated version {version_id} state to {new_state.value}")
                return True
            else:
                logger.debug(f"Version {version_id} not found for state update")
                return False

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update version {version_id} state: {e}")
            raise RuntimeError(f"Database error during state update: {e}") from e

    def get_versions_by_state(self, state: ChangeState) -> List[EntityVersion]:
        """
        Get all versions with a specific state.

        Args:
            state: State to filter by

        Returns:
            List of EntityVersion instances with the specified state
        """
        logger.debug(f"Retrieving versions with state {state.value}")

        try:
            results = self.db.execute(
                text(
                    """
                SELECT id, entity_type, entity_id, version_number, content, state,
                       parent_version_id, changeset_id, author_id, created_at, metadata
                FROM entity_versions 
                WHERE state = :state
                ORDER BY created_at DESC
            """
                ),
                {"state": state.value},
            ).fetchall()

            versions = []
            for row in results:
                versions.append(self._row_to_entity_version(row))

            logger.debug(f"Retrieved {len(versions)} versions with state {state.value}")
            return versions

        except Exception as e:
            logger.error(f"Failed to retrieve versions by state {state.value}: {e}")
            raise RuntimeError(f"Database error during version retrieval: {e}") from e

    def _get_next_version_number(self, entity_type: str, entity_id: str) -> int:
        """Get the next version number for an entity."""
        result = self.db.execute(
            text(
                """
            SELECT MAX(version_number) FROM entity_versions 
            WHERE entity_type = :entity_type AND entity_id = :entity_id
        """
            ),
            {"entity_type": entity_type, "entity_id": entity_id},
        ).scalar()

        return (result or 0) + 1

    def _row_to_entity_version(self, row) -> EntityVersion:
        """Convert database row to EntityVersion instance."""
        content = json.loads(row[4]) if row[4] else {}
        metadata = json.loads(row[10]) if row[10] else None

        return EntityVersion(
            id=row[0],
            entity_type=row[1],
            entity_id=row[2],
            version_number=row[3],
            content=content,
            state=ChangeState(row[5]),
            parent_version_id=row[6],
            changeset_id=row[7],
            author_id=row[8],
            created_at=datetime.fromisoformat(row[9].replace("Z", "+00:00")),
            metadata=metadata,
        )

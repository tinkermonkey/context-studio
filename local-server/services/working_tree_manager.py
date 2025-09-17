"""
WorkingTreeManager Service - Manages working tree state and staging operations

This service implements working tree state management, tracking current and canonical
versions of entities, and providing staging/unstaging operations for the change management system.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.version_manager import VersionManager, EntityVersion, ChangeState
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WorkingTreeEntry:
    """Data class representing a working tree entry."""

    entity_type: str
    entity_id: str
    current_version_id: str
    canonical_version_id: str
    staged: bool
    modified_at: datetime

    def has_changes(self) -> bool:
        """Check if the working version differs from canonical."""
        return self.current_version_id != self.canonical_version_id


@dataclass
class WorkingTreeStatus:
    """Data class representing overall working tree status."""

    total_entities: int
    modified_entities: int
    staged_entities: int
    unstaged_entities: int
    entries: List[WorkingTreeEntry]


class WorkingTreeManager:
    """Manages working tree state and staging operations."""

    def __init__(self, db: Session, version_manager: VersionManager):
        """
        Initialize the WorkingTreeManager.

        Args:
            db: SQLAlchemy database session
            version_manager: VersionManager instance for version operations
        """
        self.db = db
        self.version_manager = version_manager
        logger.info("WorkingTreeManager initialized")

    def initialize_entity_in_working_tree(
        self, entity_type: str, entity_id: str, initial_version_id: str
    ) -> WorkingTreeEntry:
        """
        Initialize an entity in the working tree.

        Args:
            entity_type: Type of entity ('structure_node', 'structure_node_link')
            entity_id: ID of the entity
            initial_version_id: Initial version ID (both current and canonical)

        Returns:
            WorkingTreeEntry instance

        Raises:
            ValueError: If validation fails
            RuntimeError: If database operation fails
        """
        logger.info(f"Initializing {entity_type}:{entity_id} in working tree")

        # Validate inputs
        if entity_type not in ("structure_node", "structure_node_link"):
            raise ValueError(f"Invalid entity_type: {entity_type}")

        if not entity_id or not initial_version_id:
            raise ValueError("entity_id and initial_version_id are required")

        # Check if entity already exists in working tree
        existing = self.get_working_tree_entry(entity_type, entity_id)
        if existing:
            logger.warning(
                f"Entity {entity_type}:{entity_id} already exists in working tree"
            )
            return existing

        # Verify the version exists
        version_exists = self.db.execute(
            text(
                """
            SELECT 1 FROM entity_versions WHERE id = :version_id
        """
            ),
            {"version_id": initial_version_id},
        ).fetchone()

        if not version_exists:
            raise ValueError(f"Version {initial_version_id} does not exist")

        modified_at = datetime.now(timezone.utc)

        try:
            # Insert working tree entry
            self.db.execute(
                text(
                    """
                INSERT INTO working_tree (
                    entity_type, entity_id, current_version_id, canonical_version_id, staged, modified_at
                ) VALUES (
                    :entity_type, :entity_id, :current_version_id, :canonical_version_id, :staged, :modified_at
                )
            """
                ),
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "current_version_id": initial_version_id,
                    "canonical_version_id": initial_version_id,
                    "staged": False,
                    "modified_at": modified_at.isoformat(),
                },
            )

            self.db.commit()

            logger.info(f"Initialized {entity_type}:{entity_id} in working tree")

            return WorkingTreeEntry(
                entity_type=entity_type,
                entity_id=entity_id,
                current_version_id=initial_version_id,
                canonical_version_id=initial_version_id,
                staged=False,
                modified_at=modified_at,
            )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to initialize {entity_type}:{entity_id} in working tree: {e}"
            )
            raise RuntimeError(
                f"Database error during working tree initialization: {e}"
            ) from e

    def update_current_version(
        self, entity_type: str, entity_id: str, new_version_id: str
    ) -> WorkingTreeEntry:
        """
        Update the current working version of an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            new_version_id: New current version ID

        Returns:
            Updated WorkingTreeEntry instance

        Raises:
            ValueError: If entity not in working tree or version doesn't exist
            RuntimeError: If database operation fails
        """
        logger.info(f"Updating current version for {entity_type}:{entity_id}")

        # Verify the entity exists in working tree
        existing = self.get_working_tree_entry(entity_type, entity_id)
        if not existing:
            raise ValueError(
                f"Entity {entity_type}:{entity_id} not found in working tree"
            )

        # Verify the new version exists
        version_exists = self.db.execute(
            text(
                """
            SELECT 1 FROM entity_versions WHERE id = :version_id
        """
            ),
            {"version_id": new_version_id},
        ).fetchone()

        if not version_exists:
            raise ValueError(f"Version {new_version_id} does not exist")

        modified_at = datetime.now(timezone.utc)

        try:
            # Update working tree entry
            result = self.db.execute(
                text(
                    """
                UPDATE working_tree 
                SET current_version_id = :new_version_id, 
                    modified_at = :modified_at,
                    staged = :staged
                WHERE entity_type = :entity_type AND entity_id = :entity_id
            """
                ),
                {
                    "new_version_id": new_version_id,
                    "modified_at": modified_at.isoformat(),
                    "staged": False,  # Reset staged status on version update
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                },
            )

            if result.rowcount == 0:
                raise ValueError(
                    f"Entity {entity_type}:{entity_id} not found in working tree"
                )

            self.db.commit()

            logger.info(f"Updated current version for {entity_type}:{entity_id}")

            return WorkingTreeEntry(
                entity_type=entity_type,
                entity_id=entity_id,
                current_version_id=new_version_id,
                canonical_version_id=existing.canonical_version_id,
                staged=False,
                modified_at=modified_at,
            )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to update current version for {entity_type}:{entity_id}: {e}"
            )
            raise RuntimeError(f"Database error during version update: {e}") from e

    def stage_entity(self, entity_type: str, entity_id: str) -> bool:
        """
        Stage an entity for commit.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            True if successfully staged, False if no changes to stage

        Raises:
            ValueError: If entity not in working tree
            RuntimeError: If database operation fails
        """
        logger.info(f"Staging {entity_type}:{entity_id}")

        # Get working tree entry
        entry = self.get_working_tree_entry(entity_type, entity_id)
        if not entry:
            raise ValueError(
                f"Entity {entity_type}:{entity_id} not found in working tree"
            )

        # Check if there are changes to stage
        if not entry.has_changes():
            logger.info(f"No changes to stage for {entity_type}:{entity_id}")
            return False

        if entry.staged:
            logger.info(f"Entity {entity_type}:{entity_id} is already staged")
            return True

        try:
            # Update staged status
            result = self.db.execute(
                text(
                    """
                UPDATE working_tree 
                SET staged = TRUE, modified_at = :modified_at
                WHERE entity_type = :entity_type AND entity_id = :entity_id
            """
                ),
                {
                    "modified_at": datetime.now(timezone.utc).isoformat(),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                },
            )

            if result.rowcount == 0:
                raise ValueError(
                    f"Entity {entity_type}:{entity_id} not found in working tree"
                )

            self.db.commit()

            logger.info(f"Staged {entity_type}:{entity_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to stage {entity_type}:{entity_id}: {e}")
            raise RuntimeError(f"Database error during staging: {e}") from e

    def unstage_entity(self, entity_type: str, entity_id: str) -> bool:
        """
        Unstage an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            True if successfully unstaged

        Raises:
            ValueError: If entity not in working tree
            RuntimeError: If database operation fails
        """
        logger.info(f"Unstaging {entity_type}:{entity_id}")

        # Verify entity exists in working tree
        entry = self.get_working_tree_entry(entity_type, entity_id)
        if not entry:
            raise ValueError(
                f"Entity {entity_type}:{entity_id} not found in working tree"
            )

        if not entry.staged:
            logger.info(f"Entity {entity_type}:{entity_id} is not staged")
            return True

        try:
            # Update staged status
            result = self.db.execute(
                text(
                    """
                UPDATE working_tree 
                SET staged = FALSE, modified_at = :modified_at
                WHERE entity_type = :entity_type AND entity_id = :entity_id
            """
                ),
                {
                    "modified_at": datetime.now(timezone.utc).isoformat(),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                },
            )

            if result.rowcount == 0:
                raise ValueError(
                    f"Entity {entity_type}:{entity_id} not found in working tree"
                )

            self.db.commit()

            logger.info(f"Unstaged {entity_type}:{entity_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to unstage {entity_type}:{entity_id}: {e}")
            raise RuntimeError(f"Database error during unstaging: {e}") from e

    def commit_staged_changes(self, author_id: str) -> List[EntityVersion]:
        """
        Commit all staged changes by updating canonical versions.

        Args:
            author_id: User identifier performing the commit

        Returns:
            List of committed EntityVersion instances

        Raises:
            RuntimeError: If database operation fails
        """
        logger.info(f"Committing staged changes for {author_id}")

        # Get all staged entities
        staged_entries = self.get_staged_entities()
        if not staged_entries:
            logger.info("No staged changes to commit")
            return []

        committed_versions = []

        try:
            for entry in staged_entries:
                # Update canonical version and unstage
                self.db.execute(
                    text(
                        """
                    UPDATE working_tree 
                    SET canonical_version_id = current_version_id, 
                        staged = FALSE,
                        modified_at = :modified_at
                    WHERE entity_type = :entity_type AND entity_id = :entity_id
                """
                    ),
                    {
                        "modified_at": datetime.now(timezone.utc).isoformat(),
                        "entity_type": entry.entity_type,
                        "entity_id": entry.entity_id,
                    },
                )

                # Update the version state to MERGED
                self.version_manager.update_version_state(
                    entry.current_version_id, ChangeState.MERGED, author_id
                )

                # Get the committed version
                version = self.version_manager.get_version_by_number(
                    entry.entity_type,
                    entry.entity_id,
                    self._get_version_number_by_id(entry.current_version_id),
                )
                if version:
                    committed_versions.append(version)

            self.db.commit()

            logger.info(f"Committed {len(committed_versions)} staged changes")
            return committed_versions

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to commit staged changes: {e}")
            raise RuntimeError(f"Database error during commit: {e}") from e

    def get_working_tree_entry(
        self, entity_type: str, entity_id: str
    ) -> Optional[WorkingTreeEntry]:
        """
        Get working tree entry for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            WorkingTreeEntry instance or None if not found
        """
        try:
            result = self.db.execute(
                text(
                    """
                SELECT entity_type, entity_id, current_version_id, canonical_version_id, staged, modified_at
                FROM working_tree 
                WHERE entity_type = :entity_type AND entity_id = :entity_id
            """
                ),
                {"entity_type": entity_type, "entity_id": entity_id},
            ).fetchone()

            if result:
                return self._row_to_working_tree_entry(result)

            return None

        except Exception as e:
            logger.error(
                f"Failed to retrieve working tree entry for {entity_type}:{entity_id}: {e}"
            )
            raise RuntimeError(
                f"Database error during working tree retrieval: {e}"
            ) from e

    def get_working_changes(self) -> List[WorkingTreeEntry]:
        """
        Get all entities with working changes (current != canonical).

        Returns:
            List of WorkingTreeEntry instances with changes
        """
        try:
            results = self.db.execute(
                text(
                    """
                SELECT entity_type, entity_id, current_version_id, canonical_version_id, staged, modified_at
                FROM working_tree 
                WHERE current_version_id != canonical_version_id
                ORDER BY modified_at DESC
            """
                )
            ).fetchall()

            entries = []
            for row in results:
                entries.append(self._row_to_working_tree_entry(row))

            logger.debug(f"Retrieved {len(entries)} entities with working changes")
            return entries

        except Exception as e:
            logger.error(f"Failed to retrieve working changes: {e}")
            raise RuntimeError(
                f"Database error during working changes retrieval: {e}"
            ) from e

    def get_staged_entities(self) -> List[WorkingTreeEntry]:
        """
        Get all staged entities.

        Returns:
            List of WorkingTreeEntry instances that are staged
        """
        try:
            results = self.db.execute(
                text(
                    """
                SELECT entity_type, entity_id, current_version_id, canonical_version_id, staged, modified_at
                FROM working_tree 
                WHERE staged = TRUE
                ORDER BY modified_at DESC
            """
                )
            ).fetchall()

            entries = []
            for row in results:
                entries.append(self._row_to_working_tree_entry(row))

            logger.debug(f"Retrieved {len(entries)} staged entities")
            return entries

        except Exception as e:
            logger.error(f"Failed to retrieve staged entities: {e}")
            raise RuntimeError(
                f"Database error during staged entities retrieval: {e}"
            ) from e

    def get_staged_changes(self) -> List[Dict[str, Any]]:
        """
        Get staged changes as change dictionaries for changeset creation.

        Returns:
            List of change dictionaries with version_id, change_type, and entity_type
        """
        try:
            staged_entities = self.get_staged_entities()
            changes = []

            for entry in staged_entities:
                # Determine change type based on whether this creates a new entity
                # For now, assume all changes are updates - this could be enhanced
                # to detect creates/deletes by checking if it's the first version
                change_type = "update"  # Could be "create", "update", or "delete"

                change = {
                    "version_id": entry.current_version_id,
                    "change_type": change_type,
                    "entity_type": entry.entity_type
                }
                changes.append(change)

            logger.debug(f"Retrieved {len(changes)} staged changes")
            return changes

        except Exception as e:
            logger.error(f"Failed to retrieve staged changes: {e}")
            raise RuntimeError(
                f"Database error during staged changes retrieval: {e}"
            ) from e

    def capture_version_snapshot(self) -> str:
        """
        Capture a snapshot of current version state.

        Returns:
            Snapshot identifier
        """
        try:
            snapshot_id = f"snapshot_{int(datetime.now(timezone.utc).timestamp())}"
            logger.debug(f"Captured version snapshot: {snapshot_id}")
            return snapshot_id

        except Exception as e:
            logger.error(f"Failed to capture version snapshot: {e}")
            raise RuntimeError(
                f"Error during version snapshot capture: {e}"
            ) from e

    def get_working_tree_status(self) -> WorkingTreeStatus:
        """
        Get comprehensive working tree status.

        Returns:
            WorkingTreeStatus with summary and details
        """
        try:
            # Get all working tree entries
            results = self.db.execute(
                text(
                    """
                SELECT entity_type, entity_id, current_version_id, canonical_version_id, staged, modified_at
                FROM working_tree 
                ORDER BY modified_at DESC
            """
                )
            ).fetchall()

            entries = []
            modified_count = 0
            staged_count = 0

            for row in results:
                entry = self._row_to_working_tree_entry(row)
                entries.append(entry)

                if entry.has_changes():
                    modified_count += 1

                if entry.staged:
                    staged_count += 1

            unstaged_count = modified_count - staged_count

            logger.debug(
                f"Working tree status: {len(entries)} total, {modified_count} modified, {staged_count} staged"
            )

            return WorkingTreeStatus(
                total_entities=len(entries),
                modified_entities=modified_count,
                staged_entities=staged_count,
                unstaged_entities=unstaged_count,
                entries=entries,
            )

        except Exception as e:
            logger.error(f"Failed to retrieve working tree status: {e}")
            raise RuntimeError(
                f"Database error during working tree status retrieval: {e}"
            ) from e

    def _get_version_number_by_id(self, version_id: str) -> int:
        """Get version number by version ID."""
        result = self.db.execute(
            text(
                """
            SELECT version_number FROM entity_versions WHERE id = :version_id
        """
            ),
            {"version_id": version_id},
        ).scalar()

        return result or 0

    def _row_to_working_tree_entry(self, row) -> WorkingTreeEntry:
        """Convert database row to WorkingTreeEntry instance."""
        return WorkingTreeEntry(
            entity_type=row[0],
            entity_id=row[1],
            current_version_id=row[2],
            canonical_version_id=row[3],
            staged=bool(row[4]),
            modified_at=datetime.fromisoformat(row[5].replace("Z", "+00:00")),
        )

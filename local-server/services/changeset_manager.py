"""
ChangesetManager Service - Manages changeset creation, modification, and lifecycle

This service handles the creation and management of changesets for collaborative workflows,
bundling related changes together for proposal and review processes.
"""

import uuid
import json
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.collaboration_models import (
    Changeset, ChangesetState, row_to_changeset
)
from services.version_manager import VersionManager
from services.working_tree_manager import WorkingTreeManager
from services.s3_sync_manager import S3SyncManager
from utils.logger import get_logger

logger = get_logger(__name__)


class ChangesetManager:
    """Manages changeset creation, modification, and lifecycle."""
    
    def __init__(self, db: Session, s3_sync_manager: S3SyncManager, 
                 working_tree_manager: WorkingTreeManager, version_manager: VersionManager):
        """
        Initialize the ChangesetManager.
        
        Args:
            db: SQLAlchemy database session
            s3_sync_manager: S3 synchronization manager
            working_tree_manager: Working tree state manager
            version_manager: Version management service
        """
        self.db = db
        self.s3_sync = s3_sync_manager
        self.working_tree = working_tree_manager
        self.version_manager = version_manager
        logger.info("ChangesetManager initialized")
    
    def create_changeset(self, title: str, description: str, author_id: str,
                        include_staged: bool = True) -> Changeset:
        """
        Create a new changeset from staged or all working changes.
        
        Args:
            title: Changeset title
            description: Detailed description
            author_id: Author identifier
            include_staged: If True, include only staged changes; if False, include all working changes
            
        Returns:
            Created Changeset instance
            
        Raises:
            ValueError: If no changes are available or validation fails
            RuntimeError: If database operation fails
        """
        logger.info(f"Creating changeset '{title}' by {author_id} (staged_only={include_staged})")
        
        changeset_id = str(uuid.uuid4())
        
        # Get changes to include
        if include_staged:
            changes = self.working_tree.get_staged_changes()
            logger.info(f"Found {len(changes)} staged changes")
        else:
            changes = self.working_tree.get_working_changes()
            logger.info(f"Found {len(changes)} working changes")
        
        if not changes:
            raise ValueError("No changes available to create changeset")
        
        # Create changeset record
        changeset = Changeset(
            id=changeset_id,
            title=title,
            description=description,
            state=ChangesetState.DRAFT,
            branch_name=None,
            parent_changeset_id=None,
            author_id=author_id,
            created_at=datetime.now(timezone.utc),
            metadata={"changes_count": len(changes)}
        )
        
        try:
            # Store changeset locally
            self._store_changeset_locally(changeset, changes)
            
            # Update version records with changeset_id
            self._associate_versions_with_changeset(changeset_id, changes)
            
            logger.info(f"Successfully created changeset {changeset_id} with {len(changes)} changes")
            return changeset
            
        except Exception as e:
            logger.error(f"Failed to create changeset: {e}")
            # Attempt cleanup
            try:
                self.db.execute(text("DELETE FROM changesets WHERE id = ?"), (changeset_id,))
                self.db.commit()
            except:
                pass
            raise RuntimeError(f"Failed to create changeset: {e}")
    
    def get_changeset(self, changeset_id: str) -> Optional[Changeset]:
        """
        Retrieve changeset by ID.
        
        Args:
            changeset_id: Changeset identifier
            
        Returns:
            Changeset instance or None if not found
        """
        logger.debug(f"Retrieving changeset {changeset_id}")
        
        try:
            result = self.db.execute(
                text("SELECT * FROM changesets WHERE id = ?"),
                (changeset_id,)
            ).fetchone()
            
            if not result:
                logger.debug(f"Changeset {changeset_id} not found")
                return None
                
            return row_to_changeset(result)
            
        except Exception as e:
            logger.error(f"Failed to retrieve changeset {changeset_id}: {e}")
            return None
    
    def list_changesets(self, author_id: Optional[str] = None, 
                       state: Optional[ChangesetState] = None,
                       limit: int = 100) -> List[Changeset]:
        """
        List changesets with optional filtering.
        
        Args:
            author_id: Filter by author ID
            state: Filter by changeset state
            limit: Maximum number of results
            
        Returns:
            List of Changeset instances
        """
        logger.debug(f"Listing changesets (author={author_id}, state={state}, limit={limit})")
        
        try:
            query = "SELECT * FROM changesets WHERE 1=1"
            params = []
            
            if author_id:
                query += " AND author_id = ?"
                params.append(author_id)
                
            if state:
                query += " AND state = ?"
                params.append(state.value)
                
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            results = self.db.execute(text(query), params).fetchall()
            changesets = [row_to_changeset(row) for row in results]
            
            logger.debug(f"Found {len(changesets)} changesets")
            return changesets
            
        except Exception as e:
            logger.error(f"Failed to list changesets: {e}")
            return []
    
    def update_changeset(self, changeset_id: str, title: Optional[str] = None,
                        description: Optional[str] = None) -> bool:
        """
        Update changeset metadata.
        
        Args:
            changeset_id: Changeset identifier
            title: New title (optional)
            description: New description (optional)
            
        Returns:
            True if updated successfully
        """
        logger.info(f"Updating changeset {changeset_id}")
        
        if not title and not description:
            logger.warning("No updates provided for changeset")
            return False
            
        try:
            updates = []
            params = []
            
            if title:
                updates.append("title = ?")
                params.append(title)
                
            if description:
                updates.append("description = ?")
                params.append(description)
                
            params.append(changeset_id)
            query = f"UPDATE changesets SET {', '.join(updates)} WHERE id = ?"
            
            cursor = self.db.execute(text(query), params)
            self.db.commit()
            
            if cursor.rowcount == 0:
                logger.warning(f"No changeset found with ID {changeset_id}")
                return False
                
            logger.info(f"Successfully updated changeset {changeset_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update changeset {changeset_id}: {e}")
            self.db.rollback()
            return False
    
    def update_changeset_state(self, changeset_id: str, new_state: ChangesetState) -> bool:
        """
        Update changeset state.
        
        Args:
            changeset_id: Changeset identifier
            new_state: New state
            
        Returns:
            True if updated successfully
        """
        logger.info(f"Updating changeset {changeset_id} state to {new_state.value}")
        
        try:
            # If transitioning to MERGED, record merge timestamp
            if new_state == ChangesetState.MERGED:
                query = "UPDATE changesets SET state = ?, merged_at = ? WHERE id = ?"
                params = (new_state.value, datetime.now(timezone.utc).isoformat(), changeset_id)
            else:
                query = "UPDATE changesets SET state = ? WHERE id = ?"
                params = (new_state.value, changeset_id)
            
            cursor = self.db.execute(text(query), params)
            self.db.commit()
            
            if cursor.rowcount == 0:
                logger.warning(f"No changeset found with ID {changeset_id}")
                return False
                
            logger.info(f"Successfully updated changeset {changeset_id} state to {new_state.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update changeset {changeset_id} state: {e}")
            self.db.rollback()
            return False
    
    def get_changeset_versions(self, changeset_id: str) -> List[str]:
        """
        Get all version IDs associated with a changeset.
        
        Args:
            changeset_id: Changeset identifier
            
        Returns:
            List of version IDs
        """
        logger.debug(f"Getting versions for changeset {changeset_id}")
        
        try:
            results = self.db.execute(
                text("SELECT id FROM entity_versions WHERE changeset_id = ?"),
                (changeset_id,)
            ).fetchall()
            
            version_ids = [row[0] for row in results]
            logger.debug(f"Found {len(version_ids)} versions for changeset {changeset_id}")
            return version_ids
            
        except Exception as e:
            logger.error(f"Failed to get versions for changeset {changeset_id}: {e}")
            return []
    
    def delete_changeset(self, changeset_id: str) -> bool:
        """
        Delete a changeset and disassociate its versions.
        
        Args:
            changeset_id: Changeset identifier
            
        Returns:
            True if deleted successfully
        """
        logger.info(f"Deleting changeset {changeset_id}")
        
        try:
            # Check if changeset exists
            changeset = self.get_changeset(changeset_id)
            if not changeset:
                logger.warning(f"Changeset {changeset_id} not found")
                return False
                
            # Don't allow deletion of merged changesets
            if changeset.state == ChangesetState.MERGED:
                logger.warning(f"Cannot delete merged changeset {changeset_id}")
                raise ValueError("Cannot delete merged changeset")
            
            # Remove changeset association from versions
            self.db.execute(
                text("UPDATE entity_versions SET changeset_id = NULL WHERE changeset_id = ?"),
                (changeset_id,)
            )
            
            # Delete the changeset
            cursor = self.db.execute(
                text("DELETE FROM changesets WHERE id = ?"),
                (changeset_id,)
            )
            
            self.db.commit()
            
            if cursor.rowcount == 0:
                logger.warning(f"No changeset deleted for ID {changeset_id}")
                return False
                
            logger.info(f"Successfully deleted changeset {changeset_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete changeset {changeset_id}: {e}")
            self.db.rollback()
            raise RuntimeError(f"Failed to delete changeset: {e}")
    
    def _store_changeset_locally(self, changeset: Changeset, changes: List) -> None:
        """
        Store changeset in local SQLite database.
        
        Args:
            changeset: Changeset instance to store
            changes: List of changes associated with changeset
        """
        logger.debug(f"Storing changeset {changeset.id} locally")
        
        query = """
        INSERT INTO changesets (
            id, title, description, state, branch_name, parent_changeset_id,
            author_id, created_at, merged_at, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            changeset.id, changeset.title, changeset.description,
            changeset.state.value, changeset.branch_name, changeset.parent_changeset_id,
            changeset.author_id, changeset.created_at.isoformat(),
            changeset.merged_at.isoformat() if changeset.merged_at else None,
            json.dumps(changeset.metadata) if changeset.metadata else None
        )
        
        self.db.execute(text(query), params)
        logger.debug(f"Stored changeset {changeset.id} in database")
    
    def _associate_versions_with_changeset(self, changeset_id: str, changes: List) -> None:
        """
        Associate version records with changeset.
        
        Args:
            changeset_id: Changeset identifier
            changes: List of working tree entries with changes
        """
        logger.debug(f"Associating {len(changes)} versions with changeset {changeset_id}")
        
        try:
            # Update current versions of changed entities to associate with changeset
            for change in changes:
                self.db.execute(
                    text("""
                        UPDATE entity_versions 
                        SET changeset_id = ? 
                        WHERE id = ?
                    """),
                    (changeset_id, change.current_version_id)
                )
            
            logger.debug(f"Successfully associated versions with changeset {changeset_id}")
            
        except Exception as e:
            logger.error(f"Failed to associate versions with changeset {changeset_id}: {e}")
            raise
    
    def push_changeset_to_s3(self, changeset_id: str) -> bool:
        """
        Push changeset data to S3 for collaboration.
        
        Args:
            changeset_id: Changeset identifier
            
        Returns:
            True if pushed successfully
        """
        logger.info(f"Pushing changeset {changeset_id} to S3")
        
        try:
            changeset = self.get_changeset(changeset_id)
            if not changeset:
                raise ValueError(f"Changeset {changeset_id} not found")
            
            # Get associated versions
            version_ids = self.get_changeset_versions(changeset_id)
            
            # Prepare changeset data for S3
            changeset_data = changeset.to_dict()
            changeset_data["version_ids"] = version_ids
            
            # Push to S3 (using parquet format)
            s3_path = f"s3://{self.s3_sync.s3_config['bucket']}/changesets/{changeset_id}/metadata.parquet"
            
            # Use S3 sync manager to write changeset metadata
            self.s3_sync.parquet_writer.write_metadata(changeset_data, s3_path)
            
            logger.info(f"Successfully pushed changeset {changeset_id} to S3")
            return True
            
        except Exception as e:
            logger.error(f"Failed to push changeset {changeset_id} to S3: {e}")
            return False
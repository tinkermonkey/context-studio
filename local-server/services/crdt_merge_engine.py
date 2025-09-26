"""
CRDTMergeEngine Service - Handles conflict-free replicated data type merging

This service implements CRDT semantics for merging approved changes,
providing automatic conflict resolution for collaborative workflows.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from dataclasses import dataclass
from enum import Enum

from services.collaboration_models import CRDTConflictError, ChangesetState
from services.version_manager import VersionManager, EntityVersion, ChangeState
from services.changeset_manager import ChangesetManager
from utils.logger import get_logger

logger = get_logger(__name__)


class MergeStrategy(Enum):
    """Strategy for resolving merge conflicts."""
    LAST_WRITER_WINS = "last_writer_wins"
    MERGE_BOTH = "merge_both"
    AUTHOR_PRIORITY = "author_priority"
    MANUAL_RESOLUTION = "manual_resolution"


@dataclass
class MergeResult:
    """Result of a merge operation."""
    entity_type: str
    entity_id: str
    merged_version_id: Optional[str]
    status: str  # 'success', 'conflict', 'error'
    error_message: Optional[str] = None
    conflicts: Optional[List[str]] = None


@dataclass  
class ChangesetMergeResult:
    """Result of merging an entire changeset."""
    changeset_id: str
    merged_entities: int
    conflicts: int
    results: List[MergeResult]
    conflict_details: List[Dict[str, Any]]
    merge_commit_id: Optional[str] = None


class CRDTMergeEngine:
    """Handles conflict-free replicated data type merging for approved changes."""
    
    def __init__(self, db: Session, version_manager: VersionManager, 
                 changeset_manager: ChangesetManager):
        """
        Initialize the CRDTMergeEngine.
        
        Args:
            db: SQLAlchemy database session
            version_manager: Version management service
            changeset_manager: Changeset management service
        """
        self.db = db
        self.version_manager = version_manager
        self.changeset_manager = changeset_manager
        logger.info("CRDTMergeEngine initialized")
    
    def merge_changeset(self, changeset_id: str, merge_author: str) -> ChangesetMergeResult:
        """
        Merge approved changeset using CRDT semantics.
        
        Args:
            changeset_id: ID of approved changeset to merge
            merge_author: User ID performing the merge
            
        Returns:
            ChangesetMergeResult with merge details
            
        Raises:
            ValueError: If changeset not found or not in correct state
            RuntimeError: If merge operation fails
        """
        logger.info(f"Merging changeset {changeset_id} by {merge_author}")
        
        changeset = self.changeset_manager.get_changeset(changeset_id)
        if not changeset:
            raise ValueError(f"Changeset {changeset_id} not found")
            
        if changeset.state != ChangesetState.APPROVED:
            raise ValueError(f"Cannot merge changeset in {changeset.state.value} state")
            
        try:
            # Get all versions in changeset
            changeset_versions = self._get_changeset_versions(changeset_id)
            logger.info(f"Found {len(changeset_versions)} versions to merge in changeset {changeset_id}")
            
            # Group by entity for merge processing
            entities_to_merge = self._group_versions_by_entity(changeset_versions)
            logger.info(f"Grouped into {len(entities_to_merge)} entities to merge")
            
            merge_results = []
            conflicts = []
            
            # Process each entity
            for (entity_type, entity_id), versions in entities_to_merge.items():
                logger.debug(f"Processing entity {entity_type}:{entity_id} with {len(versions)} versions")
                
                try:
                    # Get current canonical version
                    canonical = self._get_canonical_version(entity_type, entity_id)
                    
                    # Apply CRDT merge for each version
                    merged_content = self._apply_crdt_merge(canonical, versions)
                    
                    # Create merged version
                    merged_version = self.version_manager.create_version(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        content=merged_content,
                        author_id=merge_author,
                        state=ChangeState.MERGED,
                        changeset_id=changeset_id,
                        metadata={"merge_source": "crdt_auto_merge", "source_versions": [v.id for v in versions]}
                    )
                    
                    # Update canonical reference
                    self._update_canonical_version(entity_type, entity_id, merged_version.id)
                    
                    merge_results.append(MergeResult(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        merged_version_id=merged_version.id,
                        status="success"
                    ))
                    
                    logger.debug(f"Successfully merged entity {entity_type}:{entity_id}")
                    
                except CRDTConflictError as e:
                    logger.warning(f"CRDT conflict for entity {entity_type}:{entity_id}: {e}")
                    conflicts.append({
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "error": str(e),
                        "requires_manual_resolution": True
                    })
                    
                    merge_results.append(MergeResult(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        merged_version_id=None,
                        status="conflict",
                        error_message=str(e),
                        conflicts=[str(e)]
                    ))
                    
                except Exception as e:
                    logger.error(f"Error merging entity {entity_type}:{entity_id}: {e}")
                    conflicts.append({
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "error": str(e),
                        "requires_manual_resolution": True
                    })
                    
                    merge_results.append(MergeResult(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        merged_version_id=None,
                        status="error",
                        error_message=str(e)
                    ))
            
            # Update changeset state
            if not conflicts:
                self.changeset_manager.update_changeset_state(changeset_id, ChangesetState.MERGED)
                logger.info(f"Successfully merged changeset {changeset_id} with no conflicts")
            else:
                logger.warning(f"Changeset {changeset_id} merge completed with {len(conflicts)} conflicts")
            
            # Commit all changes
            self.db.commit()
            
            result = ChangesetMergeResult(
                changeset_id=changeset_id,
                merged_entities=len([r for r in merge_results if r.status == "success"]),
                conflicts=len(conflicts),
                results=merge_results,
                conflict_details=conflicts
            )
            
            logger.info(f"Changeset {changeset_id} merge completed: {result.merged_entities} merged, {result.conflicts} conflicts")
            return result
            
        except Exception as e:
            logger.error(f"Failed to merge changeset {changeset_id}: {e}")
            self.db.rollback()
            raise RuntimeError(f"Failed to merge changeset: {e}")
    
    def resolve_conflict(self, entity_type: str, entity_id: str, resolution_content: Dict[str, Any],
                        resolver_id: str) -> EntityVersion:
        """
        Manually resolve a merge conflict.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            resolution_content: Resolved content
            resolver_id: User ID who resolved the conflict
            
        Returns:
            New EntityVersion with resolved content
        """
        logger.info(f"Manually resolving conflict for {entity_type}:{entity_id} by {resolver_id}")
        
        try:
            # Create resolution version
            resolved_version = self.version_manager.create_version(
                entity_type=entity_type,
                entity_id=entity_id,
                content=resolution_content,
                author_id=resolver_id,
                state=ChangeState.MERGED,
                metadata={"merge_source": "manual_resolution"}
            )
            
            # Update canonical reference
            self._update_canonical_version(entity_type, entity_id, resolved_version.id)
            
            self.db.commit()
            
            logger.info(f"Successfully resolved conflict for {entity_type}:{entity_id}")
            return resolved_version
            
        except Exception as e:
            logger.error(f"Failed to resolve conflict for {entity_type}:{entity_id}: {e}")
            self.db.rollback()
            raise RuntimeError(f"Failed to resolve conflict: {e}")
    
    def _get_changeset_versions(self, changeset_id: str) -> List[EntityVersion]:
        """
        Get all versions associated with a changeset.
        
        Args:
            changeset_id: Changeset identifier
            
        Returns:
            List of EntityVersion instances
        """
        logger.debug(f"Getting versions for changeset {changeset_id}")
        
        try:
            results = self.db.execute(
                text("""
                    SELECT id, entity_type, entity_id, version_number, content, state,
                           parent_version_id, changeset_id, author_id, created_at, metadata
                    FROM entity_versions
                    WHERE changeset_id = :changeset_id
                    ORDER BY entity_type, entity_id, version_number
                """),
                {"changeset_id": changeset_id}
            ).fetchall()
            
            versions = []
            for row in results:
                import json
                versions.append(EntityVersion(
                    id=row[0],
                    entity_type=row[1],
                    entity_id=row[2],
                    version_number=row[3],
                    content=json.loads(row[4]),
                    state=ChangeState(row[5]),
                    parent_version_id=row[6],
                    changeset_id=row[7],
                    author_id=row[8],
                    created_at=datetime.fromisoformat(row[9]),
                    metadata=json.loads(row[10]) if row[10] else None
                ))
            
            logger.debug(f"Found {len(versions)} versions for changeset {changeset_id}")
            return versions
            
        except Exception as e:
            logger.error(f"Failed to get versions for changeset {changeset_id}: {e}")
            return []
    
    def _group_versions_by_entity(self, versions: List[EntityVersion]) -> Dict[Tuple[str, str], List[EntityVersion]]:
        """
        Group versions by entity (type, id).
        
        Args:
            versions: List of EntityVersion instances
            
        Returns:
            Dictionary mapping (entity_type, entity_id) to list of versions
        """
        entities_to_merge = {}
        
        for version in versions:
            key = (version.entity_type, version.entity_id)
            if key not in entities_to_merge:
                entities_to_merge[key] = []
            entities_to_merge[key].append(version)
        
        # Sort versions by version_number within each entity
        for key in entities_to_merge:
            entities_to_merge[key].sort(key=lambda v: v.version_number)
        
        return entities_to_merge
    
    def _get_canonical_version(self, entity_type: str, entity_id: str) -> Optional[EntityVersion]:
        """
        Get current canonical version for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            
        Returns:
            Current canonical EntityVersion or None if not found
        """
        logger.debug(f"Getting canonical version for {entity_type}:{entity_id}")
        
        try:
            # Get canonical version ID from working tree
            result = self.db.execute(
                text("""
                    SELECT canonical_version_id FROM working_tree
                    WHERE entity_type = :entity_type AND entity_id = :entity_id
                """),
                {"entity_type": entity_type, "entity_id": entity_id}
            ).fetchone()
            
            if not result:
                logger.debug(f"No canonical version found for {entity_type}:{entity_id}")
                return None
            
            canonical_version_id = result[0]
            
            # Get version details
            version_result = self.db.execute(
                text("""
                    SELECT id, entity_type, entity_id, version_number, content, state,
                           parent_version_id, changeset_id, author_id, created_at, metadata
                    FROM entity_versions
                    WHERE id = :id
                """),
                {"id": canonical_version_id}
            ).fetchone()
            
            if not version_result:
                logger.warning(f"Canonical version {canonical_version_id} not found for {entity_type}:{entity_id}")
                return None
            
            import json
            row = version_result
            return EntityVersion(
                id=row[0],
                entity_type=row[1],
                entity_id=row[2],
                version_number=row[3],
                content=json.loads(row[4]),
                state=ChangeState(row[5]),
                parent_version_id=row[6],
                changeset_id=row[7],
                author_id=row[8],
                created_at=datetime.fromisoformat(row[9]),
                metadata=json.loads(row[10]) if row[10] else None
            )
            
        except Exception as e:
            logger.error(f"Failed to get canonical version for {entity_type}:{entity_id}: {e}")
            return None
    
    def _apply_crdt_merge(self, canonical_version: Optional[EntityVersion], 
                         changeset_versions: List[EntityVersion]) -> Dict[str, Any]:
        """
        Apply CRDT merge logic to combine versions.
        
        Args:
            canonical_version: Current canonical version (base)
            changeset_versions: Versions to merge in
            
        Returns:
            Merged content dictionary
            
        Raises:
            CRDTConflictError: If conflicts cannot be automatically resolved
        """
        logger.debug(f"Applying CRDT merge to {len(changeset_versions)} versions")
        
        if not canonical_version:
            # New entity, use latest version
            if changeset_versions:
                logger.debug("New entity, using latest version")
                return changeset_versions[-1].content
            else:
                raise CRDTConflictError("No versions to merge")
        
        base_content = canonical_version.content.copy()
        merged_content = base_content.copy()
        
        # Apply each changeset version in order
        for version in changeset_versions:
            try:
                merged_content = self._merge_content_crdt(merged_content, version.content)
            except CRDTConflictError:
                # Re-raise CRDT conflicts
                raise
            except Exception as e:
                raise CRDTConflictError(f"Failed to merge version {version.id}: {e}")
        
        logger.debug("CRDT merge completed successfully")
        return merged_content
    
    def _merge_content_crdt(self, base: Dict[str, Any], changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two content objects using CRDT semantics.
        
        Args:
            base: Base content object
            changes: Changes to merge in
            
        Returns:
            Merged content object
            
        Raises:
            CRDTConflictError: If unresolvable conflicts are detected
        """
        result = base.copy()
        conflicting_fields = []
        
        for key, value in changes.items():
            if key not in result:
                # New field, add it (last-writer-wins for new fields)
                result[key] = value
                
            elif isinstance(value, dict) and isinstance(result[key], dict):
                # Nested object, recursively merge
                try:
                    result[key] = self._merge_content_crdt(result[key], value)
                except CRDTConflictError as e:
                    conflicting_fields.append(f"{key}.{str(e)}")
                    
            elif isinstance(value, list) and isinstance(result[key], list):
                # List merge - union with deduplication (set-based CRDT)
                combined = result[key].copy()
                for item in value:
                    if item not in combined:
                        combined.append(item)
                result[key] = combined
                
            elif result[key] == value:
                # Same value, no conflict
                continue
                
            else:
                # Scalar conflict - check for resolvable patterns
                if self._can_resolve_scalar_conflict(key, result[key], value):
                    result[key] = self._resolve_scalar_conflict(key, result[key], value)
                else:
                    conflicting_fields.append(f"{key}: {result[key]} vs {value}")
        
        if conflicting_fields:
            raise CRDTConflictError(f"Unresolvable conflicts in fields: {', '.join(conflicting_fields)}")
        
        return result
    
    def _can_resolve_scalar_conflict(self, field: str, base_value: Any, change_value: Any) -> bool:
        """
        Check if a scalar field conflict can be automatically resolved.
        
        Args:
            field: Field name
            base_value: Base value
            change_value: Conflicting value
            
        Returns:
            True if conflict can be auto-resolved
        """
        # For timestamps, use latest (last-writer-wins)
        if field.endswith('_at') or field.endswith('_time') or 'timestamp' in field.lower():
            return True
            
        # For counters or numeric fields, use maximum
        if isinstance(base_value, (int, float)) and isinstance(change_value, (int, float)):
            if field.endswith('_count') or field.endswith('_number') or 'version' in field.lower():
                return True
        
        # For boolean flags, use OR (true wins)
        if isinstance(base_value, bool) and isinstance(change_value, bool):
            return True
            
        return False
    
    def _resolve_scalar_conflict(self, field: str, base_value: Any, change_value: Any) -> Any:
        """
        Resolve a scalar field conflict automatically.
        
        Args:
            field: Field name
            base_value: Base value  
            change_value: Conflicting value
            
        Returns:
            Resolved value
        """
        # For timestamps, use latest
        if field.endswith('_at') or field.endswith('_time') or 'timestamp' in field.lower():
            if isinstance(base_value, str) and isinstance(change_value, str):
                return max(base_value, change_value)  # String comparison for ISO timestamps
            return change_value  # Default to change value
            
        # For counters, use maximum
        if isinstance(base_value, (int, float)) and isinstance(change_value, (int, float)):
            return max(base_value, change_value)
            
        # For booleans, use OR (true wins)
        if isinstance(base_value, bool) and isinstance(change_value, bool):
            return base_value or change_value
            
        # Default to change value (last-writer-wins)
        return change_value
    
    def _update_canonical_version(self, entity_type: str, entity_id: str, version_id: str) -> None:
        """
        Update canonical version reference in working tree.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            version_id: New canonical version ID
        """
        logger.debug(f"Updating canonical version for {entity_type}:{entity_id} to {version_id}")
        
        try:
            self.db.execute(
                text("""
                    UPDATE working_tree
                    SET canonical_version_id = :canonical_version_id, current_version_id = :current_version_id, modified_at = :modified_at
                    WHERE entity_type = :entity_type AND entity_id = :entity_id
                """),
                {
                    "canonical_version_id": version_id,
                    "current_version_id": version_id,
                    "modified_at": datetime.now(timezone.utc).isoformat(),
                    "entity_type": entity_type,
                    "entity_id": entity_id
                }
            )
            
            logger.debug(f"Updated canonical version for {entity_type}:{entity_id}")
            
        except Exception as e:
            logger.error(f"Failed to update canonical version for {entity_type}:{entity_id}: {e}")
            raise
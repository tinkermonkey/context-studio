# mypy: ignore-errors
"""
Version Management API Endpoints

This module implements the version management API endpoints for entity versioning,
working tree state management, diff generation, and rollback capabilities.

Endpoints:
- GET /api/versions/entities/{entity_type}/{entity_id}/versions - Get version history for an entity
- GET /api/versions/entities/{entity_type}/{entity_id}/versions/{version_number} - Get specific version
- POST /api/versions/entities/{entity_type}/{entity_id}/rollback - Rollback entity to specific version
- GET /api/versions/entities/{entity_type}/{entity_id}/diff - Get working diff for entity
- GET /api/versions/working-tree/status - Get working tree status
- GET /api/versions/working-tree/changes - Get all working changes
- POST /api/versions/working-tree/stage - Stage entity for commit
- POST /api/versions/working-tree/unstage - Unstage entity
- POST /api/versions/working-tree/commit - Commit staged changes
- GET /api/versions/working-tree/preview - Preview what would be committed
- GET /api/versions/diffs/working - Get all working diffs
- POST /api/versions/diffs/compare - Compare two specific versions
- GET /api/versions/health - Get version management system health
- GET /api/versions/stats - Get version management statistics
"""

import logging
from fastapi import APIRouter, HTTPException, Query, Depends, Path
from typing import List
from uuid import UUID
from sqlalchemy import text

from services.version_manager import VersionManager, EntityVersion
from services.working_tree_manager import WorkingTreeManager
from services.diff_generator import DiffGenerator
from services.service_factory import (
    get_version_manager_via_factory,
    get_working_tree_manager_via_factory,
    get_diff_generator_via_factory
)
from api.models.version_management import (
    EntityVersionOut, EntityVersionSummary, WorkingTreeStatusOut, WorkingTreeEntryOut,
    EntityDiffOut, DiffSummaryOut, RollbackRequest, CommitRequest,
    StageRequest, DiffRequest, DiffFormatEnum, VersionManagementHealthOut, VersionManagementStatsOut,
    EntityTypeEnum, ChangeStateEnum
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/versions", tags=["version_management"])


@router.get("/entities/{entity_type}/{entity_id}/versions", response_model=List[EntityVersionSummary])
def get_entity_versions(
    entity_type: EntityTypeEnum = Path(..., description="Entity type"),
    entity_id: UUID = Path(..., description="Entity ID"),
    version_manager: VersionManager = Depends(get_version_manager_via_factory)
):
    """
    Get version history for an entity.
    
    Returns all versions of the specified entity ordered by version number.
    """
    try:
        versions = version_manager.get_entity_versions(entity_type.value, str(entity_id))
        return [_entity_version_to_summary(version) for version in versions]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve versions: {str(e)}")


@router.get("/entities/{entity_type}/{entity_id}/versions/{version_number}", response_model=EntityVersionOut)
def get_entity_version(
    entity_type: EntityTypeEnum = Path(..., description="Entity type"),
    entity_id: UUID = Path(..., description="Entity ID"),
    version_number: int = Path(..., ge=1, description="Version number"),
    version_manager: VersionManager = Depends(get_version_manager_via_factory)
):
    """
    Get specific version of an entity.
    
    Returns the full content and metadata for the specified version.
    """
    try:
        version = version_manager.get_version_by_number(entity_type.value, str(entity_id), version_number)
        if not version:
            raise HTTPException(status_code=404, detail=f"Version {version_number} not found")
        
        return _entity_version_to_out(version)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve version: {str(e)}")


@router.post("/entities/{entity_type}/{entity_id}/rollback")
def rollback_entity(
    rollback_request: RollbackRequest,
    entity_type: EntityTypeEnum = Path(..., description="Entity type"),
    entity_id: UUID = Path(..., description="Entity ID"),
    version_manager: VersionManager = Depends(get_version_manager_via_factory)
):
    """
    Rollback entity to specific version.

    Creates a new version with the content from the target version.
    Note: This currently only creates a version record. Entity content rollback
    requires additional implementation.
    """
    try:
        rollback_version = version_manager.rollback_to_version(
            entity_type.value,
            str(entity_id),
            rollback_request.target_version_number,
            rollback_request.author_id
        )

        return {"success": True, "version": _entity_version_to_out(rollback_version)}

    except ValueError as e:
        # Check if error message indicates entity/version not found
        error_msg = str(e).lower()
        if "not found" in error_msg or "does not exist" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")


@router.get("/entities/{entity_type}/{entity_id}/diff")
def get_working_diff(
    entity_type: EntityTypeEnum = Path(..., description="Entity type"),
    entity_id: UUID = Path(..., description="Entity ID"),
    format: DiffFormatEnum = Query(DiffFormatEnum.SUMMARY, description="Diff format"),
    diff_generator: DiffGenerator = Depends(get_diff_generator_via_factory)
):
    """
    Get diff between working and canonical versions.

    Shows what changes exist in the working version compared to the last committed version.
    """
    try:
        diff = diff_generator.generate_working_diff(entity_type.value, str(entity_id))
        diff_out = _entity_diff_to_out(diff)
        # Add diff field that tests expect (alias for changes)
        response = diff_out.dict()
        response["diff"] = response["changes"]
        return response

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate diff: {str(e)}")


@router.get("/working-tree/status", response_model=WorkingTreeStatusOut)
def get_working_tree_status(
    working_tree_manager: WorkingTreeManager = Depends(get_working_tree_manager_via_factory)
):
    """
    Get working tree status.
    
    Returns summary of all entities in the working tree including staged/unstaged counts.
    """
    try:
        status = working_tree_manager.get_working_tree_status()
        return WorkingTreeStatusOut(
            total_entities=status.total_entities,
            modified_entities=status.modified_entities,
            staged_entities=status.staged_entities,
            unstaged_entities=status.unstaged_entities,
            entries=[_working_tree_entry_to_out(entry) for entry in status.entries]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get working tree status: {str(e)}")


@router.get("/working-tree/changes", response_model=List[WorkingTreeEntryOut])
def get_working_changes(
    working_tree_manager: WorkingTreeManager = Depends(get_working_tree_manager_via_factory)
):
    """
    Get all entities with working changes.
    
    Returns entities where the working version differs from the canonical version.
    """
    try:
        changes = working_tree_manager.get_working_changes()
        return [_working_tree_entry_to_out(entry) for entry in changes]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get working changes: {str(e)}")


@router.post("/working-tree/stage")
def stage_entity(
    stage_request: StageRequest,
    working_tree_manager: WorkingTreeManager = Depends(get_working_tree_manager_via_factory)
):
    """
    Stage an entity for commit.

    Marks the entity as staged, meaning its changes will be included in the next commit.
    Returns success even if there are no changes (idempotent operation).
    """
    try:
        success = working_tree_manager.stage_entity(
            stage_request.entity_type.value,
            str(stage_request.entity_id)
        )

        # Return success even if no changes - staging is idempotent
        message = "Entity staged successfully" if success else "No changes to stage"

        return {"success": True, "message": message}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stage entity: {str(e)}")


@router.post("/working-tree/unstage")
def unstage_entity(
    stage_request: StageRequest,
    working_tree_manager: WorkingTreeManager = Depends(get_working_tree_manager_via_factory)
):
    """
    Unstage an entity.
    
    Removes the entity from the staged list, but keeps working changes.
    """
    try:
        working_tree_manager.unstage_entity(
            stage_request.entity_type.value,
            str(stage_request.entity_id)
        )

        return {"success": True, "message": "Entity unstaged successfully"}
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unstage entity: {str(e)}")


@router.post("/working-tree/commit")
def commit_staged_changes(
    commit_request: CommitRequest,
    working_tree_manager: WorkingTreeManager = Depends(get_working_tree_manager_via_factory)
):
    """
    Commit all staged changes.

    Updates canonical versions for all staged entities and marks them as merged.
    Returns 400 if there are no staged changes to commit.
    """
    try:
        committed_versions = working_tree_manager.commit_staged_changes(commit_request.author_id)

        # Return 400 if nothing to commit
        if not committed_versions:
            raise HTTPException(status_code=400, detail="No staged changes to commit")

        return {
            "success": True,
            "committed_count": len(committed_versions),
            "versions": [_entity_version_to_summary(version) for version in committed_versions]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to commit changes: {str(e)}")


@router.get("/working-tree/preview", response_model=List[EntityDiffOut])
def get_commit_preview(
    diff_generator: DiffGenerator = Depends(get_diff_generator_via_factory)
):
    """
    Preview what would be committed.

    Returns diffs for all staged entities showing what changes would be committed.
    """
    try:
        diffs = diff_generator.generate_commit_preview()
        return [_entity_diff_to_out(diff) for diff in diffs]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate commit preview: {str(e)}")


@router.get("/diffs/working", response_model=List[EntityDiffOut])
def get_all_working_diffs(
    diff_generator: DiffGenerator = Depends(get_diff_generator_via_factory)
):
    """
    Get diffs for all entities with working changes.
    
    Returns structured diffs showing what has changed in the working versions.
    """
    try:
        diffs = diff_generator.generate_all_working_diffs()
        return [_entity_diff_to_out(diff) for diff in diffs]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate working diffs: {str(e)}")


@router.post("/diffs/compare")
def compare_versions(
    diff_request: DiffRequest,
    diff_generator: DiffGenerator = Depends(get_diff_generator_via_factory)
):
    """
    Compare two specific versions of an entity.
    
    Generates a structured diff between the specified before and after versions.
    """
    try:
        diff = diff_generator.generate_version_diff(
            diff_request.entity_type.value,
            str(diff_request.entity_id),
            diff_request.before_version_number,
            diff_request.after_version_number
        )

        diff_out = _entity_diff_to_out(diff)
        # Add diff field that tests expect (alias for changes)
        response = diff_out.dict()
        response["diff"] = response["changes"]
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare versions: {str(e)}")


@router.get("/health", response_model=VersionManagementHealthOut)
def get_version_management_health(
    version_manager: VersionManager = Depends(get_version_manager_via_factory),
    working_tree_manager: WorkingTreeManager = Depends(get_working_tree_manager_via_factory)
):
    """
    Get version management system health status.
    
    Returns overall health, counts, and any issues detected.
    """
    try:
        # Get basic statistics using the version manager's database session
        db = version_manager.db
        
        total_versions = db.execute(text("SELECT COUNT(*) FROM entity_versions")).scalar() or 0
        total_working_entries = db.execute(text("SELECT COUNT(*) FROM working_tree")).scalar() or 0
        staged_entities = db.execute(text("SELECT COUNT(*) FROM working_tree WHERE staged = 1")).scalar() or 0
        modified_entities = db.execute(text("SELECT COUNT(*) FROM working_tree WHERE current_version_id != canonical_version_id")).scalar() or 0
        
        # Check for issues
        issues = []
        status = "healthy"
        
        # Check for orphaned versions
        orphaned_versions = db.execute(text("""
            SELECT COUNT(*) FROM entity_versions ev
            LEFT JOIN entity_versions parent ON ev.parent_version_id = parent.id
            WHERE ev.parent_version_id IS NOT NULL AND parent.id IS NULL
        """)).scalar() or 0
        
        if orphaned_versions > 0:
            issues.append(f"{orphaned_versions} orphaned versions found")
            status = "warning"
        
        # Check for inconsistent working tree
        inconsistent_entries = db.execute(text("""
            SELECT COUNT(*) FROM working_tree wt
            LEFT JOIN entity_versions ev ON wt.current_version_id = ev.id
            WHERE ev.id IS NULL
        """)).scalar() or 0
        
        if inconsistent_entries > 0:
            issues.append(f"{inconsistent_entries} working tree entries reference missing versions")
            status = "error"
        
        return VersionManagementHealthOut(
            status=status,
            total_versions=total_versions,
            total_working_tree_entries=total_working_entries,
            total_staged_entities=staged_entities,
            total_modified_entities=modified_entities,
            issues=issues,
            database_status="connected"
        )
        
    except Exception as e:
        return VersionManagementHealthOut(
            status="error",
            total_versions=0,
            total_working_tree_entries=0,
            total_staged_entities=0,
            total_modified_entities=0,
            issues=[f"Health check failed: {str(e)}"],
            database_status="error"
        )


@router.get("/stats", response_model=VersionManagementStatsOut)
def get_version_management_stats(
    version_manager: VersionManager = Depends(get_version_manager_via_factory),
    working_tree_manager: WorkingTreeManager = Depends(get_working_tree_manager_via_factory)
):
    """
    Get version management system statistics.
    
    Returns detailed statistics including version counts by type and state,
    working tree summary, recent activity, and performance metrics.
    """
    try:
        # Get basic version statistics
        db = version_manager.db
        
        # Count versions by entity type
        versions_by_type = {}
        type_results = db.execute(text("""
            SELECT entity_type, COUNT(*) as count
            FROM entity_versions 
            GROUP BY entity_type
        """)).fetchall()
        
        for entity_type, count in type_results:
            versions_by_type[entity_type] = count
        
        # Count versions by state
        versions_by_state = {}
        state_results = db.execute(text("""
            SELECT state, COUNT(*) as count
            FROM entity_versions 
            GROUP BY state
        """)).fetchall()
        
        for state, count in state_results:
            versions_by_state[state] = count
        
        # Get working tree status and convert to API model
        working_tree_status_raw = working_tree_manager.get_working_tree_status()
        working_tree_status = WorkingTreeStatusOut(
            total_entities=working_tree_status_raw.total_entities,
            modified_entities=working_tree_status_raw.modified_entities,
            staged_entities=working_tree_status_raw.staged_entities,
            unstaged_entities=working_tree_status_raw.unstaged_entities,
            entries=[_working_tree_entry_to_out(entry) for entry in working_tree_status_raw.entries]
        )
        
        # Get recent activity (last 10 versions created)
        recent_activity = []
        recent_results = db.execute(text("""
            SELECT entity_type, entity_id, version_number, state, author_id, created_at
            FROM entity_versions 
            ORDER BY created_at DESC 
            LIMIT 10
        """)).fetchall()
        
        for result in recent_results:
            recent_activity.append({
                "entity_type": result[0],
                "entity_id": result[1],
                "version_number": result[2],
                "state": result[3],
                "author_id": result[4],
                "created_at": result[5]
            })
        
        # Performance metrics (basic for now)
        performance_metrics = {
            "avg_versions_per_entity": 0,
            "largest_version_count": 0,
            "total_storage_mb": 0  # Would need to calculate actual storage
        }
        
        # Calculate average versions per entity
        total_versions = sum(versions_by_type.values())
        unique_entities = db.execute(text("""
            SELECT COUNT(DISTINCT entity_type || ':' || entity_id) 
            FROM entity_versions
        """)).scalar() or 0
        
        if unique_entities > 0:
            performance_metrics["avg_versions_per_entity"] = round(total_versions / unique_entities, 2)
        
        # Find entity with most versions
        max_versions = db.execute(text("""
            SELECT MAX(version_count) FROM (
                SELECT COUNT(*) as version_count
                FROM entity_versions 
                GROUP BY entity_type, entity_id
            )
        """)).scalar() or 0
        
        performance_metrics["largest_version_count"] = max_versions
        
        return VersionManagementStatsOut(
            versions_by_entity_type=versions_by_type,
            versions_by_state=versions_by_state,
            working_tree_summary=working_tree_status,
            recent_activity=recent_activity,
            performance_metrics=performance_metrics
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")


# Helper functions for data conversion

def _entity_version_to_out(version: EntityVersion) -> EntityVersionOut:
    """Convert EntityVersion to API output model."""
    return EntityVersionOut(
        id=version.id,
        entity_type=EntityTypeEnum(version.entity_type),
        entity_id=UUID(version.entity_id),
        version_number=version.version_number,
        content=version.content,
        state=ChangeStateEnum(version.state.value),
        parent_version_id=UUID(version.parent_version_id) if version.parent_version_id else None,
        changeset_id=UUID(version.changeset_id) if version.changeset_id else None,
        author_id=version.author_id,
        created_at=version.created_at,
        metadata=version.metadata
    )


def _entity_version_to_summary(version: EntityVersion) -> EntityVersionSummary:
    """Convert EntityVersion to summary model."""
    return EntityVersionSummary(
        id=version.id,
        entity_type=EntityTypeEnum(version.entity_type),
        entity_id=UUID(version.entity_id),
        version_number=version.version_number,
        state=ChangeStateEnum(version.state.value),
        author_id=version.author_id,
        created_at=version.created_at,
        parent_version_id=UUID(version.parent_version_id) if version.parent_version_id else None,
        changeset_id=UUID(version.changeset_id) if version.changeset_id else None
    )


def _working_tree_entry_to_out(entry) -> WorkingTreeEntryOut:
    """Convert WorkingTreeEntry to API output model."""
    return WorkingTreeEntryOut(
        entity_type=EntityTypeEnum(entry.entity_type),
        entity_id=UUID(entry.entity_id),
        current_version_id=UUID(entry.current_version_id),
        canonical_version_id=UUID(entry.canonical_version_id),
        staged=entry.staged,
        modified_at=entry.modified_at,
        has_changes=entry.has_changes()
    )


def _entity_diff_to_out(diff) -> EntityDiffOut:
    """Convert EntityDiff to API output model."""
    # Convert summary data to DiffSummaryOut
    if hasattr(diff, 'summary') and isinstance(diff.summary, dict):
        summary_data = diff.summary
        summary = DiffSummaryOut(
            added_items=summary_data.get('dictionary_item_added', 0) + summary_data.get('iterable_item_added', 0),
            removed_items=summary_data.get('dictionary_item_removed', 0) + summary_data.get('iterable_item_removed', 0),
            modified_items=summary_data.get('values_changed', 0),
            type_changes=summary_data.get('type_changes', 0),
            moved_items=0,  # DeepDiff doesn't track moves by default
            total_changes=sum(summary_data.values())
        )
    else:
        summary = DiffSummaryOut()
    
    return EntityDiffOut(
        entity_type=EntityTypeEnum(diff.entity_type),
        entity_id=UUID(diff.entity_id),
        before_version=_entity_version_to_summary(diff.before_version) if diff.before_version else None,
        after_version=_entity_version_to_summary(diff.after_version),
        changes=diff.changes,
        summary=summary,
        has_changes=diff.has_changes(),
        generated_at=diff.generated_at
    )
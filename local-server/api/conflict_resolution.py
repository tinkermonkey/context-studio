"""
Conflict Resolution API Endpoints

This module implements advanced conflict resolution API endpoints for intelligent
conflict detection, resolution suggestions, and manual/automatic resolution workflows.

Endpoints:
- GET /api/conflicts - List all conflicts with filtering
- GET /api/conflicts/{conflict_id} - Get conflict details
- POST /api/conflicts/{conflict_id}/resolve - Manually resolve conflict
- POST /api/conflicts/{conflict_id}/auto-resolve - Attempt automatic resolution
- GET /api/conflicts/entity/{entity_type}/{entity_id} - Get conflicts for specific entity
- POST /api/conflicts/detect - Detect conflicts between versions
- POST /api/conflicts/batch-resolve - Resolve multiple conflicts
- GET /api/conflicts/resolution-suggestions/{conflict_id} - Get resolution suggestions
- GET /api/conflicts/analytics - Get conflict analytics
- GET /api/conflicts/health - Get conflict resolution system health
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from database.utils import get_db
from services.service_factory import get_conflict_resolution_engine_via_factory
from pydantic import BaseModel, Field
from enum import Enum

router = APIRouter(prefix="/api/conflicts", tags=["conflict_resolution"])


class ConflictTypeEnum(str, Enum):
    """Enumeration of conflict types."""
    CONCURRENT_MODIFICATION = "concurrent_modification"
    STRUCTURAL_CONFLICT = "structural_conflict"
    DEPENDENCY_CONFLICT = "dependency_conflict"
    SEMANTIC_CONFLICT = "semantic_conflict"


class ConflictSeverityEnum(str, Enum):
    """Enumeration of conflict severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConflictDescriptorOut(BaseModel):
    """API model for conflict descriptor output."""
    conflict_id: str
    conflict_type: ConflictTypeEnum
    entity_type: str
    entity_id: str
    severity: ConflictSeverityEnum
    conflict_details: Dict[str, Any]
    resolution_suggestions: List[Dict[str, Any]]


class ResolveConflictRequest(BaseModel):
    """API model for conflict resolution request."""
    resolution_choice: Dict[str, Any]
    resolved_by: str


class DetectConflictsRequest(BaseModel):
    """API model for conflict detection request."""
    local_versions: List[Dict[str, Any]]
    remote_versions: List[Dict[str, Any]]
    entity_type: str


class BatchResolveRequest(BaseModel):
    """API model for batch conflict resolution."""
    conflict_ids: List[str] = Field(..., min_items=1)
    resolved_by: str
    resolution_strategy: str = Field(..., description="Strategy: auto, manual, prefer_local, prefer_remote")


class AutoResolveRequest(BaseModel):
    """API model for automatic conflict resolution."""
    confidence_threshold: float = Field(0.8, ge=0.0, le=1.0)
    max_attempts: int = Field(3, ge=1, le=10)


class ResolutionSuggestionOut(BaseModel):
    """API model for conflict resolution suggestions."""
    suggestion_id: str
    resolution_type: str
    confidence_score: float
    description: str
    resolution_data: Dict[str, Any]
    risk_level: str


class ConflictAnalyticsOut(BaseModel):
    """API model for conflict analytics."""
    total_conflicts: int
    conflicts_by_type: Dict[str, int]
    conflicts_by_severity: Dict[str, int]
    resolution_rates: Dict[str, float]
    avg_resolution_time_hours: Optional[float]
    auto_resolution_success_rate: float
    top_conflict_entities: List[Dict[str, Any]]


class ConflictHealthOut(BaseModel):
    """API model for conflict resolution system health."""
    status: str
    active_conflicts: int
    unresolved_high_severity: int
    auto_resolution_enabled: bool
    resolution_queue_size: int
    avg_detection_time_ms: float
    system_version: str


def get_conflict_resolution_engine(db: Session = Depends(get_db)):
    """Get ConflictResolutionEngine instance via service factory."""
    return get_conflict_resolution_engine_via_factory(db)


# Core Conflict Management Endpoints

@router.get("/", response_model=List[ConflictDescriptorOut])
def list_conflicts(
    conflict_type: Optional[ConflictTypeEnum] = Query(None, description="Filter by conflict type"),
    severity: Optional[ConflictSeverityEnum] = Query(None, description="Filter by severity"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    resolved_by: Optional[str] = Query(None, description="Filter by resolver"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of conflicts to return"),
    offset: int = Query(0, ge=0, description="Number of conflicts to skip"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """List conflicts with comprehensive filtering options."""
    try:
        conflicts = conflict_engine.list_conflicts(
            conflict_type=conflict_type.value if conflict_type else None,
            severity=severity.value if severity else None,
            entity_type=entity_type,
            entity_id=entity_id,
            resolved=resolved,
            resolved_by=resolved_by,
            limit=limit,
            offset=offset
        )
        return [ConflictDescriptorOut.model_validate(conflict) for conflict in conflicts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list conflicts: {str(e)}")


@router.get("/{conflict_id}", response_model=ConflictDescriptorOut)
def get_conflict(
    conflict_id: str = Path(..., description="Conflict ID"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Get detailed information about a specific conflict."""
    try:
        conflict = conflict_engine.get_conflict(conflict_id)
        if not conflict:
            raise HTTPException(status_code=404, detail=f"Conflict {conflict_id} not found")
        return ConflictDescriptorOut.model_validate(conflict)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conflict: {str(e)}")


@router.post("/{conflict_id}/resolve")
def resolve_conflict_manually(
    request: ResolveConflictRequest,
    conflict_id: str = Path(..., description="Conflict ID"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Manually resolve a specific conflict with custom resolution choice."""
    try:
        success = conflict_engine.resolve_conflict_manually(
            conflict_id=conflict_id,
            resolved_by=request.resolved_by,
            resolution_choice=request.resolution_choice
        )
        if not success:
            raise HTTPException(status_code=400, detail="Failed to resolve conflict")
        return {"message": f"Conflict {conflict_id} resolved successfully", "resolution": "manual"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve conflict: {str(e)}")


@router.post("/{conflict_id}/auto-resolve")
def auto_resolve_conflict(
    request: AutoResolveRequest,
    conflict_id: str = Path(..., description="Conflict ID"),
    resolved_by: str = Query(..., description="User requesting auto-resolution"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Attempt automatic resolution of a conflict using intelligent algorithms."""
    try:
        result = conflict_engine.resolve_conflict_automatically(
            conflict_id=conflict_id,
            resolved_by=resolved_by,
            confidence_threshold=request.confidence_threshold,
            max_attempts=request.max_attempts
        )
        
        if result.get("resolved", False):
            return {
                "message": f"Conflict {conflict_id} auto-resolved successfully",
                "resolution": "automatic",
                "confidence": result.get("confidence"),
                "strategy": result.get("strategy")
            }
        else:
            return {
                "message": f"Auto-resolution failed for conflict {conflict_id}",
                "reason": result.get("reason"),
                "suggestions": result.get("suggestions", [])
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to auto-resolve conflict: {str(e)}")


@router.get("/entity/{entity_type}/{entity_id}", response_model=List[ConflictDescriptorOut])
def get_entity_conflicts(
    entity_type: str = Path(..., description="Entity type"),
    entity_id: str = Path(..., description="Entity ID"),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Get all conflicts associated with a specific entity."""
    try:
        conflicts = conflict_engine.get_entity_conflicts(
            entity_type=entity_type,
            entity_id=entity_id,
            resolved=resolved
        )
        return [ConflictDescriptorOut.model_validate(conflict) for conflict in conflicts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get entity conflicts: {str(e)}")


# Conflict Detection and Batch Operations

@router.post("/detect", response_model=List[ConflictDescriptorOut])
def detect_conflicts(
    request: DetectConflictsRequest,
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Detect conflicts between local and remote entity versions."""
    try:
        conflicts = conflict_engine.detect_conflicts_between_versions(
            local_versions=request.local_versions,
            remote_versions=request.remote_versions,
            entity_type=request.entity_type
        )
        return [ConflictDescriptorOut.model_validate(conflict) for conflict in conflicts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detect conflicts: {str(e)}")


@router.post("/batch-resolve")
def batch_resolve_conflicts(
    request: BatchResolveRequest,
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Resolve multiple conflicts using a specified strategy."""
    try:
        results = conflict_engine.batch_resolve_conflicts(
            conflict_ids=request.conflict_ids,
            resolved_by=request.resolved_by,
            resolution_strategy=request.resolution_strategy
        )
        
        successful = len([r for r in results if r.get("success", False)])
        failed = len(results) - successful
        
        return {
            "message": f"Batch resolution completed: {successful} successful, {failed} failed",
            "successful_resolutions": successful,
            "failed_resolutions": failed,
            "details": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to batch resolve conflicts: {str(e)}")


# Resolution Suggestions and Intelligence

@router.get("/resolution-suggestions/{conflict_id}", response_model=List[ResolutionSuggestionOut])
def get_resolution_suggestions(
    conflict_id: str = Path(..., description="Conflict ID"),
    max_suggestions: int = Query(5, ge=1, le=10, description="Maximum number of suggestions"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Get intelligent resolution suggestions for a specific conflict."""
    try:
        suggestions = conflict_engine.get_resolution_suggestions(
            conflict_id=conflict_id,
            max_suggestions=max_suggestions
        )
        return [ResolutionSuggestionOut.model_validate(suggestion) for suggestion in suggestions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get resolution suggestions: {str(e)}")


# Analytics and Monitoring

@router.get("/analytics", response_model=ConflictAnalyticsOut)
def get_conflict_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    entity_type: Optional[str] = Query(None, description="Filter analytics by entity type"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Get comprehensive conflict resolution analytics."""
    try:
        analytics = conflict_engine.get_conflict_analytics(
            days=days,
            entity_type=entity_type
        )
        return ConflictAnalyticsOut.model_validate(analytics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conflict analytics: {str(e)}")


@router.get("/health", response_model=ConflictHealthOut)
def get_conflict_resolution_health(
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Get conflict resolution system health and performance metrics."""
    try:
        health = conflict_engine.get_system_health()
        return ConflictHealthOut.model_validate(health)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system health: {str(e)}")


# Advanced Conflict Resolution Features

@router.post("/resolve-strategy/prefer-local")
def resolve_conflicts_prefer_local(
    conflict_ids: List[str] = Query(..., description="Conflict IDs to resolve"),
    resolved_by: str = Query(..., description="User resolving conflicts"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Resolve conflicts by preferring local versions."""
    try:
        results = conflict_engine.resolve_conflicts_prefer_local(
            conflict_ids=conflict_ids,
            resolved_by=resolved_by
        )
        return {"message": "Conflicts resolved preferring local versions", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve conflicts: {str(e)}")


@router.post("/resolve-strategy/prefer-remote")
def resolve_conflicts_prefer_remote(
    conflict_ids: List[str] = Query(..., description="Conflict IDs to resolve"),
    resolved_by: str = Query(..., description="User resolving conflicts"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Resolve conflicts by preferring remote versions."""
    try:
        results = conflict_engine.resolve_conflicts_prefer_remote(
            conflict_ids=conflict_ids,
            resolved_by=resolved_by
        )
        return {"message": "Conflicts resolved preferring remote versions", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve conflicts: {str(e)}")


@router.post("/resolve-strategy/merge-intelligent")
def resolve_conflicts_intelligent_merge(
    conflict_ids: List[str] = Query(..., description="Conflict IDs to resolve"),
    resolved_by: str = Query(..., description="User resolving conflicts"),
    confidence_threshold: float = Query(0.8, ge=0.0, le=1.0, description="Minimum confidence for auto-merge"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Resolve conflicts using intelligent CRDT-based merging."""
    try:
        results = conflict_engine.resolve_conflicts_intelligent_merge(
            conflict_ids=conflict_ids,
            resolved_by=resolved_by,
            confidence_threshold=confidence_threshold
        )
        return {"message": "Conflicts resolved using intelligent merging", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve conflicts: {str(e)}")


# Conflict Prevention and Early Warning

@router.get("/risk-analysis/{entity_type}/{entity_id}")
def get_conflict_risk_analysis(
    entity_type: str = Path(..., description="Entity type"),
    entity_id: str = Path(..., description="Entity ID"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Get conflict risk analysis for an entity before modification."""
    try:
        risk_analysis = conflict_engine.analyze_conflict_risk(
            entity_type=entity_type,
            entity_id=entity_id
        )
        return risk_analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze conflict risk: {str(e)}")


@router.get("/hotspots")
def get_conflict_hotspots(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of hotspots to return"),
    conflict_engine = Depends(get_conflict_resolution_engine)
):
    """Get entities with highest conflict rates (hotspots)."""
    try:
        hotspots = conflict_engine.get_conflict_hotspots(
            days=days,
            limit=limit
        )
        return {"hotspots": hotspots, "analysis_period_days": days}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conflict hotspots: {str(e)}")
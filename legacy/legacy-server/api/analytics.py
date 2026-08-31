"""
Analytics API Endpoints

This module implements comprehensive analytics API endpoints for change analytics,  # noqa: E501
collaboration insights, system performance monitoring, and executive reporting.

Endpoints:
- GET /api/analytics/summary - Get change summary for specified period
- GET /api/analytics/user-activity - Get user activity reports
- GET /api/analytics/entity-hotspots - Get most frequently modified entities
- GET /api/analytics/collaboration-metrics - Get collaboration effectiveness metrics  # noqa: E501
- GET /api/analytics/change-impact/{changeset_id} - Get impact analysis for specific changeset  # noqa: E501
- GET /api/analytics/trends - Get comprehensive change trends over time
- GET /api/analytics/performance - Get system performance metrics
- GET /api/analytics/collaboration-insights - Get advanced collaboration insights  # noqa: E501
- GET /api/analytics/executive-summary - Get executive summary report
- GET /api/analytics/conflict-metrics - Get conflict resolution metrics
- GET /api/analytics/health - Get analytics system health
"""

from typing import Any

import pandas as pd  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from services.service_factory import get_change_analytics_engine_via_factory

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class AnalyticsHealthOut(BaseModel):
    """API model for analytics system health."""

    status: str
    duckdb_available: bool
    s3_configured: bool
    active_views: int
    data_freshness_hours: float | None
    query_performance_ms: float | None
    system_version: str


class ChangeSummaryOut(BaseModel):
    """API model for change summary output."""

    total_changes: int
    entities_modified: int
    active_users: int
    changesets: int
    period_start: str | None
    period_end: str | None


class UserActivityOut(BaseModel):
    """API model for user activity output."""

    author_id: str
    total_changes: int
    total_entities: int
    active_days: int
    avg_changes_per_day: float
    max_changes_per_day: int


class EntityHotspotOut(BaseModel):
    """API model for entity hotspot output."""

    entity_type: str
    entity_id: str
    total_modifications: int
    unique_authors: int
    lifespan_days: int
    modification_rate: float


class CollaborationMetricsOut(BaseModel):
    """API model for collaboration metrics output."""

    proposal_authors: int
    voters: int
    total_votes: int
    avg_response_time_hours: float
    approval_rate: float


class ChangeImpactOut(BaseModel):
    """API model for change impact analysis."""

    changeset_id: str
    total_entities: int
    entity_types_affected: int | None
    affected_entity_types: list[str] | None
    entities_created: int | None
    entities_updated: int | None
    entities_deleted: int | None
    impact_by_type: list[dict[str, Any]]


class TrendAnalysisOut(BaseModel):
    """API model for trend analysis output."""

    daily_trends: list[dict[str, Any]]
    peak_hours: list[dict[str, Any]]
    analysis_period_days: int


class PerformanceMetricsOut(BaseModel):
    """API model for performance metrics output."""

    sync_performance: dict[str, Any]
    system_load: list[dict[str, Any]]


class CollaborationInsightsOut(BaseModel):
    """API model for collaboration insights output."""

    collaboration_networks: list[dict[str, Any]]
    team_productivity: list[dict[str, Any]]
    analysis_period_days: int


class ExecutiveSummaryOut(BaseModel):
    """API model for executive summary output."""

    summary_period_days: int
    key_metrics: dict[str, Any]
    collaboration_health: dict[str, Any]
    system_health: dict[str, Any]
    top_entities: list[dict[str, Any]]
    generated_at: str


def get_analytics_engine():
    """Get ChangeAnalyticsEngine instance via service factory."""
    return get_change_analytics_engine_via_factory()


# Core Analytics Endpoints


@router.get("/summary", response_model=ChangeSummaryOut)
def get_change_summary(
    days: int = Query(
        30, ge=1, le=365, description="Number of days to analyze"
    ),
    analytics_engine=Depends(get_analytics_engine),
):
    """Get comprehensive change summary for specified period."""
    try:
        summary = analytics_engine.get_change_summary(days=days)
        return ChangeSummaryOut.model_validate(summary)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get change summary: {e!s}"
        )


@router.get("/user-activity", response_model=list[UserActivityOut])
def get_user_activity_report(
    user_id: str | None = Query(
        None, description="Specific user ID to analyze"
    ),
    days: int = Query(
        30, ge=1, le=365, description="Number of days to analyze"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of users to return"
    ),
    analytics_engine=Depends(get_analytics_engine),
):
    """Get comprehensive user activity reports."""
    try:
        activity_df = analytics_engine.get_user_activity_report(
            user_id=user_id, days=days
        )

        if activity_df.empty:
            return []

        # Apply limit
        limited_df = activity_df.head(limit)
        return [
            UserActivityOut.model_validate(row.to_dict())
            for _, row in limited_df.iterrows()
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get user activity: {e!s}"
        )


@router.get("/entity-hotspots", response_model=list[EntityHotspotOut])
def get_entity_hotspots(
    limit: int = Query(
        50, ge=1, le=500, description="Maximum number of hotspots to return"
    ),
    analytics_engine=Depends(get_analytics_engine),
):
    """Get entities with highest modification frequency (hotspots)."""
    try:
        hotspots_df = analytics_engine.get_entity_hotspots(limit=limit)

        if hotspots_df.empty:
            return []

        return [
            EntityHotspotOut.model_validate(row.to_dict())
            for _, row in hotspots_df.iterrows()
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get entity hotspots: {e!s}"
        )


@router.get("/collaboration-metrics", response_model=CollaborationMetricsOut)
def get_collaboration_metrics(
    days: int = Query(
        60, ge=1, le=365, description="Number of days to analyze"
    ),
    analytics_engine=Depends(get_analytics_engine),
):
    """Get collaboration effectiveness metrics."""
    try:
        metrics = analytics_engine.get_collaboration_metrics(days=days)
        return CollaborationMetricsOut.model_validate(metrics)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get collaboration metrics: {e!s}"
        )


@router.get("/change-impact/{changeset_id}", response_model=ChangeImpactOut)
def get_change_impact_analysis(
    changeset_id: str = Path(..., description="Changeset ID to analyze"),
    analytics_engine=Depends(get_analytics_engine),
):
    """Get comprehensive impact analysis for a specific changeset."""
    try:
        impact = analytics_engine.generate_change_impact_analysis(changeset_id)
        return ChangeImpactOut.model_validate(impact)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get change impact analysis: {e!s}"
        )


@router.get("/trends", response_model=TrendAnalysisOut)
def get_change_trends(
    days: int = Query(
        90, ge=1, le=365, description="Number of days to analyze"
    ),
    analytics_engine=Depends(get_analytics_engine),
):
    """Get comprehensive change trends and patterns over time."""
    try:
        trends = analytics_engine.get_comprehensive_change_trends(days=days)
        return TrendAnalysisOut.model_validate(trends)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get change trends: {e!s}"
        )


@router.get("/performance", response_model=PerformanceMetricsOut)
def get_system_performance_metrics(analytics_engine=Depends(get_analytics_engine)):
    """Get system performance and health metrics."""
    try:
        metrics = analytics_engine.get_system_performance_metrics()
        return PerformanceMetricsOut.model_validate(metrics)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get performance metrics: {e!s}"
        )


@router.get("/collaboration-insights", response_model=CollaborationInsightsOut)
def get_collaboration_insights(
    days: int = Query(
        60, ge=1, le=365, description="Number of days to analyze"
    ),
    analytics_engine=Depends(get_analytics_engine),
):
    """Get advanced insights into collaboration patterns and team productivity."""
    try:
        insights = analytics_engine.get_advanced_collaboration_insights(
            days=days
        )
        return CollaborationInsightsOut.model_validate(insights)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get collaboration insights: {e!s}"
        )


@router.get("/executive-summary", response_model=ExecutiveSummaryOut)
def get_executive_summary(
    days: int = Query(
        30, ge=1, le=365, description="Number of days to analyze"
    ),
    analytics_engine=Depends(get_analytics_engine),
):
    """Generate executive summary of system activity and health."""
    try:
        summary = analytics_engine.generate_executive_summary(days=days)
        return ExecutiveSummaryOut.model_validate(summary)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate executive summary: {e!s}"
        )


# Conflict Analytics (delegated from other systems)


@router.get("/conflict-metrics")
def get_conflict_resolution_metrics(analytics_engine=Depends(get_analytics_engine)):
    """Get comprehensive conflict resolution analytics."""
    try:
        metrics = analytics_engine.get_conflict_resolution_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get conflict metrics: {e!s}"
        )


# System Health and Monitoring


@router.get("/health", response_model=AnalyticsHealthOut)
def get_analytics_health(analytics_engine=Depends(get_analytics_engine)):
    """Get analytics system health and performance status."""
    try:
        # Check DuckDB availability
        duckdb_available = analytics_engine.duckdb.connection is not None
        s3_configured = bool(
            analytics_engine.s3_config and "bucket" in analytics_engine.s3_config
        )

        # Check active views
        active_views = 0
        if duckdb_available:
            try:
                # Count active analytical views
                view_check_result = analytics_engine.duckdb.execute_query(
                    "SELECT COUNT(*) as view_count FROM information_schema.views WHERE table_schema = 'main'"
                )
                active_views = (
                    view_check_result.iloc[0]["view_count"]
                    if not view_check_result.empty
                    else 0
                )
            except Exception:
                active_views = 0

        # Basic performance check
        import time

        start_time = time.time()
        try:
            analytics_engine.get_change_summary(days=1)
            query_performance_ms = (time.time() - start_time) * 1000
        except Exception:
            query_performance_ms = None

        health_status = "healthy" if duckdb_available else "degraded"

        return AnalyticsHealthOut(
            status=health_status,
            duckdb_available=duckdb_available,
            s3_configured=s3_configured,
            active_views=active_views,
            data_freshness_hours=None,  # Would need to check actual data timestamps
            query_performance_ms=query_performance_ms,
            system_version="4.0.0",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get analytics health: {e!s}"
        )


# Export and Reporting Endpoints


@router.get("/export/csv/{report_type}")
def export_analytics_csv(
    report_type: str = Path(
        ...,
        description="Type of report to export (summary, user-activity, hotspots, trends)",
    ),
    days: int = Query(
        30, ge=1, le=365, description="Number of days to analyze"
    ),
    analytics_engine=Depends(get_analytics_engine),
):
    """Export analytics data as CSV format."""
    import io

    from fastapi.responses import StreamingResponse

    try:
        # Generate appropriate report based on type
        if report_type == "user-activity":
            df = analytics_engine.get_user_activity_report(days=days)
        elif report_type == "hotspots":
            df = analytics_engine.get_entity_hotspots(limit=1000)
        elif report_type == "trends":
            trends = analytics_engine.get_comprehensive_change_trends(
                days=days
            )
            df = pd.DataFrame(trends.get("daily_trends", []))
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported report type: {report_type}"
            )

        # Convert to CSV (even if empty)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(csv_buffer.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={report_type}_analytics_{days}days.csv"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to export analytics: {e!s}"
        )


# Real-time Analytics Dashboard Support


@router.get("/dashboard/metrics")
def get_dashboard_metrics(
    refresh_interval: int = Query(
        300, ge=60, le=3600, description="Refresh interval in seconds"
    ),
    analytics_engine=Depends(get_analytics_engine),
):
    """Get real-time metrics suitable for dashboard display."""
    try:
        # Get key metrics for dashboard
        change_summary = analytics_engine.get_change_summary(
            days=1
        )  # Last 24 hours
        user_activity = analytics_engine.get_user_activity_report(
            days=7
        )  # Last week
        conflict_metrics = analytics_engine.get_conflict_resolution_metrics()
        performance_metrics = analytics_engine.get_system_performance_metrics()

        return {
            "timestamp": pd.Timestamp.now().isoformat(),
            "refresh_interval": refresh_interval,
            "metrics": {
                "changes_today": change_summary.get("total_changes", 0),
                "active_users_week": (
                    len(user_activity) if not user_activity.empty else 0
                ),
                "unresolved_conflicts": (
                    conflict_metrics.get("total_conflicts", 0)
                    - conflict_metrics.get("resolved_conflicts", 0)
                ),
                "avg_sync_time": performance_metrics.get("sync_performance", {}).get(
                    "avg_sync_time_minutes", 0
                ),
                "system_status": (
                    "healthy" if analytics_engine.duckdb.connection else "degraded"
                ),
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get dashboard metrics: {e!s}"
        )

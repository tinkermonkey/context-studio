"""
Enhanced Event Processor Administrative Monitoring

This module provides administrative endpoints for monitoring the Enhanced Event Processor
which leverages Phase 3 Enhanced Database Manager optimizations.

Features:
- Event processing statistics and performance metrics
- Database connection health monitoring
- Environment-aware configuration reporting
- Enhanced performance recommendations
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, Optional
from datetime import datetime

from utils.event_processor import get_global_event_processor
from database.utils import get_database_manager

router = APIRouter()


@router.get("/admin/events/health", summary="Event Processor Health Check")
async def get_event_processor_health(request: Request) -> Dict[str, Any]:
    """Get comprehensive health status of the event processor."""
    try:
        # Get the global event processor
        processor = get_global_event_processor()
        
        if not processor:
            return {
                "status": "not_running",
                "message": "No event processor instance found",
                "timestamp": datetime.now().isoformat(),
                "enhanced_available": True
            }
        
        # Check if it's the enhanced version with health monitoring
        if hasattr(processor, 'get_health_status'):
            return processor.get_health_status()
        else:
            # Legacy processor - basic health check
            stats = processor.get_stats() if hasattr(processor, 'get_stats') else {}
            return {
                "status": "running" if stats.get("is_running", False) else "stopped",
                "timestamp": datetime.now().isoformat(),
                "processor_type": "legacy",
                "enhanced_available": True,
                "stats": stats,
                "recommendation": "Consider upgrading to EnhancedEventProcessor for better monitoring"
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/admin/events/stats", summary="Event Processor Statistics")
async def get_event_processor_stats(request: Request) -> Dict[str, Any]:
    """Get detailed statistics from the event processor."""
    try:
        processor = get_global_event_processor()
        
        if not processor:
            return {
                "error": "No event processor instance found",
                "timestamp": datetime.now().isoformat(),
                "enhanced_available": True
            }
        
        stats = processor.get_stats() if hasattr(processor, 'get_stats') else {}
        
        return {
            "timestamp": datetime.now().isoformat(),
            "processor_type": "enhanced" if hasattr(processor, 'db_manager') else "legacy",
            "enhanced_available": True,
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")


@router.get("/admin/events/performance", summary="Event Processing Performance Metrics")
async def get_event_processing_performance(request: Request) -> Dict[str, Any]:
    """Get detailed performance metrics for event processing."""
    try:
        processor = get_global_event_processor()
        
        if not processor:
            return {
                "error": "No event processor instance found",
                "timestamp": datetime.now().isoformat()
            }
        
        # Get processor stats
        stats = processor.get_stats() if hasattr(processor, 'get_stats') else {}
        
        # Enhanced processor provides database metrics
        performance_data = {
            "timestamp": datetime.now().isoformat(),
            "processor_type": "enhanced" if hasattr(processor, 'db_manager') else "legacy",
            "event_metrics": {
                "unprocessed_count": stats.get("unprocessed_count", 0),
                "processed_count": stats.get("processed_count", 0),
                "total_processed": stats.get("events_processed_total", stats.get("processed_count", 0)),
                "is_running": stats.get("is_running", False),
                "last_processed_id": stats.get("last_processed_id", 0)
            }
        }
        
        # Add enhanced metrics if available
        if hasattr(processor, 'db_manager'):
            performance_data.update({
                "engine_id": stats.get("engine_id", "unknown"),
                "database_metrics": stats.get("database_metrics", {}),
                "enhanced_features": stats.get("enhanced_features", {})
            })
        
        return performance_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Performance metrics failed: {str(e)}")


@router.get("/admin/events/database", summary="Event Processor Database Status")
async def get_event_processor_database_status(request: Request) -> Dict[str, Any]:
    """Get database connection status for the event processor."""
    try:
        processor = get_global_event_processor()
        
        if not processor:
            return {
                "error": "No event processor instance found",
                "timestamp": datetime.now().isoformat()
            }
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "processor_type": "enhanced" if hasattr(processor, 'db_manager') else "legacy"
        }
        
        # Enhanced processor provides database manager integration
        if hasattr(processor, 'db_manager'):
            db_manager = processor.db_manager
            health = db_manager.perform_health_check()
            
            result.update({
                "database_health": health,
                "engine_id": processor.engine_id,
                "optimized_pooling": True
            })
        else:
            # Legacy processor
            result.update({
                "database_health": {"status": "unknown", "message": "Legacy processor - limited health monitoring"},
                "optimized_pooling": False,
                "recommendation": "Upgrade to EnhancedEventProcessor for database health monitoring"
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database status check failed: {str(e)}")


@router.post("/admin/events/restart", summary="Restart Event Processor")
async def restart_event_processor(request: Request) -> Dict[str, Any]:
    """Restart the event processor."""
    try:
        processor = get_global_event_processor()
        
        if not processor:
            return {
                "error": "No event processor instance found",
                "timestamp": datetime.now().isoformat()
            }
        
        # Stop the processor
        processor.stop()
        
        # Start it again
        processor.start()
        
        return {
            "status": "success",
            "message": "Event processor restarted successfully",
            "timestamp": datetime.now().isoformat(),
            "processor_type": "enhanced" if hasattr(processor, 'db_manager') else "legacy"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restart failed: {str(e)}")


@router.get("/admin/events/recommendations", summary="Event Processor Performance Recommendations")
async def get_event_processor_recommendations(request: Request) -> Dict[str, Any]:
    """Get performance recommendations for the event processor."""
    try:
        processor = get_global_event_processor()
        
        if not processor:
            return {
                "recommendations": ["No event processor instance found - start the application to initialize event processing"],
                "timestamp": datetime.now().isoformat()
            }
        
        stats = processor.get_stats() if hasattr(processor, 'get_stats') else {}
        recommendations = []
        
        # Check processor type
        is_enhanced = hasattr(processor, 'db_manager')
        
        if not is_enhanced and True:
            recommendations.append(
                "🚀 Upgrade to EnhancedEventProcessor for 50%+ better performance with optimized database pooling"
            )
        
        # Check unprocessed events
        unprocessed = stats.get("unprocessed_count", 0)
        if unprocessed > 100:
            recommendations.append(f"⚠️ High unprocessed event count ({unprocessed}) - consider reducing poll_interval or increasing max_events")
        elif unprocessed > 1000:
            recommendations.append(f"🔥 Very high unprocessed event count ({unprocessed}) - immediate attention required")
        
        # Check if processor is running
        if not stats.get("is_running", False):
            recommendations.append("❌ Event processor is not running - restart required")
        
        # Enhanced processor specific recommendations
        if is_enhanced:
            db_metrics = stats.get("database_metrics", {})
            
            # Database performance recommendations
            if db_metrics.get("pool_efficiency_percent", 100) < 80:
                recommendations.append("📊 Database pool efficiency is low - consider adjusting pool configuration")
            
            if db_metrics.get("avg_query_time_ms", 0) > 10:
                recommendations.append("⏱️ Database query times are high - check database performance")
        
        # If no issues found
        if not recommendations:
            recommendations.append("✅ Event processor performance is optimal")
        
        return {
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat(),
            "processor_type": "enhanced" if is_enhanced else "legacy",
            "enhanced_available": True,
            "stats_summary": {
                "unprocessed_count": stats.get("unprocessed_count", 0),
                "is_running": stats.get("is_running", False)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendations failed: {str(e)}")


@router.get("/admin/events/dashboard", summary="Event Processor Dashboard")
async def get_event_processor_dashboard(request: Request) -> Dict[str, Any]:
    """Get comprehensive dashboard data for event processor monitoring."""
    try:
        processor = get_global_event_processor()
        
        if not processor:
            return {
                "status": "no_processor",
                "message": "No event processor instance found",
                "timestamp": datetime.now().isoformat(),
                "enhanced_available": True
            }
        
        # Get basic stats
        stats = processor.get_stats() if hasattr(processor, 'get_stats') else {}
        is_enhanced = hasattr(processor, 'db_manager')
        
        dashboard = {
            "timestamp": datetime.now().isoformat(),
            "processor_info": {
                "type": "enhanced" if is_enhanced else "legacy",
                "is_running": stats.get("is_running", False),
                "enhanced_available": True
            },
            "event_metrics": {
                "unprocessed_count": stats.get("unprocessed_count", 0),
                "processed_count": stats.get("processed_count", 0),
                "total_processed": stats.get("events_processed_total", stats.get("processed_count", 0)),
                "last_processed_id": stats.get("last_processed_id", 0)
            }
        }
        
        # Add enhanced features if available
        if is_enhanced:
            dashboard.update({
                "database_metrics": stats.get("database_metrics", {}),
                "enhanced_features": stats.get("enhanced_features", {}),
                "engine_id": stats.get("engine_id", "unknown")
            })
            
            # Add health status if available
            if hasattr(processor, 'get_health_status'):
                health = processor.get_health_status()
                dashboard["health_status"] = health
        
        return dashboard
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard data failed: {str(e)}")

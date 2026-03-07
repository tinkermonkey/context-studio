"""
Migration 010: Add Phase 5 Optimization Features

This migration adds tables for Phase 5 enterprise-scale optimization features including:
- Query optimization metrics and materialized view tracking
- Storage optimization and lifecycle management
- Performance monitoring and alerting
- Batch operation optimization tracking
- System optimization configuration

Tables added:
- query_performance_metrics: Query execution and optimization tracking
- materialized_views_registry: Materialized view management
- storage_optimization_logs: Storage optimization operation tracking
- performance_alerts: Performance alert and notification system
- batch_operation_metrics: Batch processing performance tracking
- optimization_configuration: System optimization settings
"""

from sqlalchemy import text
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

MIGRATION_VERSION = 10
MIGRATION_DESCRIPTION = "Add Phase 5 Optimization Features - Enterprise Performance and Storage Optimization"


def upgrade(connection):
    """Apply migration 010 - add optimization features tables."""
    logger.info(f"Applying migration {MIGRATION_VERSION}: {MIGRATION_DESCRIPTION}")

    try:
        # Enable foreign keys
        connection.execute(text("PRAGMA foreign_keys = ON"))

        # 1. Query performance metrics table
        connection.execute(text("""
        CREATE TABLE query_performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id TEXT NOT NULL,
            query_hash TEXT NOT NULL,
            query_text TEXT NOT NULL,
            execution_time_ms REAL NOT NULL,
            rows_processed INTEGER DEFAULT 0,
            bytes_scanned INTEGER DEFAULT 0,
            partitions_accessed INTEGER DEFAULT 0,
            cache_hit_ratio REAL DEFAULT 0.0,
            optimization_level TEXT CHECK (optimization_level IN ('none', 'basic', 'advanced', 'failed')),  
            optimization_strategies TEXT,  -- JSON array of applied strategies
            created_at TEXT NOT NULL,
            database_type TEXT DEFAULT 'duckdb' CHECK (database_type IN ('duckdb', 'sqlite', 'other'))  
        )
        """))

        # Indexes for query performance metrics
        connection.execute(text("""
        CREATE INDEX idx_query_metrics_hash ON query_performance_metrics(query_hash, created_at DESC)  
        """))

        connection.execute(text("""
        CREATE INDEX idx_query_metrics_performance ON query_performance_metrics(execution_time_ms DESC, created_at DESC)  
        """))

        connection.execute(text("""
        CREATE INDEX idx_query_metrics_optimization ON query_performance_metrics(optimization_level, cache_hit_ratio)  
        """))

        # 2. Materialized views registry table
        connection.execute(text("""
        CREATE TABLE materialized_views_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            view_name TEXT UNIQUE NOT NULL,
            view_query TEXT NOT NULL,
            refresh_strategy TEXT NOT NULL CHECK (refresh_strategy IN ('manual', 'scheduled', 'on_demand')),  
            created_at TEXT NOT NULL,
            last_refreshed_at TEXT,
            refresh_frequency_minutes INTEGER,
            row_count INTEGER DEFAULT 0,
            size_bytes INTEGER DEFAULT 0,
            usage_count INTEGER DEFAULT 0,
            last_used_at TEXT,
            enabled INTEGER DEFAULT 1 CHECK (enabled IN (0, 1)),
            metadata TEXT  -- JSON metadata including dependencies
        )
        """))

        # Indexes for materialized views
        connection.execute(text("""
        CREATE INDEX idx_materialized_views_refresh ON materialized_views_registry(refresh_strategy, last_refreshed_at)  
        """))

        connection.execute(text("""
        CREATE INDEX idx_materialized_views_usage ON materialized_views_registry(usage_count DESC, last_used_at DESC)  
        """))

        # 3. Storage optimization logs table
        connection.execute(text("""
        CREATE TABLE storage_optimization_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            optimization_id TEXT UNIQUE NOT NULL,
            optimization_type TEXT NOT NULL CHECK (optimization_type IN ('compression', 'lifecycle', 'cleanup', 'migration', 'full')),  
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),  
            objects_processed INTEGER DEFAULT 0,
            storage_freed_bytes INTEGER DEFAULT 0,
            cost_reduction_estimate REAL DEFAULT 0.0,
            compression_ratio REAL DEFAULT 1.0,
            optimization_details TEXT,  -- JSON object with details
            error_details TEXT,  -- JSON array of errors
            triggered_by TEXT,  -- 'automatic', 'manual', 'scheduled'
            s3_bucket TEXT,
            metadata TEXT  -- JSON metadata
        )
        """))

        # Indexes for storage optimization logs
        connection.execute(text("""
        CREATE INDEX idx_storage_optimization_type ON storage_optimization_logs(optimization_type, started_at DESC)  
        """))

        connection.execute(text("""
        CREATE INDEX idx_storage_optimization_status ON storage_optimization_logs(status, completed_at DESC)  
        """))

        connection.execute(text("""
        CREATE INDEX idx_storage_optimization_savings ON storage_optimization_logs(storage_freed_bytes DESC, cost_reduction_estimate DESC)  
        """))

        # 4. Performance alerts table
        connection.execute(text("""
        CREATE TABLE performance_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id TEXT UNIQUE NOT NULL,
            alert_type TEXT NOT NULL CHECK (alert_type IN ('threshold_exceeded', 'anomaly_detected', 'degradation', 'system_error')),  
            severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),  
            metric_name TEXT NOT NULL,
            current_value REAL NOT NULL,
            threshold_value REAL,
            deviation_percent REAL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            acknowledged_at TEXT,
            acknowledged_by TEXT,
            resolved_at TEXT,
            resolved_by TEXT,
            resolution_notes TEXT,
            notification_sent INTEGER DEFAULT 0 CHECK (notification_sent IN (0, 1)),  
            alert_metadata TEXT  -- JSON metadata including context
        )
        """))

        # Indexes for performance alerts
        connection.execute(text("""
        CREATE INDEX idx_performance_alerts_severity ON performance_alerts(severity, created_at DESC)  
        """))

        connection.execute(text("""
        CREATE INDEX idx_performance_alerts_metric ON performance_alerts(metric_name, current_value)  
        """))

        connection.execute(text("""
        CREATE INDEX idx_performance_alerts_resolution ON performance_alerts(resolved_at, acknowledged_at)  
        """))

        # 5. Batch operation metrics table
        connection.execute(text("""
        CREATE TABLE batch_operation_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id TEXT UNIQUE NOT NULL,
            operation_type TEXT NOT NULL CHECK (operation_type IN ('create_versions', 'merge_changes', 'bulk_update', 'data_migration')),  
            author_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            total_items INTEGER NOT NULL,
            successful_items INTEGER DEFAULT 0,
            failed_items INTEGER DEFAULT 0,
            processing_time_seconds REAL DEFAULT 0.0,
            throughput_per_second REAL DEFAULT 0.0,
            parallel_workers INTEGER DEFAULT 1,
            batch_size INTEGER DEFAULT 1000,
            memory_usage_mb REAL DEFAULT 0.0,
            optimization_applied TEXT,  -- JSON array of optimizations
            errors_summary TEXT,  -- JSON array of error summaries
            performance_grade TEXT CHECK (performance_grade IN ('A+', 'A', 'B', 'C', 'D', 'F')),  
            metadata TEXT  -- JSON metadata
        )
        """))

        # Indexes for batch operation metrics
        connection.execute(text("""
        CREATE INDEX idx_batch_metrics_type ON batch_operation_metrics(operation_type, started_at DESC)  
        """))

        connection.execute(text("""
        CREATE INDEX idx_batch_metrics_performance ON batch_operation_metrics(throughput_per_second DESC, processing_time_seconds ASC)  
        """))

        connection.execute(text("""
        CREATE INDEX idx_batch_metrics_author ON batch_operation_metrics(author_id, started_at DESC)  
        """))

        # 6. Optimization configuration table
        connection.execute(text("""
        CREATE TABLE optimization_configuration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT UNIQUE NOT NULL,
            config_category TEXT NOT NULL CHECK (config_category IN ('query', 'storage', 'performance', 'batch', 'system')),  
            config_value TEXT NOT NULL,  -- JSON value
            config_type TEXT NOT NULL CHECK (config_type IN ('string', 'number', 'boolean', 'object', 'array')),  
            description TEXT,
            default_value TEXT,  -- JSON default value
            last_updated_at TEXT NOT NULL,
            updated_by TEXT,
            enabled INTEGER DEFAULT 1 CHECK (enabled IN (0, 1)),
            metadata TEXT  -- JSON metadata including validation rules
        )
        """))

        # Indexes for optimization configuration
        connection.execute(text("""
        CREATE INDEX idx_optimization_config_category ON optimization_configuration(config_category, enabled)  
        """))

        connection.execute(text("""
        CREATE INDEX idx_optimization_config_updated ON optimization_configuration(last_updated_at DESC)  
        """))

        # 7. Performance monitoring sessions table (for continuous monitoring)
        connection.execute(text("""
        CREATE TABLE performance_monitoring_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            monitoring_type TEXT NOT NULL CHECK (monitoring_type IN ('continuous', 'scheduled', 'on_demand')),  
            started_at TEXT NOT NULL,
            ended_at TEXT,
            metrics_collected INTEGER DEFAULT 0,
            alerts_triggered INTEGER DEFAULT 0,
            optimizations_applied INTEGER DEFAULT 0,
            session_status TEXT NOT NULL CHECK (session_status IN ('active', 'completed', 'failed', 'cancelled')),  
            configuration TEXT,  -- JSON configuration for the session
            summary_metrics TEXT,  -- JSON summary of collected metrics
            created_by TEXT DEFAULT 'system',
            metadata TEXT  -- JSON metadata
        )
        """))

        # Index for monitoring sessions
        connection.execute(text("""
        CREATE INDEX idx_monitoring_sessions_type ON performance_monitoring_sessions(monitoring_type, started_at DESC)  
        """))

        # 8. Create useful views for optimization analytics

        # View for query performance analytics
        connection.execute(text("""
        CREATE VIEW query_performance_analytics AS
        SELECT
            DATE(created_at) as performance_date,
            optimization_level,
            COUNT(*) as total_queries,
            AVG(execution_time_ms) as avg_execution_time_ms,
            MIN(execution_time_ms) as min_execution_time_ms,
            MAX(execution_time_ms) as max_execution_time_ms,
            AVG(cache_hit_ratio) as avg_cache_hit_ratio,
            AVG(rows_processed) as avg_rows_processed,
            SUM(bytes_scanned) / 1024.0 / 1024.0 as total_mb_scanned
        FROM query_performance_metrics
        GROUP BY DATE(created_at), optimization_level
        ORDER BY performance_date DESC, optimization_level;
        """))

        # View for storage optimization analytics
        connection.execute(text("""
        CREATE VIEW storage_optimization_analytics AS
        SELECT
            DATE(started_at) as optimization_date,
            optimization_type,
            COUNT(*) as operations_count,
            SUM(objects_processed) as total_objects_processed,
            SUM(storage_freed_bytes) / 1024.0 / 1024.0 / 1024.0 as total_gb_freed,  
            AVG(cost_reduction_estimate) as avg_cost_reduction,
            AVG(compression_ratio) as avg_compression_ratio,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_operations,  
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_operations
        FROM storage_optimization_logs
        WHERE completed_at IS NOT NULL
        GROUP BY DATE(started_at), optimization_type
        ORDER BY optimization_date DESC, optimization_type;
        """))

        # View for performance health dashboard
        connection.execute(text("""
        CREATE VIEW performance_health_dashboard AS
        SELECT
            'current_status' as metric_category,
            COUNT(CASE WHEN severity = 'critical' AND resolved_at IS NULL THEN 1 END) as critical_alerts,  
            COUNT(CASE WHEN severity = 'high' AND resolved_at IS NULL THEN 1 END) as high_alerts,  
            COUNT(CASE WHEN severity IN ('medium', 'low') AND resolved_at IS NULL THEN 1 END) as other_alerts,  
            (
                SELECT COUNT(*)
                FROM query_performance_metrics
                WHERE created_at > datetime('now', '-1 hour')
            ) as queries_last_hour,
            (
                SELECT AVG(execution_time_ms)
                FROM query_performance_metrics
                WHERE created_at > datetime('now', '-1 hour')
            ) as avg_query_time_last_hour,
            (
                SELECT COUNT(*)
                FROM batch_operation_metrics
                WHERE started_at > datetime('now', '-24 hours') AND completed_at IS NOT NULL  
            ) as batch_operations_last_24h,
            (
                SELECT COUNT(*)
                FROM storage_optimization_logs
                WHERE started_at > datetime('now', '-7 days') AND status = 'completed'  
            ) as storage_optimizations_last_week
        FROM performance_alerts
        WHERE created_at > datetime('now', '-24 hours');
        """))

        # Insert default optimization configuration
        default_configs = [
            ("query_cache_ttl_seconds", "query", "3600", "number", "Query cache time-to-live in seconds"),
            ("query_optimization_enabled", "query", "true", "boolean", "Enable automatic query optimization"),
            ("storage_lifecycle_policies_enabled", "storage", "true", "boolean", "Enable S3 lifecycle policies"),
            ("performance_monitoring_interval_seconds", "performance", "300", "number", "Performance monitoring interval"),
            ("auto_optimization_enabled", "system", "true", "boolean", "Enable automatic optimization"),
            ("batch_operation_default_size", "batch", "1000", "number", "Default batch operation size"),
            ("alert_notification_enabled", "performance", "true", "boolean", "Enable performance alert notifications")
        ]

        for config_key, category, value, config_type, description in default_configs:
            connection.execute(text("""
            INSERT INTO optimization_configuration
            (config_key, config_category, config_value, config_type, description, last_updated_at, updated_by)  
            VALUES (:config_key, :category, :value, :config_type, :description, :last_updated_at, 'system')  
            """), {
                "config_key": config_key,
                "category": category,
                "value": value,
                "config_type": config_type,
                "description": description,
                "last_updated_at": datetime.now().isoformat()
            })

        # Update schema version
        connection.execute(text(f"""
        UPDATE schema_version SET version = {MIGRATION_VERSION}, updated_at = :updated_at
        """), {"updated_at": datetime.now().isoformat()})

        connection.commit()
        logger.info(f"Migration {MIGRATION_VERSION} completed successfully")

    except Exception as e:
        connection.rollback()
        logger.error(f"Migration {MIGRATION_VERSION} failed: {e}")
        raise


def downgrade(connection):
    """Rollback migration 010 - remove optimization features tables."""
    logger.info(f"Rolling back migration {MIGRATION_VERSION}")

    try:
        # Drop views first
        connection.execute(text("DROP VIEW IF EXISTS performance_health_dashboard"))
        connection.execute(text("DROP VIEW IF EXISTS storage_optimization_analytics"))
        connection.execute(text("DROP VIEW IF EXISTS query_performance_analytics"))

        # Drop tables in reverse order (respecting foreign key constraints)
        connection.execute(text("DROP TABLE IF EXISTS performance_monitoring_sessions"))
        connection.execute(text("DROP TABLE IF EXISTS optimization_configuration"))
        connection.execute(text("DROP TABLE IF EXISTS batch_operation_metrics"))
        connection.execute(text("DROP TABLE IF EXISTS performance_alerts"))
        connection.execute(text("DROP TABLE IF EXISTS storage_optimization_logs"))
        connection.execute(text("DROP TABLE IF EXISTS materialized_views_registry"))
        connection.execute(text("DROP TABLE IF EXISTS query_performance_metrics"))

        # Revert schema version
        connection.execute(text(f"""
        UPDATE schema_version SET version = {MIGRATION_VERSION - 1}, updated_at = :updated_at
        """), {"updated_at": datetime.now().isoformat()})

        connection.commit()
        logger.info(f"Migration {MIGRATION_VERSION} rollback completed")

    except Exception as e:
        connection.rollback()
        logger.error(f"Migration {MIGRATION_VERSION} rollback failed: {e}")
        raise

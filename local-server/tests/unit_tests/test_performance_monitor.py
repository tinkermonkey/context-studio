"""
Unit tests for PerformanceMonitor - Testing comprehensive performance monitoring.

Tests performance metrics collection, trend analysis, automated optimization, and alerting.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
import time
import statistics
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from services.performance_monitor import (
    PerformanceMonitor,
    PerformanceAlert,
    OptimizationAction
)


class TestPerformanceMonitor:
    """Test cases for PerformanceMonitor functionality."""
    
    @pytest.fixture
    def mock_sqlite_conn(self):
        """Create a mock SQLite connection."""
        mock_conn = Mock()
        cursor = Mock()
        
        # Mock cursor methods
        cursor.fetchall.return_value = [('main', 'database', 'test.db', 2)]
        cursor.fetchone.return_value = (150, 45, 12)  # total_objects, table_count, index_count
        
        mock_conn.cursor.return_value = cursor
        return mock_conn
    
    @pytest.fixture
    def mock_duckdb_conn(self):
        """Create a mock DuckDB connection."""
        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = [('result',)]
        return mock_conn
    
    @pytest.fixture
    def mock_s3_sync(self):
        """Create a mock S3 sync manager."""
        mock_sync = Mock()
        return mock_sync
    
    @pytest.fixture
    def performance_monitor(self, mock_sqlite_conn, mock_duckdb_conn, mock_s3_sync):
        """Create a PerformanceMonitor instance for testing."""
        return PerformanceMonitor(mock_sqlite_conn, mock_duckdb_conn, mock_s3_sync)
    
    def test_monitor_initialization(self, performance_monitor):
        """Test PerformanceMonitor initialization."""
        assert performance_monitor.sqlite_conn is not None
        assert performance_monitor.duckdb_conn is not None
        assert performance_monitor.s3_sync is not None
        assert performance_monitor.metrics_history == []
        assert performance_monitor.alerts == []
        assert performance_monitor.optimization_history == []
        assert performance_monitor.optimization_enabled is True
        assert performance_monitor.auto_optimization_interval == 3600
    
    def test_performance_thresholds_configuration(self, performance_monitor):
        """Test performance thresholds configuration."""
        thresholds = performance_monitor.performance_thresholds
        
        # Check all expected thresholds are present
        expected_thresholds = [
            'query_time_ms', 'sync_time_ms', 'memory_usage_mb',
            'error_rate_percent', 'throughput_per_second', 'cache_hit_rate',
            'storage_growth_rate_mb_per_hour'
        ]
        
        for threshold in expected_thresholds:
            assert threshold in thresholds
            assert isinstance(thresholds[threshold], (int, float))
    
    def test_collect_performance_metrics(self, performance_monitor):
        """Test comprehensive performance metrics collection."""
        metrics = performance_monitor.collect_performance_metrics()
        
        # Check metrics structure
        assert 'timestamp' in metrics
        assert 'collection_time_ms' in metrics
        assert 'database_metrics' in metrics
        assert 's3_metrics' in metrics
        assert 'query_metrics' in metrics
        assert 'system_metrics' in metrics
        assert 'cache_metrics' in metrics
        assert 'batch_metrics' in metrics
        
        # Check timestamp format
        assert isinstance(metrics['timestamp'], str)
        datetime.fromisoformat(metrics['timestamp'].replace('Z', '+00:00'))
        
        # Check collection time
        assert metrics['collection_time_ms'] >= 0
        
        # Check that metrics were stored in history
        assert len(performance_monitor.metrics_history) == 1
        assert performance_monitor.metrics_history[0] == metrics
    
    def test_database_metrics_collection(self, performance_monitor, mock_sqlite_conn):
        """Test database metrics collection."""
        metrics = performance_monitor.collect_performance_metrics()
        db_metrics = metrics['database_metrics']
        
        # Check database metrics structure
        assert 'total_objects' in db_metrics
        assert 'table_count' in db_metrics
        assert 'index_count' in db_metrics
        assert 'table_metrics' in db_metrics
        assert 'connection_status' in db_metrics
        
        # Check that database was queried
        mock_sqlite_conn.cursor.assert_called()
    
    def test_s3_metrics_collection(self, performance_monitor):
        """Test S3 metrics collection."""
        metrics = performance_monitor.collect_performance_metrics()
        s3_metrics = metrics['s3_metrics']
        
        # Check S3 metrics structure (mock data)
        assert 'sync_operations_count' in s3_metrics
        assert 'avg_sync_time_ms' in s3_metrics
        assert 'total_storage_bytes' in s3_metrics
        assert 'success_rate' in s3_metrics
        assert 'status' in s3_metrics
    
    def test_system_metrics_collection_with_psutil(self, performance_monitor):
        """Test system metrics collection with psutil."""
        with patch('psutil.cpu_percent', return_value=25.5), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            # Mock memory and disk info
            mock_memory.return_value = Mock(
                used=2147483648,  # 2GB
                total=8589934592,  # 8GB
                available=6442450944  # 6GB
            )
            mock_disk.return_value = Mock(
                used=53687091200,  # 50GB
                free=429496729600  # 400GB
            )
            
            metrics = performance_monitor.collect_performance_metrics()
            system_metrics = metrics['system_metrics']
            
            assert 'cpu_usage_percent' in system_metrics
            assert 'memory_usage_mb' in system_metrics
            assert 'memory_total_mb' in system_metrics
            assert 'memory_available_mb' in system_metrics
            assert 'disk_usage_gb' in system_metrics
            assert 'disk_free_gb' in system_metrics
            
            assert system_metrics['cpu_usage_percent'] == 25.5
            assert system_metrics['memory_usage_mb'] == 2048  # 2GB in MB
    
    def test_system_metrics_fallback_without_psutil(self, performance_monitor):
        """Test system metrics fallback when psutil is not available."""
        with patch('psutil.cpu_percent', side_effect=ImportError("psutil not available")):
            metrics = performance_monitor.collect_performance_metrics()
            system_metrics = metrics['system_metrics']
            
            # Should use mock values
            assert 'cpu_usage_percent' in system_metrics
            assert 'memory_usage_mb' in system_metrics
            assert 'note' in system_metrics
            assert 'psutil not available' in system_metrics['note']
    
    def test_analyze_performance_trends(self, performance_monitor):
        """Test performance trend analysis."""
        # Generate some test metrics over time
        base_time = datetime.now(timezone.utc)
        
        for i in range(10):
            metrics = {
                'timestamp': (base_time - timedelta(hours=i)).isoformat(),
                'query_metrics': {'avg_execution_time_ms': 1000 + i * 100},
                's3_metrics': {'avg_sync_time_ms': 2000 + i * 50},
                'system_metrics': {
                    'memory_usage_mb': 500 + i * 10,
                    'error_rate_percent': 0.5 + i * 0.1
                },
                'batch_metrics': {'avg_throughput_per_second': 100 - i * 2},
                'cache_metrics': {'hit_rate': 0.9 - i * 0.01}
            }
            performance_monitor.metrics_history.append(metrics)
        
        trends = performance_monitor.analyze_performance_trends(window_hours=24)
        
        # Check trends structure
        assert 'analysis_window_hours' in trends
        assert 'trends' in trends
        assert 'issues' in trends
        assert 'recommendations' in trends
        assert 'overall_health_score' in trends
        assert 'performance_grade' in trends
        
        # Check trend analysis details
        trend_data = trends['trends']
        assert 'query_time_trend' in trend_data
        assert 'memory_usage_trend' in trend_data
        assert 'cache_hit_rate_trend' in trend_data
        
        # Should identify increasing query times
        query_trend = trend_data['query_time_trend']
        assert query_trend['trend'] == 'increasing'
    
    def test_performance_alert_generation(self, performance_monitor):
        """Test performance alert generation."""
        # Create metrics that exceed thresholds
        high_performance_metrics = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'query_metrics': {'avg_execution_time_ms': 8000},  # Above 5000ms threshold
            'system_metrics': {
                'memory_usage_mb': 1200,  # Above 1000MB threshold
                'error_rate_percent': 2.5  # Above 1.0% threshold
            },
            'cache_metrics': {'hit_rate': 0.5}  # Below 0.8 threshold
        }
        
        performance_monitor.metrics_history.append(high_performance_metrics)
        performance_monitor._check_performance_alerts(high_performance_metrics)
        
        # Should have generated alerts
        assert len(performance_monitor.alerts) >= 3
        
        # Check alert types
        alert_metrics = [alert.metric_name for alert in performance_monitor.alerts]
        assert 'query_metrics.avg_execution_time_ms' in alert_metrics
        assert 'system_metrics.memory_usage_mb' in alert_metrics
        assert 'system_metrics.error_rate_percent' in alert_metrics
    
    def test_auto_optimization_execution(self, performance_monitor):
        """Test automated optimization execution."""
        # Set up conditions that trigger optimization
        performance_monitor.last_optimization_time = 0  # Force optimization
        
        # Create metrics that trigger optimization
        poor_metrics = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'query_metrics': {'avg_execution_time_ms': 7000},
            'cache_metrics': {'hit_rate': 0.6},
            's3_metrics': {'storage_growth_rate_mb_per_hour': 150}
        }
        
        with patch.object(performance_monitor, 'collect_performance_metrics', return_value=poor_metrics):
            result = performance_monitor.auto_optimize_based_on_metrics()
        
        # Should have executed optimizations
        assert 'optimization_actions' in result
        assert 'optimizations_applied' in result
        assert 'next_optimization_check' in result
        
        # Should have recorded optimization history
        assert len(performance_monitor.optimization_history) > 0
    
    def test_optimization_cooldown(self, performance_monitor):
        """Test optimization cooldown period."""
        # Set recent optimization time
        performance_monitor.last_optimization_time = time.time() - 1800  # 30 minutes ago
        
        result = performance_monitor.auto_optimize_based_on_metrics()
        
        # Should skip optimization due to cooldown
        assert result['message'] == 'Too soon for next optimization cycle'
    
    def test_optimization_disabled(self, performance_monitor):
        """Test behavior when optimization is disabled."""
        performance_monitor.optimization_enabled = False
        
        result = performance_monitor.auto_optimize_based_on_metrics()
        
        assert result['message'] == 'Auto-optimization is disabled'
    
    def test_optimization_actions(self, performance_monitor):
        """Test individual optimization actions."""
        # Test query optimization
        with patch.object(performance_monitor, '_is_metric_above_threshold', return_value=True):
            action = performance_monitor._optimize_slow_queries()
            
            assert action is not None
            assert isinstance(action, OptimizationAction)
            assert action.action_type == 'query_optimization'
            assert action.success is True
    
    def test_materialized_view_refresh(self, performance_monitor):
        """Test materialized view refresh optimization."""
        with patch.object(performance_monitor, '_are_materialized_views_stale', return_value=True):
            action = performance_monitor._refresh_stale_materialized_views()
            
            assert action is not None
            assert action.action_type == 'materialized_view_refresh'
            assert action.success is True
            assert 'views_refreshed' in action.parameters
    
    def test_cache_optimization(self, performance_monitor):
        """Test cache optimization action."""
        poor_metrics = {
            'cache_metrics': {'hit_rate': 0.5}  # Below threshold
        }
        
        with patch.object(performance_monitor, '_is_metric_below_threshold', return_value=True):
            action = performance_monitor._optimize_cache_settings()
            
            assert action is not None
            assert action.action_type == 'cache_optimization'
            assert action.success is True
    
    def test_performance_dashboard(self, performance_monitor):
        """Test performance dashboard data generation."""
        # Generate some test data
        test_metrics = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'query_metrics': {'avg_execution_time_ms': 1500},
            'system_metrics': {'memory_usage_mb': 600}
        }
        performance_monitor.metrics_history.append(test_metrics)
        
        dashboard = performance_monitor.get_performance_dashboard()
        
        # Check dashboard structure
        assert 'current_metrics' in dashboard
        assert 'trends' in dashboard
        assert 'active_alerts' in dashboard
        assert 'recent_optimizations' in dashboard
        assert 'system_status' in dashboard
        
        # Check system status
        system_status = dashboard['system_status']
        assert 'health_score' in system_status
        assert 'performance_grade' in system_status
        assert 'optimization_enabled' in system_status
    
    def test_health_score_calculation(self, performance_monitor):
        """Test health score calculation."""
        # Create test trends data
        trends = {
            'query_time_trend': {'current_value': 3000},  # Good performance
            'memory_usage_trend': {'current_value': 500},  # Good memory usage
            'error_rate_trend': {'current_value': 0.3},  # Low error rate
            'cache_hit_rate_trend': {'current_value': 0.85},  # Good cache performance
            'throughput_trend': {'current_value': 200}  # Good throughput
        }
        
        health_score = performance_monitor._calculate_health_score(trends)
        
        # Should be a good health score (above 0.8)
        assert 0 <= health_score <= 1
        assert health_score > 0.8
    
    def test_performance_grade_calculation(self, performance_monitor):
        """Test performance grade calculation."""
        test_cases = [
            (0.95, 'A+'),
            (0.85, 'A'),
            (0.75, 'B'),
            (0.65, 'C'),
            (0.55, 'D'),
            (0.35, 'F')
        ]
        
        for health_score, expected_grade in test_cases:
            grade = performance_monitor._calculate_performance_grade(health_score)
            assert grade == expected_grade
    
    def test_metric_threshold_checking(self, performance_monitor):
        """Test metric threshold checking utilities."""
        test_metrics = {
            'query_metrics': {'avg_execution_time_ms': 6000},
            'cache_metrics': {'hit_rate': 0.7}
        }
        
        # Test above threshold
        above = performance_monitor._is_metric_above_threshold(
            test_metrics, 'query_metrics.avg_execution_time_ms', 'query_time_ms'
        )
        assert above is True
        
        # Test below threshold
        below = performance_monitor._is_metric_below_threshold(
            test_metrics, 'cache_metrics.hit_rate', 'cache_hit_rate'
        )
        assert below is True
    
    def test_alert_severity_calculation(self, performance_monitor):
        """Test alert severity determination."""
        # Test critical severity (>50% deviation)
        severity_critical = performance_monitor._determine_alert_severity(
            'query_time_ms', 8000, 5000
        )
        assert severity_critical == 'critical'
        
        # Test high severity (25-50% deviation)
        severity_high = performance_monitor._determine_alert_severity(
            'query_time_ms', 6500, 5000
        )
        assert severity_high == 'high'
        
        # Test medium severity (10-25% deviation)
        severity_medium = performance_monitor._determine_alert_severity(
            'query_time_ms', 5700, 5000
        )
        assert severity_medium == 'medium'
    
    def test_metrics_history_rolling_window(self, performance_monitor):
        """Test that metrics history maintains rolling window."""
        # Generate more than the limit (10000) metrics
        for i in range(10050):
            metrics = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'test_metric': i
            }
            performance_monitor.metrics_history.append(metrics)
        
        # Trigger collection to check rolling window
        performance_monitor.collect_performance_metrics()
        
        # Should keep only last 10000 metrics
        assert len(performance_monitor.metrics_history) == 10000
    
    def test_issue_identification(self, performance_monitor):
        """Test performance issue identification."""
        # Create trends indicating issues
        trends = {
            'query_time_trend': {
                'trend': 'increasing',
                'change_percent': 25,
                'current_value': 6000
            },
            'memory_usage_trend': {
                'trend': 'increasing',
                'current_value': 900
            },
            'error_rate_trend': {
                'current_value': 1.5,
                'trend': 'increasing'
            },
            'cache_hit_rate_trend': {
                'current_value': 0.65,
                'trend': 'decreasing'
            }
        }
        
        issues = performance_monitor._identify_performance_issues(trends)
        
        assert len(issues) > 0
        
        # Check for expected issue types
        issue_types = [issue['type'] for issue in issues]
        expected_types = ['query_performance_degradation', 'high_error_rate', 'low_cache_hit_rate']
        
        for expected_type in expected_types:
            assert expected_type in issue_types
    
    def test_optimization_recommendations(self, performance_monitor):
        """Test optimization recommendation generation."""
        trends = {
            'query_time_trend': {'current_value': 7000, 'trend': 'increasing'}
        }
        
        issues = [
            {'type': 'query_performance_degradation', 'current_value': 7000}
        ]
        
        recommendations = performance_monitor._generate_optimization_recommendations(trends, issues)
        
        assert len(recommendations) > 0
        
        for rec in recommendations:
            assert 'priority' in rec
            assert 'category' in rec
            assert 'action' in rec
            assert 'description' in rec
            assert 'estimated_impact' in rec
            assert 'effort_level' in rec
    
    def test_concurrent_metrics_collection(self, performance_monitor):
        """Test thread safety of metrics collection."""
        import threading
        import concurrent.futures
        
        results = []
        exceptions = []
        
        def collect_metrics():
            try:
                metrics = performance_monitor.collect_performance_metrics()
                results.append(metrics)
            except Exception as e:
                exceptions.append(e)
        
        # Run concurrent collections
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(collect_metrics) for _ in range(10)]
            concurrent.futures.wait(futures)
        
        # Check results
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        assert len(results) == 10
        
        # All results should be valid metrics
        for metrics in results:
            assert 'timestamp' in metrics
            assert 'database_metrics' in metrics
    
    @patch('services.performance_monitor.logger')
    def test_logging_during_operations(self, mock_logger, performance_monitor):
        """Test that operations are properly logged."""
        performance_monitor.collect_performance_metrics()
        performance_monitor.auto_optimize_based_on_metrics()
        
        # Verify logging occurred
        mock_logger.info.assert_called()
        mock_logger.debug.assert_called()


class TestPerformanceAlert:
    """Test cases for PerformanceAlert data structure."""
    
    def test_alert_initialization(self):
        """Test PerformanceAlert initialization."""
        alert = PerformanceAlert(
            alert_id='alert_123',
            alert_type='threshold_exceeded',
            severity='high',
            metric_name='query_time_ms',
            current_value=7500.0,
            threshold_value=5000.0,
            description='Query execution time exceeded threshold',
            created_at=datetime.now(timezone.utc)
        )
        
        assert alert.alert_id == 'alert_123'
        assert alert.alert_type == 'threshold_exceeded'
        assert alert.severity == 'high'
        assert alert.metric_name == 'query_time_ms'
        assert alert.current_value == 7500.0
        assert alert.threshold_value == 5000.0
        assert alert.description == 'Query execution time exceeded threshold'
        assert isinstance(alert.created_at, datetime)
        assert alert.resolved_at is None
    
    def test_alert_severity_levels(self):
        """Test different alert severity levels."""
        severities = ['low', 'medium', 'high', 'critical']
        
        for severity in severities:
            alert = PerformanceAlert(
                alert_id=f'alert_{severity}',
                alert_type='test_alert',
                severity=severity,
                metric_name='test_metric',
                current_value=100.0,
                threshold_value=50.0,
                description=f'Test {severity} alert',
                created_at=datetime.now(timezone.utc)
            )
            assert alert.severity == severity


class TestOptimizationAction:
    """Test cases for OptimizationAction data structure."""
    
    def test_optimization_action_initialization(self):
        """Test OptimizationAction initialization."""
        action = OptimizationAction(
            action_id='action_123',
            action_type='query_optimization',
            description='Optimized slow-performing queries',
            parameters={'queries_optimized': 5, 'avg_improvement_ms': 2000},
            executed_at=datetime.now(timezone.utc),
            success=True,
            impact_metrics={'performance_gain_percent': 40}
        )
        
        assert action.action_id == 'action_123'
        assert action.action_type == 'query_optimization'
        assert action.description == 'Optimized slow-performing queries'
        assert action.parameters == {'queries_optimized': 5, 'avg_improvement_ms': 2000}
        assert isinstance(action.executed_at, datetime)
        assert action.success is True
        assert action.impact_metrics == {'performance_gain_percent': 40}
    
    def test_optimization_action_types(self):
        """Test different optimization action types."""
        action_types = [
            'query_optimization',
            'cache_optimization',
            'storage_cleanup',
            'materialized_view_refresh',
            'batch_size_optimization'
        ]
        
        for action_type in action_types:
            action = OptimizationAction(
                action_id=f'action_{action_type}',
                action_type=action_type,
                description=f'Test {action_type}',
                parameters={},
                executed_at=datetime.now(timezone.utc),
                success=True,
                impact_metrics={}
            )
            assert action.action_type == action_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
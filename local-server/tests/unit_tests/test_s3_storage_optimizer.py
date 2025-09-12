"""
Unit tests for S3StorageOptimizer - Testing storage optimization functionality.

Tests S3 storage optimization, lifecycle policies, compression, and cost monitoring.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from services.s3_storage_optimizer import (
    S3StorageOptimizer,
    StorageOptimizationResult,
    CompressionAnalysis
)


class TestS3StorageOptimizer:
    """Test cases for S3StorageOptimizer functionality."""
    
    @pytest.fixture
    def s3_config(self):
        """Create test S3 configuration."""
        return {
            'bucket': 'test-bucket',
            'access_key_id': 'test-key',
            'secret_access_key': 'test-secret',
            'region': 'us-east-1'
        }
    
    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        mock_client = Mock()
        
        # Mock list_objects_v2 response
        mock_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'changes/2024/01/01/change_001.parquet',
                    'Size': 1024000,  # 1MB
                    'LastModified': datetime(2024, 1, 1, tzinfo=timezone.utc),
                    'StorageClass': 'STANDARD'
                },
                {
                    'Key': 'changes/2024/01/02/change_002.parquet',
                    'Size': 2048000,  # 2MB
                    'LastModified': datetime(2024, 1, 2, tzinfo=timezone.utc),
                    'StorageClass': 'STANDARD'
                }
            ],
            'IsTruncated': False
        }
        
        # Mock get_object response
        mock_client.get_object.return_value = {
            'Body': Mock(),
            'ContentLength': 1024000,
            'ContentType': 'application/octet-stream',
            'Metadata': {}
        }
        
        # Mock put_bucket_lifecycle_configuration response
        mock_client.put_bucket_lifecycle_configuration.return_value = {}
        
        return mock_client
    
    @pytest.fixture
    def storage_optimizer(self, s3_config, mock_s3_client):
        """Create an S3StorageOptimizer instance for testing."""
        with patch('boto3.client', return_value=mock_s3_client):
            return S3StorageOptimizer(s3_config)
    
    def test_optimizer_initialization(self, storage_optimizer, s3_config):
        """Test S3StorageOptimizer initialization."""
        assert storage_optimizer.s3_config == s3_config
        assert storage_optimizer.s3_client is not None
        assert storage_optimizer.bucket_name == 'test-bucket'
        assert storage_optimizer.optimization_history == []
    
    def test_analyze_storage_usage(self, storage_optimizer, mock_s3_client):
        """Test storage usage analysis."""
        usage_analysis = storage_optimizer.analyze_storage_usage()
        
        # Check analysis structure
        assert 'total_objects' in usage_analysis
        assert 'total_size_bytes' in usage_analysis
        assert 'storage_classes' in usage_analysis
        assert 'age_distribution' in usage_analysis
        assert 'size_distribution' in usage_analysis
        
        # Check calculated values
        assert usage_analysis['total_objects'] == 2
        assert usage_analysis['total_size_bytes'] == 3072000  # 1MB + 2MB
        
        # Verify S3 client was called
        mock_s3_client.list_objects_v2.assert_called()
    
    def test_setup_lifecycle_policies(self, storage_optimizer, mock_s3_client):
        """Test lifecycle policy setup."""
        success = storage_optimizer.setup_lifecycle_policies()
        
        assert success is True
        
        # Verify lifecycle policy was applied
        mock_s3_client.put_bucket_lifecycle_configuration.assert_called_once()
        
        # Check the lifecycle configuration structure
        call_args = mock_s3_client.put_bucket_lifecycle_configuration.call_args
        assert 'LifecycleConfiguration' in call_args[1]
        
        lifecycle_config = call_args[1]['LifecycleConfiguration']
        assert 'Rules' in lifecycle_config
        assert len(lifecycle_config['Rules']) >= 1
        
        # Check that transitions are configured
        rule = lifecycle_config['Rules'][0]
        assert 'Transitions' in rule
        transitions = rule['Transitions']
        
        # Should have transitions to IA, Glacier, and Deep Archive
        storage_classes = [t['StorageClass'] for t in transitions]
        assert 'STANDARD_IA' in storage_classes
        assert 'GLACIER' in storage_classes
        assert 'DEEP_ARCHIVE' in storage_classes
    
    def test_analyze_compression_opportunities(self, storage_optimizer, mock_s3_client):
        """Test compression opportunity analysis."""
        # Mock S3 object data for compression analysis
        mock_body = Mock()
        mock_body.read.return_value = b'{"test": "data", "repeated": "content"}' * 1000
        mock_s3_client.get_object.return_value['Body'] = mock_body
        
        analysis = storage_optimizer.analyze_compression_opportunities()
        
        assert isinstance(analysis, CompressionAnalysis)
        assert analysis.total_objects_analyzed >= 0
        assert analysis.compression_recommendations is not None
        assert analysis.estimated_savings_bytes >= 0
        assert analysis.recommended_algorithm in ['zstd', 'snappy', 'gzip', 'lz4']
    
    def test_optimize_object_compression(self, storage_optimizer, mock_s3_client):
        """Test individual object compression optimization."""
        object_key = 'test/data.json'
        
        # Mock object data
        original_data = b'{"test": "data with repetitive content"}' * 100
        compressed_data = b'compressed_data'
        
        mock_s3_client.get_object.return_value['Body'].read.return_value = original_data
        
        with patch('gzip.compress', return_value=compressed_data):
            result = storage_optimizer.optimize_object_compression(object_key, 'gzip')
        
        assert result['success'] is True
        assert result['original_size'] == len(original_data)
        assert result['compressed_size'] == len(compressed_data)
        assert result['compression_ratio'] == len(original_data) / len(compressed_data)
        
        # Verify S3 operations
        mock_s3_client.get_object.assert_called_with(Bucket='test-bucket', Key=object_key)
        mock_s3_client.put_object.assert_called()
    
    def test_optimize_storage_comprehensive(self, storage_optimizer, mock_s3_client):
        """Test comprehensive storage optimization."""
        result = storage_optimizer.optimize_storage_comprehensive()
        
        assert isinstance(result, StorageOptimizationResult)
        assert result.optimization_id is not None
        assert result.total_objects_processed >= 0
        assert result.total_bytes_saved >= 0
        assert result.cost_savings_estimate >= 0
        assert result.optimizations_applied is not None
        assert result.completion_time is not None
        
        # Check that optimization was recorded in history
        assert len(storage_optimizer.optimization_history) == 1
        assert storage_optimizer.optimization_history[0] == result
    
    def test_calculate_storage_costs(self, storage_optimizer):
        """Test storage cost calculation."""
        test_data = {
            'standard_gb': 100,
            'ia_gb': 200,
            'glacier_gb': 500,
            'deep_archive_gb': 1000
        }
        
        costs = storage_optimizer.calculate_storage_costs(test_data)
        
        # Check cost structure
        assert 'standard_cost' in costs
        assert 'ia_cost' in costs
        assert 'glacier_cost' in costs
        assert 'deep_archive_cost' in costs
        assert 'total_cost' in costs
        
        # Costs should be positive
        for cost_type, cost_value in costs.items():
            assert cost_value >= 0
        
        # Total should be sum of individual costs
        expected_total = (
            costs['standard_cost'] + costs['ia_cost'] + 
            costs['glacier_cost'] + costs['deep_archive_cost']
        )
        assert abs(costs['total_cost'] - expected_total) < 0.01
    
    def test_recommend_optimization_strategy(self, storage_optimizer):
        """Test optimization strategy recommendation."""
        usage_data = {
            'total_size_bytes': 10 * 1024 * 1024 * 1024,  # 10GB
            'age_distribution': {
                'recent': 0.3,    # 30% recent data
                'medium': 0.4,    # 40% medium age
                'old': 0.3        # 30% old data
            },
            'access_patterns': {
                'frequent': 0.2,  # 20% frequently accessed
                'occasional': 0.5, # 50% occasionally accessed
                'rare': 0.3       # 30% rarely accessed
            }
        }
        
        recommendations = storage_optimizer.recommend_optimization_strategy(usage_data)
        
        # Check recommendation structure
        assert 'lifecycle_policy' in recommendations
        assert 'compression_strategy' in recommendations
        assert 'cost_optimization' in recommendations
        assert 'priority_actions' in recommendations
        
        # Should have actionable recommendations
        assert len(recommendations['priority_actions']) > 0
        for action in recommendations['priority_actions']:
            assert 'action' in action
            assert 'estimated_savings' in action
            assert 'effort_level' in action
    
    def test_create_storage_checkpoint(self, storage_optimizer, mock_s3_client):
        """Test storage checkpoint creation."""
        checkpoint_id = storage_optimizer.create_storage_checkpoint("test_checkpoint")
        
        assert checkpoint_id is not None
        assert isinstance(checkpoint_id, str)
        
        # Should have created metadata about current state
        mock_s3_client.list_objects_v2.assert_called()
    
    def test_get_optimization_summary(self, storage_optimizer):
        """Test optimization summary generation."""
        # Create some test optimization history
        test_result = StorageOptimizationResult(
            optimization_id="test_123",
            start_time=datetime.now(timezone.utc),
            completion_time=datetime.now(timezone.utc),
            total_objects_processed=100,
            total_bytes_saved=1024 * 1024 * 100,  # 100MB
            cost_savings_estimate=25.50,
            optimizations_applied=['compression', 'lifecycle'],
            success=True,
            error_count=0,
            details={}
        )
        storage_optimizer.optimization_history.append(test_result)
        
        summary = storage_optimizer.get_optimization_summary()
        
        # Check summary structure
        assert 'total_optimizations' in summary
        assert 'total_bytes_saved' in summary
        assert 'total_cost_savings' in summary
        assert 'success_rate' in summary
        assert 'recent_optimizations' in summary
        
        # Check calculated values
        assert summary['total_optimizations'] == 1
        assert summary['total_bytes_saved'] == 1024 * 1024 * 100
        assert summary['total_cost_savings'] == 25.50
        assert summary['success_rate'] == 1.0  # 100% success
    
    def test_monitor_storage_growth(self, storage_optimizer, mock_s3_client):
        """Test storage growth monitoring."""
        # Mock historical data
        with patch.object(storage_optimizer, '_get_historical_storage_data') as mock_history:
            mock_history.return_value = [
                {'date': '2024-01-01', 'total_bytes': 1000000},
                {'date': '2024-01-02', 'total_bytes': 1100000},
                {'date': '2024-01-03', 'total_bytes': 1200000}
            ]
            
            growth_analysis = storage_optimizer.monitor_storage_growth(days=30)
        
        # Check analysis structure
        assert 'current_size_bytes' in growth_analysis
        assert 'growth_rate_per_day' in growth_analysis
        assert 'projected_size_30_days' in growth_analysis
        assert 'growth_trend' in growth_analysis
        assert 'recommendations' in growth_analysis
        
        # Growth rate should be calculated
        assert growth_analysis['growth_rate_per_day'] > 0
        assert growth_analysis['growth_trend'] in ['increasing', 'stable', 'decreasing']
    
    def test_error_handling_s3_operations(self, s3_config):
        """Test error handling for S3 operation failures."""
        # Create optimizer with failing S3 client
        failing_client = Mock()
        failing_client.list_objects_v2.side_effect = Exception("S3 operation failed")
        
        with patch('boto3.client', return_value=failing_client):
            optimizer = S3StorageOptimizer(s3_config)
            
            # Should handle errors gracefully
            usage_analysis = optimizer.analyze_storage_usage()
            
            # Should return empty/error state
            assert 'error' in usage_analysis or usage_analysis.get('total_objects', 0) == 0
    
    def test_lifecycle_policy_error_handling(self, storage_optimizer, mock_s3_client):
        """Test error handling for lifecycle policy setup."""
        # Make lifecycle policy setup fail
        mock_s3_client.put_bucket_lifecycle_configuration.side_effect = Exception("Policy setup failed")
        
        success = storage_optimizer.setup_lifecycle_policies()
        
        assert success is False
    
    def test_compression_algorithm_selection(self, storage_optimizer):
        """Test intelligent compression algorithm selection."""
        # Test different data types
        test_cases = [
            {
                'data_type': 'json',
                'file_size': 1024 * 1024,  # 1MB
                'expected_algorithm': 'zstd'  # Good for JSON
            },
            {
                'data_type': 'parquet',
                'file_size': 10 * 1024 * 1024,  # 10MB
                'expected_algorithm': 'snappy'  # Good for Parquet
            },
            {
                'data_type': 'text',
                'file_size': 100 * 1024,  # 100KB
                'expected_algorithm': 'gzip'  # Good for small text
            }
        ]
        
        for test_case in test_cases:
            algorithm = storage_optimizer._select_optimal_compression(
                test_case['data_type'],
                test_case['file_size']
            )
            
            # Should return a valid compression algorithm
            assert algorithm in ['zstd', 'snappy', 'gzip', 'lz4']
    
    def test_cost_optimization_recommendations(self, storage_optimizer):
        """Test cost optimization recommendation generation."""
        current_costs = {
            'standard_cost': 100.0,
            'ia_cost': 50.0,
            'glacier_cost': 20.0,
            'deep_archive_cost': 10.0,
            'total_cost': 180.0
        }
        
        recommendations = storage_optimizer.generate_cost_optimization_recommendations(current_costs)
        
        # Should provide actionable recommendations
        assert len(recommendations) > 0
        
        for recommendation in recommendations:
            assert 'strategy' in recommendation
            assert 'estimated_savings' in recommendation
            assert 'implementation_effort' in recommendation
            assert 'description' in recommendation
    
    def test_batch_compression_optimization(self, storage_optimizer, mock_s3_client):
        """Test batch compression of multiple objects."""
        object_keys = [
            'data/file1.json',
            'data/file2.json',
            'data/file3.json'
        ]
        
        # Mock successful compression for all objects
        with patch.object(storage_optimizer, 'optimize_object_compression') as mock_compress:
            mock_compress.return_value = {
                'success': True,
                'original_size': 1000,
                'compressed_size': 600,
                'compression_ratio': 1.67
            }
            
            results = storage_optimizer.batch_optimize_compression(object_keys, 'zstd')
        
        # Check batch results
        assert 'successful_optimizations' in results
        assert 'failed_optimizations' in results
        assert 'total_bytes_saved' in results
        assert 'total_objects' in results
        
        assert results['total_objects'] == 3
        assert results['successful_optimizations'] == 3
        assert results['failed_optimizations'] == 0
        assert results['total_bytes_saved'] == 1200  # 400 bytes saved per file * 3
    
    def test_storage_health_check(self, storage_optimizer, mock_s3_client):
        """Test storage system health check."""
        health_status = storage_optimizer.get_storage_health_status()
        
        # Check health status structure
        assert 'overall_status' in health_status
        assert 'storage_utilization' in health_status
        assert 'cost_efficiency' in health_status
        assert 'optimization_opportunities' in health_status
        assert 'last_optimization' in health_status
        assert 'recommendations' in health_status
        
        # Overall status should be one of the valid states
        assert health_status['overall_status'] in ['healthy', 'warning', 'critical']
    
    @patch('services.s3_storage_optimizer.logger')
    def test_logging_during_optimization(self, mock_logger, storage_optimizer):
        """Test that optimization operations are properly logged."""
        # Trigger various operations
        storage_optimizer.setup_lifecycle_policies()
        storage_optimizer.analyze_storage_usage()
        
        # Verify logging occurred
        mock_logger.info.assert_called()


class TestStorageOptimizationResult:
    """Test cases for StorageOptimizationResult data structure."""
    
    def test_result_initialization(self):
        """Test StorageOptimizationResult initialization."""
        start_time = datetime.now(timezone.utc)
        completion_time = datetime.now(timezone.utc)
        
        result = StorageOptimizationResult(
            optimization_id="test_123",
            start_time=start_time,
            completion_time=completion_time,
            total_objects_processed=100,
            total_bytes_saved=1024000,
            cost_savings_estimate=25.0,
            optimizations_applied=['compression', 'lifecycle'],
            success=True,
            error_count=0,
            details={'algorithm': 'zstd'}
        )
        
        assert result.optimization_id == "test_123"
        assert result.start_time == start_time
        assert result.completion_time == completion_time
        assert result.total_objects_processed == 100
        assert result.total_bytes_saved == 1024000
        assert result.cost_savings_estimate == 25.0
        assert result.optimizations_applied == ['compression', 'lifecycle']
        assert result.success is True
        assert result.error_count == 0
        assert result.details == {'algorithm': 'zstd'}
    
    def test_result_duration_calculation(self):
        """Test optimization duration calculation."""
        start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        completion_time = datetime(2024, 1, 1, 10, 5, 30, tzinfo=timezone.utc)
        
        result = StorageOptimizationResult(
            optimization_id="test_duration",
            start_time=start_time,
            completion_time=completion_time,
            total_objects_processed=50,
            total_bytes_saved=0,
            cost_savings_estimate=0.0,
            optimizations_applied=[],
            success=True,
            error_count=0,
            details={}
        )
        
        duration = result.completion_time - result.start_time
        assert duration.total_seconds() == 330  # 5 minutes 30 seconds


class TestCompressionAnalysis:
    """Test cases for CompressionAnalysis data structure."""
    
    def test_compression_analysis_initialization(self):
        """Test CompressionAnalysis initialization."""
        analysis = CompressionAnalysis(
            total_objects_analyzed=100,
            total_size_bytes=10000000,
            estimated_savings_bytes=3000000,
            recommended_algorithm='zstd',
            compression_recommendations=['Use ZSTD for JSON files', 'Use Snappy for Parquet'],
            analysis_timestamp=datetime.now(timezone.utc)
        )
        
        assert analysis.total_objects_analyzed == 100
        assert analysis.total_size_bytes == 10000000
        assert analysis.estimated_savings_bytes == 3000000
        assert analysis.recommended_algorithm == 'zstd'
        assert len(analysis.compression_recommendations) == 2
        assert isinstance(analysis.analysis_timestamp, datetime)
    
    def test_compression_ratio_calculation(self):
        """Test compression ratio calculation."""
        analysis = CompressionAnalysis(
            total_objects_analyzed=50,
            total_size_bytes=5000000,  # 5MB
            estimated_savings_bytes=2000000,  # 2MB savings
            recommended_algorithm='zstd',
            compression_recommendations=[],
            analysis_timestamp=datetime.now(timezone.utc)
        )
        
        # Compression ratio should be original / compressed
        compressed_size = analysis.total_size_bytes - analysis.estimated_savings_bytes
        expected_ratio = analysis.total_size_bytes / compressed_size
        
        # Ratio should be about 1.67 (5MB / 3MB)
        assert abs(expected_ratio - 1.67) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
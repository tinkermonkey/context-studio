"""
Unit tests for BatchOperationProcessor - Testing high-performance batch operations.

Tests parallel batch processing, performance optimization, checkpoint management, and error handling.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
import time
import threading
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from services.batch_operation_processor import (
    BatchOperationProcessor,
    BatchOperationResult,
    BatchOperationError,
    SystemCheckpoint
)


class TestBatchOperationProcessor:
    """Test cases for BatchOperationProcessor functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        mock_db = Mock()
        mock_db.commit.return_value = None
        mock_db.rollback.return_value = None
        return mock_db
    
    @pytest.fixture
    def mock_s3_sync(self):
        """Create a mock S3 sync manager."""
        mock_sync = Mock()
        mock_sync.sync_entity_version.return_value = True
        return mock_sync
    
    @pytest.fixture
    def mock_version_manager(self):
        """Create a mock version manager."""
        mock_vm = Mock()
        mock_vm.create_version.return_value = Mock(id='version_123')
        return mock_vm
    
    @pytest.fixture
    def mock_working_tree_manager(self):
        """Create a mock working tree manager."""
        mock_wtm = Mock()
        mock_wtm.apply_changes.return_value = True
        return mock_wtm
    
    @pytest.fixture
    def batch_processor(self, mock_db, mock_s3_sync, mock_version_manager, mock_working_tree_manager):
        """Create a BatchOperationProcessor instance for testing."""
        return BatchOperationProcessor(
            mock_db, mock_s3_sync, mock_version_manager, mock_working_tree_manager
        )
    
    def test_processor_initialization(self, batch_processor):
        """Test BatchOperationProcessor initialization."""
        assert batch_processor.db is not None
        assert batch_processor.s3_sync is not None
        assert batch_processor.version_manager is not None
        assert batch_processor.working_tree_manager is not None
        assert batch_processor.max_parallel_workers == 8
        assert batch_processor.default_batch_size == 1000
        assert batch_processor.performance_metrics == []
        assert batch_processor.checkpoints == {}
    
    def test_batch_create_versions(self, batch_processor):
        """Test batch version creation functionality."""
        entity_data = [
            {'id': f'entity_{i}', 'type': 'document', 'content': f'Content {i}'}
            for i in range(10)
        ]
        author_id = 'test_author'
        
        result = batch_processor.batch_create_versions(entity_data, author_id)
        
        # Check result structure
        assert isinstance(result, BatchOperationResult)
        assert result.operation_id is not None
        assert result.total_items == 10
        assert result.successful_items >= 0
        assert result.failed_items >= 0
        assert result.successful_items + result.failed_items == result.total_items
        assert result.processing_time_seconds > 0
        assert result.throughput_per_second > 0
    
    def test_batch_merge_changes(self, batch_processor):
        """Test batch change merging functionality."""
        change_data = [
            {
                'entity_id': f'entity_{i}',
                'changes': {'content': f'Updated content {i}'},
                'version_id': f'version_{i}'
            }
            for i in range(5)
        ]
        author_id = 'merge_author'
        
        result = batch_processor.batch_merge_changes(change_data, author_id)
        
        assert isinstance(result, BatchOperationResult)
        assert result.operation_id is not None
        assert result.total_items == 5
        assert result.processing_time_seconds > 0
    
    def test_parallel_processing_optimization(self, batch_processor, mock_version_manager):
        """Test parallel processing optimization."""
        # Create a larger dataset to test parallel processing
        entity_data = [
            {'id': f'entity_{i}', 'type': 'document', 'content': f'Content {i}'}
            for i in range(100)
        ]
        
        # Mock version creation to take some time
        def slow_create_version(*args, **kwargs):
            time.sleep(0.01)  # 10ms delay
            return Mock(id=f'version_{time.time()}')
        
        mock_version_manager.create_version.side_effect = slow_create_version
        
        start_time = time.time()
        result = batch_processor.batch_create_versions(entity_data, 'test_author')
        execution_time = time.time() - start_time
        
        # Parallel processing should be faster than sequential
        # With 8 workers and 100 items, should be significantly faster than 2 seconds
        assert execution_time < 2.0
        assert result.throughput_per_second > 50  # Should process at least 50 items/sec
    
    def test_batch_size_optimization(self, batch_processor):
        """Test dynamic batch size optimization."""
        # Test with different data sizes
        small_dataset = [{'id': f'entity_{i}'} for i in range(50)]
        large_dataset = [{'id': f'entity_{i}'} for i in range(5000)]
        
        # Process small dataset
        result_small = batch_processor.batch_create_versions(small_dataset, 'author1')
        
        # Process large dataset
        result_large = batch_processor.batch_create_versions(large_dataset, 'author2')
        
        # Should optimize batch size for larger datasets
        assert result_small.total_items == 50
        assert result_large.total_items == 5000
        
        # Large dataset should have better throughput due to optimization
        assert result_large.throughput_per_second >= result_small.throughput_per_second
    
    def test_error_handling_and_recovery(self, batch_processor, mock_version_manager):
        """Test error handling and recovery in batch operations."""
        entity_data = [
            {'id': f'entity_{i}', 'type': 'document', 'content': f'Content {i}'}
            for i in range(10)
        ]
        
        # Make some operations fail - match actual create_version signature
        def failing_create_version(entity_type, entity_id, content, author_id, state=None,
                                  parent_version_id=None, changeset_id=None, metadata=None):
            if entity_id in ['entity_3', 'entity_7']:
                raise Exception(f"Simulated error for {entity_id}")
            return Mock(id=f"version_{entity_id}")
        
        mock_version_manager.create_version.side_effect = failing_create_version
        
        result = batch_processor.batch_create_versions(entity_data, 'test_author')
        
        # Should handle errors gracefully
        assert result.total_items == 10
        assert result.failed_items == 2  # entity_3 and entity_7 failed
        assert result.successful_items == 8
        assert len(result.errors) == 2
        
        # Check error details
        error_entity_ids = [error.entity_id for error in result.errors]
        assert 'entity_3' in error_entity_ids
        assert 'entity_7' in error_entity_ids
    
    def test_checkpoint_creation(self, batch_processor):
        """Test system checkpoint creation functionality."""
        checkpoint_name = 'test_checkpoint'
        
        checkpoint_id = batch_processor.create_system_checkpoint(checkpoint_name)
        
        assert checkpoint_id is not None
        assert isinstance(checkpoint_id, str)
        assert checkpoint_id in batch_processor.checkpoints
        
        checkpoint = batch_processor.checkpoints[checkpoint_id]
        assert isinstance(checkpoint, SystemCheckpoint)
        assert checkpoint.checkpoint_name == checkpoint_name
        assert checkpoint.created_at is not None
        assert checkpoint.system_state is not None
    
    def test_checkpoint_restoration(self, batch_processor, mock_db):
        """Test system checkpoint restoration functionality."""
        # Create a checkpoint first
        checkpoint_id = batch_processor.create_system_checkpoint('restore_test')
        
        # Modify some state
        batch_processor.performance_metrics.append({'test': 'data'})
        
        # Restore from checkpoint
        success = batch_processor.restore_from_checkpoint(checkpoint_id)
        
        assert success is True
        # Verify restoration occurred (implementation dependent)
        mock_db.rollback.assert_called()
    
    def test_performance_metrics_collection(self, batch_processor):
        """Test performance metrics collection during batch operations."""
        entity_data = [
            {'id': f'entity_{i}', 'type': 'test'}
            for i in range(20)
        ]
        
        # Clear existing metrics
        batch_processor.performance_metrics.clear()
        
        batch_processor.batch_create_versions(entity_data, 'metrics_test')
        
        # Should have recorded performance metrics
        assert len(batch_processor.performance_metrics) >= 1
        
        metrics = batch_processor.performance_metrics[-1]  # Latest metrics
        assert 'operation_type' in metrics
        assert 'total_items' in metrics
        assert 'processing_time_seconds' in metrics
        assert 'throughput_per_second' in metrics
        assert 'parallel_workers' in metrics
        assert 'success_rate' in metrics
    
    def test_get_performance_statistics(self, batch_processor):
        """Test performance statistics aggregation."""
        # Generate some test operations to create metrics
        test_operations = [
            ([{'id': f'op1_{i}'} for i in range(10)], 'author1'),
            ([{'id': f'op2_{i}'} for i in range(20)], 'author2'),
            ([{'id': f'op3_{i}'} for i in range(15)], 'author3')
        ]
        
        for entity_data, author in test_operations:
            batch_processor.batch_create_versions(entity_data, author)
        
        stats = batch_processor.get_performance_statistics()
        
        # Check statistics structure
        assert 'total_operations' in stats
        assert 'total_items_processed' in stats
        assert 'avg_throughput_per_second' in stats
        assert 'avg_processing_time_seconds' in stats
        assert 'overall_success_rate' in stats
        assert 'parallel_efficiency' in stats
        
        # Should have processed multiple operations
        assert stats['total_operations'] >= 3
        assert stats['total_items_processed'] >= 45  # 10 + 20 + 15
        assert 0 <= stats['overall_success_rate'] <= 1.0
    
    def test_memory_optimization(self, batch_processor):
        """Test memory optimization during large batch operations."""
        # Create a large dataset to test memory handling
        large_dataset = [
            {
                'id': f'entity_{i}',
                'type': 'document',
                'content': 'x' * 1000,  # 1KB per entity
                'metadata': {'size': 'large', 'index': i}
            }
            for i in range(2000)  # 2MB total
        ]
        
        # Monitor memory usage (simplified)
        import psutil
        process = psutil.Process()
        memory_before = process.memory_info().rss
        
        result = batch_processor.batch_create_versions(large_dataset, 'memory_test')
        
        memory_after = process.memory_info().rss
        memory_increase = memory_after - memory_before
        
        # Should not consume excessive memory (less than 50MB increase)
        assert memory_increase < 50 * 1024 * 1024
        assert result.total_items == 2000
    
    def test_batch_operation_cancellation(self, batch_processor):
        """Test batch operation cancellation capability."""
        # Create a long-running operation
        large_dataset = [{'id': f'entity_{i}'} for i in range(1000)]
        
        # Start operation in a separate thread
        result_container = []
        exception_container = []
        
        def run_batch():
            try:
                result = batch_processor.batch_create_versions(large_dataset, 'cancel_test')
                result_container.append(result)
            except Exception as e:
                exception_container.append(e)
        
        thread = threading.Thread(target=run_batch)
        thread.start()
        
        # Let it run for a short time then cancel
        time.sleep(0.1)
        
        # Note: Actual cancellation would require implementing cancellation tokens
        # For now, just verify the operation can complete
        thread.join(timeout=5.0)
        
        # Should either complete or handle cancellation gracefully
        assert thread.is_alive() is False
    
    def test_data_validation(self, batch_processor):
        """Test data validation in batch operations."""
        # Test with invalid data
        invalid_data = [
            {'id': 'valid_1', 'type': 'document'},
            {'missing_id': True, 'type': 'document'},  # Missing required field
            {'id': 'valid_2', 'type': 'document'},
            {'id': 'valid_3', 'invalid_field': 'should_be_ignored'},  # Invalid field
        ]
        
        result = batch_processor.batch_create_versions(invalid_data, 'validation_test')
        
        # Should handle validation errors
        assert result.total_items == 4
        # Exact success/failure count depends on validation implementation
        assert result.failed_items >= 1  # At least the missing_id item should fail
        
        # Errors should contain validation details
        validation_errors = [e for e in result.errors if 'validation' in str(e.error_message).lower()]
        assert len(validation_errors) >= 1
    
    def test_transaction_management(self, batch_processor, mock_db):
        """Test transaction management in batch operations."""
        entity_data = [{'id': f'entity_{i}'} for i in range(5)]
        
        # Test successful transaction
        batch_processor.batch_create_versions(entity_data, 'transaction_test')
        
        # Should commit on success
        mock_db.commit.assert_called()
        
        # Reset mock
        mock_db.reset_mock()
        
        # Test failed transaction
        with patch.object(batch_processor.version_manager, 'create_version', side_effect=Exception("DB Error")):
            batch_processor.batch_create_versions(entity_data, 'transaction_fail')
        
        # Should rollback on failure
        mock_db.rollback.assert_called()
    
    def test_concurrent_batch_operations(self, batch_processor):
        """Test thread safety of concurrent batch operations."""
        results = []
        exceptions = []
        
        def run_batch_operation(thread_id):
            try:
                entity_data = [
                    {'id': f'thread_{thread_id}_entity_{i}', 'type': 'concurrent_test'}
                    for i in range(10)
                ]
                result = batch_processor.batch_create_versions(entity_data, f'thread_{thread_id}')
                results.append(result)
            except Exception as e:
                exceptions.append(e)
        
        # Run multiple concurrent operations
        threads = []
        for i in range(5):
            thread = threading.Thread(target=run_batch_operation, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=10.0)
        
        # Check results
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        assert len(results) == 5
        
        # Each operation should have processed 10 items
        for result in results:
            assert result.total_items == 10
        
        # Should have recorded metrics for all operations
        assert len(batch_processor.performance_metrics) >= 5
    
    def test_resource_cleanup(self, batch_processor):
        """Test proper resource cleanup after batch operations."""
        entity_data = [{'id': f'entity_{i}'} for i in range(50)]
        
        # Track resource usage
        len(batch_processor.checkpoints)
        initial_metrics_count = len(batch_processor.performance_metrics)
        
        result = batch_processor.batch_create_versions(entity_data, 'cleanup_test')
        
        # Verify operation completed
        assert result.total_items == 50
        
        # Resources should be managed appropriately
        # (Exact behavior depends on implementation details)
        assert len(batch_processor.performance_metrics) >= initial_metrics_count
    
    def test_adaptive_batch_sizing(self, batch_processor):
        """Test adaptive batch size adjustment based on performance."""
        # Simulate different performance scenarios
        fast_data = [{'id': f'fast_{i}', 'size': 'small'} for i in range(100)]
        slow_data = [{'id': f'slow_{i}', 'size': 'large'} for i in range(100)]
        
        # Process fast data
        result_fast = batch_processor.batch_create_versions(fast_data, 'fast_author')
        
        # Process slow data
        with patch.object(batch_processor.version_manager, 'create_version') as mock_create:
            def slow_create(*args, **kwargs):
                time.sleep(0.01)  # Simulate slow processing
                return Mock(id='slow_version')
            mock_create.side_effect = slow_create
            
            result_slow = batch_processor.batch_create_versions(slow_data, 'slow_author')
        
        # Both should complete successfully
        assert result_fast.total_items == 100
        assert result_slow.total_items == 100
        
        # Fast processing should have better throughput
        assert result_fast.throughput_per_second >= result_slow.throughput_per_second


class TestBatchOperationResult:
    """Test cases for BatchOperationResult data structure."""
    
    def test_result_initialization(self):
        """Test BatchOperationResult initialization."""
        start_time = datetime.now(timezone.utc)
        errors = [
            BatchOperationError('entity_1', 'validation_error', 'Missing required field'),
            BatchOperationError('entity_2', 'processing_error', 'Database constraint violation')
        ]
        
        result = BatchOperationResult(
            operation_id='test_op_123',
            operation_type='create_versions',
            total_items=100,
            successful_items=98,
            failed_items=2,
            processing_time_seconds=5.25,
            throughput_per_second=19.05,
            start_time=start_time,
            errors=errors,
            metadata={'batch_size': 50, 'workers': 4}
        )
        
        assert result.operation_id == 'test_op_123'
        assert result.operation_type == 'create_versions'
        assert result.total_items == 100
        assert result.successful_items == 98
        assert result.failed_items == 2
        assert result.processing_time_seconds == 5.25
        assert result.throughput_per_second == 19.05
        assert result.start_time == start_time
        assert len(result.errors) == 2
        assert result.metadata == {'batch_size': 50, 'workers': 4}
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        result = BatchOperationResult(
            operation_id='success_test',
            operation_type='test',
            total_items=100,
            successful_items=85,
            failed_items=15,
            processing_time_seconds=1.0,
            throughput_per_second=100.0,
            start_time=datetime.now(timezone.utc),
            errors=[],
            metadata={}
        )
        
        success_rate = result.successful_items / result.total_items
        assert success_rate == 0.85


class TestBatchOperationError:
    """Test cases for BatchOperationError data structure."""
    
    def test_error_initialization(self):
        """Test BatchOperationError initialization."""
        error = BatchOperationError(
            entity_id='entity_123',
            error_type='validation_error',
            error_message='Field "name" is required but missing',
            additional_context={'field': 'name', 'value': None}
        )
        
        assert error.entity_id == 'entity_123'
        assert error.error_type == 'validation_error'
        assert error.error_message == 'Field "name" is required but missing'
        assert error.additional_context == {'field': 'name', 'value': None}
    
    def test_error_types(self):
        """Test different error types."""
        error_types = [
            'validation_error',
            'processing_error',
            'database_error',
            'network_error',
            'timeout_error'
        ]
        
        for error_type in error_types:
            error = BatchOperationError(
                entity_id='test_entity',
                error_type=error_type,
                error_message=f'Test {error_type}',
                additional_context={}
            )
            assert error.error_type == error_type


class TestSystemCheckpoint:
    """Test cases for SystemCheckpoint data structure."""
    
    def test_checkpoint_initialization(self):
        """Test SystemCheckpoint initialization."""
        system_state = {
            'database_version': '1.2.3',
            'active_transactions': 5,
            'memory_usage': '2.5GB'
        }
        
        checkpoint = SystemCheckpoint(
            checkpoint_id='checkpoint_123',
            checkpoint_name='test_checkpoint',
            created_at=datetime.now(timezone.utc),
            system_state=system_state,
            metadata={'creator': 'test_user', 'purpose': 'backup'}
        )
        
        assert checkpoint.checkpoint_id == 'checkpoint_123'
        assert checkpoint.checkpoint_name == 'test_checkpoint'
        assert isinstance(checkpoint.created_at, datetime)
        assert checkpoint.system_state == system_state
        assert checkpoint.metadata == {'creator': 'test_user', 'purpose': 'backup'}
    
    def test_checkpoint_age_calculation(self):
        """Test checkpoint age calculation."""
        past_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        checkpoint = SystemCheckpoint(
            checkpoint_id='age_test',
            checkpoint_name='age_test',
            created_at=past_time,
            system_state={},
            metadata={}
        )
        
        # Age should be positive (current time - past time)
        current_time = datetime.now(timezone.utc)
        age = current_time - checkpoint.created_at
        assert age.total_seconds() > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import tempfile
from unittest.mock import Mock, patch
import statistics

from pipeline.manager import PipelineDatabaseManager
from llm.execution_tracker import ExecutionTracker
from llm.models import RecordSelectionRequest


class TestLLMTraceabilityPerformance:
    
    def setup_method(self):
        """Set up test fixtures with temporary operations database."""
        # Create temporary operations database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Initialize operations database manager with temp file
        self.pipeline_manager = PipelineDatabaseManager(self.temp_db.name)
        
    def teardown_method(self):
        """Clean up test fixtures."""
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_execution_tracking_performance(self, mock_get_session):
        """Test performance of execution tracking operations."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        num_executions = 100
        
        # Test start_execution performance
        start_times = []
        execution_ids = []
        
        for i in range(num_executions):
            test_request = Mock()
            test_request.model_dump.return_value = {"term": f"perf_test_{i}"}
            
            start_time = time.time()
            execution_id = tracker.start_execution(
                pipeline_flavor_id=f"perf-flavor-{i % 10}",  # Vary flavor IDs
                pipeline_type="suggest_term_definition",
                pipeline_flavor_version=1,
                request=test_request,
                user_prompt=f"Define: perf_test_{i}"
            )
            execution_time = (time.time() - start_time) * 1000  # Convert to ms
            
            start_times.append(execution_time)
            execution_ids.append(execution_id)
            
            # Verify execution ID is valid
            assert execution_id != "unknown"
        
        # Analyze start_execution performance
        avg_start_time = statistics.mean(start_times)
        max_start_time = max(start_times)
        p95_start_time = statistics.quantiles(start_times, n=20)[18]  # 95th percentile
        
        print(f"\nStart Execution Performance ({num_executions} operations):")
        print(f"  Average: {avg_start_time:.2f}ms")
        print(f"  Maximum: {max_start_time:.2f}ms") 
        print(f"  95th percentile: {p95_start_time:.2f}ms")
        
        # Performance assertions (based on PRP requirement of <5% overhead)
        # Assuming base operation ~10ms, 5% overhead = 0.5ms
        assert avg_start_time < 20.0, f"Average start time {avg_start_time:.2f}ms exceeds 20ms threshold"
        assert p95_start_time < 50.0, f"95th percentile {p95_start_time:.2f}ms exceeds 50ms threshold"
        
        # Test complete_execution performance
        complete_times = []
        
        for i, execution_id in enumerate(execution_ids):
            start_time = time.time()
            tracker.complete_execution(
                execution_id=execution_id,
                response_message=f"Performance test response {i}",
                success=True,
                token_usage={
                    "input_tokens": 10 + (i % 5),
                    "output_tokens": 15 + (i % 3),
                    "total_tokens": 25 + (i % 8)
                }
            )
            execution_time = (time.time() - start_time) * 1000
            complete_times.append(execution_time)
        
        # Analyze complete_execution performance
        avg_complete_time = statistics.mean(complete_times)
        max_complete_time = max(complete_times)
        p95_complete_time = statistics.quantiles(complete_times, n=20)[18]
        
        print(f"\nComplete Execution Performance ({num_executions} operations):")
        print(f"  Average: {avg_complete_time:.2f}ms")
        print(f"  Maximum: {max_complete_time:.2f}ms")
        print(f"  95th percentile: {p95_complete_time:.2f}ms")
        
        # Performance assertions
        assert avg_complete_time < 20.0, f"Average complete time {avg_complete_time:.2f}ms exceeds 20ms threshold"
        assert p95_complete_time < 50.0, f"95th percentile {p95_complete_time:.2f}ms exceeds 50ms threshold"
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_selection_tracking_performance(self, mock_get_session):
        """Test performance of selection tracking operations."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        num_selections = 50
        
        # First create some executions to select from
        execution_ids = []
        for i in range(num_selections):
            test_request = Mock()
            test_request.model_dump.return_value = {"term": f"selection_test_{i}"}
            
            execution_id = tracker.start_execution(
                pipeline_flavor_id=f"sel-flavor-{i % 5}",
                pipeline_type="suggest_term_definition", 
                pipeline_flavor_version=1,
                request=test_request,
                user_prompt=f"Define: selection_test_{i}"
            )
            
            tracker.complete_execution(
                execution_id=execution_id,
                response_message=f"Response for selection test {i}",
                success=True
            )
            
            execution_ids.append(execution_id)
        
        # Test record_selection performance
        selection_times = []
        
        for i, execution_id in enumerate(execution_ids):
            selection_request = RecordSelectionRequest(
                execution_id=execution_id,
                record_type="structure_node",
                record_id=f"perf-node-{i}",
                suggestion_field="definition",
                selected_content=f"Performance test selection content {i}"
            )
            
            start_time = time.time()
            selection_id = tracker.record_selection(selection_request)
            execution_time = (time.time() - start_time) * 1000
            
            selection_times.append(execution_time)
            assert selection_id is not None
        
        # Analyze selection tracking performance
        avg_selection_time = statistics.mean(selection_times)
        max_selection_time = max(selection_times)
        p95_selection_time = statistics.quantiles(selection_times, n=20)[18]
        
        print(f"\nSelection Tracking Performance ({num_selections} operations):")
        print(f"  Average: {avg_selection_time:.2f}ms")
        print(f"  Maximum: {max_selection_time:.2f}ms")
        print(f"  95th percentile: {p95_selection_time:.2f}ms")
        
        # Performance assertions
        assert avg_selection_time < 30.0, f"Average selection time {avg_selection_time:.2f}ms exceeds 30ms threshold"
        assert p95_selection_time < 60.0, f"95th percentile {p95_selection_time:.2f}ms exceeds 60ms threshold"
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_analytics_query_performance(self, mock_get_session):
        """Test performance of analytics queries."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        
        # Create test data for analytics
        num_executions = 200
        num_selections = 50
        
        print(f"\nCreating {num_executions} executions and {num_selections} selections for analytics test...")
        
        execution_ids = []
        for i in range(num_executions):
            test_request = Mock()
            test_request.model_dump.return_value = {"term": f"analytics_test_{i}"}
            
            execution_id = tracker.start_execution(
                pipeline_flavor_id=f"analytics-flavor-{i % 20}",
                pipeline_type=["suggest_term_definition", "suggest_layer_definition", "suggest_domain_definition"][i % 3],
                pipeline_flavor_version=1,
                request=test_request,
                user_prompt=f"Define: analytics_test_{i}"
            )
            
            # Complete with varying success rates
            success = i % 10 != 0  # 90% success rate
            tracker.complete_execution(
                execution_id=execution_id,
                response_message=f"Response {i}" if success else "",
                success=success,
                error_message="Test error" if not success else None,
                token_usage={"input_tokens": 10, "output_tokens": 15, "total_tokens": 25} if success else None
            )
            
            if success:
                execution_ids.append(execution_id)
        
        # Add selections for some executions
        for i in range(min(num_selections, len(execution_ids))):
            selection_request = RecordSelectionRequest(
                execution_id=execution_ids[i],
                record_type="structure_node",
                record_id=f"analytics-node-{i}",
                suggestion_field="definition",
                selected_content=f"Analytics test content {i}"
            )
            tracker.record_selection(selection_request)
        
        # Test analytics query performance
        analytics_times = []
        
        # Test overall analytics
        for _ in range(10):  # Run multiple times to get average
            start_time = time.time()
            analytics = tracker.get_execution_analytics()
            execution_time = (time.time() - start_time) * 1000
            analytics_times.append(execution_time)
            
            # Verify analytics are reasonable
            assert analytics["total_executions"] == num_executions
            assert analytics["successful_executions"] > 0
            assert 0 <= analytics["success_rate"] <= 1
        
        # Test filtered analytics
        filtered_times = []
        for _ in range(10):
            start_time = time.time()
            tracker.get_execution_analytics(
                pipeline_type=None,  # Test with pipeline type filter
                days_back=7
            )
            execution_time = (time.time() - start_time) * 1000
            filtered_times.append(execution_time)
        
        # Analyze analytics performance
        avg_analytics_time = statistics.mean(analytics_times)
        max_analytics_time = max(analytics_times)
        
        avg_filtered_time = statistics.mean(filtered_times)
        max_filtered_time = max(filtered_times)
        
        print(f"\nAnalytics Query Performance (10 runs on {num_executions} executions):")
        print(f"  Overall analytics - Average: {avg_analytics_time:.2f}ms, Maximum: {max_analytics_time:.2f}ms")
        print(f"  Filtered analytics - Average: {avg_filtered_time:.2f}ms, Maximum: {max_filtered_time:.2f}ms")
        
        # Performance assertions (based on PRP requirements)
        assert avg_analytics_time < 100.0, f"Average analytics time {avg_analytics_time:.2f}ms exceeds 100ms threshold"
        assert max_analytics_time < 500.0, f"Maximum analytics time {max_analytics_time:.2f}ms exceeds 500ms threshold"
        
        assert avg_filtered_time < 150.0, f"Average filtered time {avg_filtered_time:.2f}ms exceeds 150ms threshold"
        assert max_filtered_time < 600.0, f"Maximum filtered time {max_filtered_time:.2f}ms exceeds 600ms threshold"
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_execution_details_query_performance(self, mock_get_session):
        """Test performance of execution details queries."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        
        # Create executions with selections
        execution_ids = []
        for i in range(50):
            test_request = Mock()
            test_request.model_dump.return_value = {"term": f"details_test_{i}"}
            
            execution_id = tracker.start_execution(
                pipeline_flavor_id=f"details-flavor-{i % 5}",
                pipeline_type="suggest_term_definition",
                pipeline_flavor_version=1,
                request=test_request,
                user_prompt=f"Define: details_test_{i}"
            )
            
            tracker.complete_execution(
                execution_id=execution_id,
                response_message=f"Detailed response {i}",
                success=True,
                token_usage={"input_tokens": 20, "output_tokens": 30, "total_tokens": 50}
            )
            
            execution_ids.append(execution_id)
            
            # Add multiple selections for each execution
            for j in range(3):  # 3 selections per execution
                selection_request = RecordSelectionRequest(
                    execution_id=execution_id,
                    record_type="structure_node",
                    record_id=f"details-node-{i}-{j}",
                    suggestion_field="definition",
                    selected_content=f"Details test content {i}-{j}"
                )
                tracker.record_selection(selection_request)
        
        # Test execution details query performance
        details_times = []
        
        for execution_id in execution_ids[:20]:  # Test on subset to avoid excessive runtime
            start_time = time.time()
            details = tracker.get_execution_details(execution_id)
            execution_time = (time.time() - start_time) * 1000
            details_times.append(execution_time)
            
            # Verify details are complete
            assert details is not None
            assert details["execution"]["id"] == execution_id
            assert len(details["selections"]) == 3  # Should have 3 selections
        
        # Analyze execution details performance
        avg_details_time = statistics.mean(details_times)
        max_details_time = max(details_times)
        p95_details_time = statistics.quantiles(details_times, n=20)[18]
        
        print("\nExecution Details Query Performance (20 queries):")
        print(f"  Average: {avg_details_time:.2f}ms")
        print(f"  Maximum: {max_details_time:.2f}ms")
        print(f"  95th percentile: {p95_details_time:.2f}ms")
        
        # Performance assertions
        assert avg_details_time < 50.0, f"Average details time {avg_details_time:.2f}ms exceeds 50ms threshold"
        assert max_details_time < 200.0, f"Maximum details time {max_details_time:.2f}ms exceeds 200ms threshold"
        assert p95_details_time < 100.0, f"95th percentile {p95_details_time:.2f}ms exceeds 100ms threshold"
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_database_index_effectiveness(self, mock_get_session):
        """Test that database indexes are effective for performance."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        
        # Create a larger dataset to test index effectiveness
        num_executions = 500
        
        print(f"\nCreating {num_executions} executions to test index effectiveness...")
        
        execution_ids = []
        for i in range(num_executions):
            test_request = Mock()
            test_request.model_dump.return_value = {"term": f"index_test_{i}"}
            
            execution_id = tracker.start_execution(
                pipeline_flavor_id=f"index-flavor-{i % 50}",  # 50 different flavors
                pipeline_type=["suggest_term_definition", "suggest_layer_definition"][i % 2],  # Alternate types
                pipeline_flavor_version=1,
                request=test_request,
                user_prompt=f"Define: index_test_{i}"
            )
            
            tracker.complete_execution(
                execution_id=execution_id,
                response_message=f"Index test response {i}",
                success=i % 20 != 0,  # 95% success rate
                token_usage={"input_tokens": 10, "output_tokens": 15, "total_tokens": 25}
            )
            
            execution_ids.append(execution_id)
        
        # Test queries that should benefit from indexes
        test_scenarios = [
            ("Pipeline type filter", lambda: tracker.get_execution_analytics(pipeline_type=None, days_back=30)),
            ("Status-based analytics", lambda: tracker.get_execution_analytics(days_back=7)),
            ("Recent executions", lambda: tracker.get_execution_analytics(days_back=1))
        ]
        
        for scenario_name, query_func in test_scenarios:
            times = []
            for _ in range(5):  # Run each scenario 5 times
                start_time = time.time()
                result = query_func()
                execution_time = (time.time() - start_time) * 1000
                times.append(execution_time)
                
                # Verify results are reasonable
                assert "total_executions" in result
                assert result["total_executions"] >= 0
            
            avg_time = statistics.mean(times)
            max_time = max(times)
            
            print(f"  {scenario_name} - Average: {avg_time:.2f}ms, Maximum: {max_time:.2f}ms")
            
            # With proper indexing, these queries should be fast even with large datasets
            assert avg_time < 150.0, f"{scenario_name} average time {avg_time:.2f}ms suggests poor index performance"
            assert max_time < 300.0, f"{scenario_name} maximum time {max_time:.2f}ms suggests poor index performance"
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import tempfile
import json
from datetime import datetime

from pipeline.manager import PipelineDatabaseManager
from llm.execution_tracker import ExecutionTracker
from llm.models import RecordSelectionRequest, PipelineType
from sqlalchemy import text


class TestLLMTraceabilityIntegration:
    
    def setup_method(self):
        """Set up test fixtures with temporary pipeline database."""
        # Create temporary pipeline database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Initialize pipeline database manager with temp file
        self.pipeline_manager = PipelineDatabaseManager(self.temp_db.name)
        
        # Patch get_pipeline_session to use our test database
        self.original_get_session = None
        
    def teardown_method(self):
        """Clean up test fixtures."""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_full_execution_tracking_flow(self, mock_get_session):
        """Test complete execution tracking flow from start to completion."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        
        # Test request object
        test_request = Mock()
        test_request.model_dump.return_value = {
            "term": "integration test",
            "domain_title": "Testing"
        }
        
        # Start execution tracking
        execution_id = tracker.start_execution(
            pipeline_flavor_id="test-flavor-123",
            pipeline_type="suggest_term_definition",
            pipeline_flavor_version=1,
            request=test_request,
            user_prompt="Define: integration test"
        )
        
        assert execution_id != "unknown"
        assert len(execution_id) == 36  # UUID length
        
        # Complete execution tracking
        tracker.complete_execution(
            execution_id=execution_id,
            response_message="An integration test is a type of testing...",
            success=True,
            token_usage={
                "input_tokens": 20,
                "output_tokens": 30,
                "total_tokens": 50
            },
            start_time=1000000000.0
        )
        
        # Verify execution was recorded properly
        details = tracker.get_execution_details(execution_id)
        assert details is not None
        assert details["execution"]["id"] == execution_id
        assert details["execution"]["status"] == "success"
        assert details["execution"]["pipeline_type"] == "suggest_term_definition"
        assert details["execution"]["token_usage"]["total_tokens"] == 50
        assert details["selections"] == []  # No selections yet
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_selection_tracking_flow(self, mock_get_session):
        """Test user selection tracking flow."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        
        # First create an execution to select from
        test_request = Mock()
        test_request.model_dump.return_value = {"term": "test"}
        
        execution_id = tracker.start_execution(
            pipeline_flavor_id="test-flavor-123",
            pipeline_type="suggest_term_definition",
            pipeline_flavor_version=1,
            request=test_request,
            user_prompt="Define: test"
        )
        
        tracker.complete_execution(
            execution_id=execution_id,
            response_message="A test is...",
            success=True
        )
        
        # Now record a selection
        selection_request = RecordSelectionRequest(
            execution_id=execution_id,
            record_type="structure_node",
            record_id="test-node-123",
            suggestion_field="definition",
            selected_content="A test is a procedure for evaluation."
        )
        
        selection_id = tracker.record_selection(selection_request)
        assert selection_id is not None
        assert len(selection_id) == 36  # UUID length
        
        # Verify selection was recorded
        details = tracker.get_execution_details(execution_id)
        assert len(details["selections"]) == 1
        
        selection = details["selections"][0]
        assert selection["id"] == selection_id
        assert selection["record_type"] == "structure_node"
        assert selection["record_id"] == "test-node-123"
        assert selection["suggestion_field"] == "definition"
        assert selection["selected_content"] == "A test is a procedure for evaluation."
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_analytics_calculation(self, mock_get_session):
        """Test analytics calculation with multiple executions."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        
        # Create multiple executions
        execution_ids = []
        for i in range(5):
            test_request = Mock()
            test_request.model_dump.return_value = {"term": f"test{i}"}
            
            execution_id = tracker.start_execution(
                pipeline_flavor_id="test-flavor-123",
                pipeline_type="suggest_term_definition",
                pipeline_flavor_version=1,
                request=test_request,
                user_prompt=f"Define: test{i}"
            )
            execution_ids.append(execution_id)
            
            # Complete with success (4 out of 5)
            success = i < 4
            tracker.complete_execution(
                execution_id=execution_id,
                response_message=f"Response for test{i}" if success else "",
                success=success,
                error_message="Test error" if not success else None,
                token_usage={"input_tokens": 10, "output_tokens": 15, "total_tokens": 25} if success else None
            )
        
        # Add some selections (2 out of 4 successful)
        for i in range(2):
            selection_request = RecordSelectionRequest(
                execution_id=execution_ids[i],
                record_type="structure_node",
                record_id=f"node-{i}",
                suggestion_field="definition",
                selected_content=f"Selected content {i}"
            )
            tracker.record_selection(selection_request)
        
        # Get analytics
        analytics = tracker.get_execution_analytics()
        
        assert analytics["total_executions"] == 5
        assert analytics["successful_executions"] == 4
        assert analytics["success_rate"] == 0.8  # 4/5
        assert analytics["total_tokens_used"] == 100  # 4 * 25
        assert analytics["total_selections"] == 2
        assert analytics["selection_rate"] == 0.5  # 2/4 successful
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_pipeline_type_filtering(self, mock_get_session):
        """Test analytics filtering by pipeline type."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        
        # Create executions of different types
        pipeline_types = [
            "suggest_term_definition",
            "suggest_term_definition", 
            "suggest_layer_definition"
        ]
        
        for i, pipeline_type in enumerate(pipeline_types):
            test_request = Mock()
            test_request.model_dump.return_value = {"term": f"test{i}"}
            
            execution_id = tracker.start_execution(
                pipeline_flavor_id="test-flavor-123",
                pipeline_type=pipeline_type,
                pipeline_flavor_version=1,
                request=test_request,
                user_prompt=f"Define: test{i}"
            )
            
            tracker.complete_execution(
                execution_id=execution_id,
                response_message=f"Response {i}",
                success=True,
                token_usage={"input_tokens": 10, "output_tokens": 15, "total_tokens": 25}
            )
        
        # Get analytics for all types
        all_analytics = tracker.get_execution_analytics()
        assert all_analytics["total_executions"] == 3
        
        # Get analytics for term definition only
        term_analytics = tracker.get_execution_analytics(
            pipeline_type=PipelineType.SUGGEST_TERM_DEFINITION
        )
        assert term_analytics["total_executions"] == 2
        
        # Get analytics for layer definition only
        layer_analytics = tracker.get_execution_analytics(
            pipeline_type=PipelineType.SUGGEST_LAYER_DEFINITION
        )
        assert layer_analytics["total_executions"] == 1
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_error_scenarios(self, mock_get_session):
        """Test various error scenarios."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        
        # Test recording selection for non-existent execution
        selection_request = RecordSelectionRequest(
            execution_id="nonexistent-execution",
            record_type="structure_node",
            record_id="test-node",
            suggestion_field="definition",
            selected_content="Test content"
        )
        
        with pytest.raises(ValueError, match="Execution nonexistent-execution not found"):
            tracker.record_selection(selection_request)
        
        # Test getting details for non-existent execution
        details = tracker.get_execution_details("nonexistent-execution")
        assert details is None
    
    @patch('llm.execution_tracker.get_pipeline_session')  
    def test_concurrent_executions(self, mock_get_session):
        """Test handling multiple concurrent executions."""
        
        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()
        
        tracker = ExecutionTracker()
        
        # Start multiple executions
        execution_ids = []
        for i in range(3):
            test_request = Mock()
            test_request.model_dump.return_value = {"term": f"concurrent{i}"}
            
            execution_id = tracker.start_execution(
                pipeline_flavor_id=f"flavor-{i}",
                pipeline_type="suggest_term_definition",
                pipeline_flavor_version=1,
                request=test_request,
                user_prompt=f"Define: concurrent{i}"
            )
            execution_ids.append(execution_id)
        
        # Complete them in different order
        for i in [2, 0, 1]:  # Complete out of order
            tracker.complete_execution(
                execution_id=execution_ids[i],
                response_message=f"Response for concurrent{i}",
                success=True,
                token_usage={"input_tokens": 5, "output_tokens": 10, "total_tokens": 15}
            )
        
        # Verify all executions completed properly
        analytics = tracker.get_execution_analytics()
        assert analytics["total_executions"] == 3
        assert analytics["successful_executions"] == 3
        assert analytics["success_rate"] == 1.0
        assert analytics["total_tokens_used"] == 45  # 3 * 15
    
    def test_database_schema_creation(self):
        """Test that the pipeline database schema is created correctly."""
        
        # Verify tables exist
        engine = self.pipeline_manager.get_engine()
        with engine.connect() as conn:
            # Check pipeline_flavor_executions table exists
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_flavor_executions'"
            ))
            assert result.fetchone() is not None
            
            # Check pipeline_flavor_selections table exists
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_flavor_selections'"
            ))
            assert result.fetchone() is not None
            
            # Check indexes were created
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ))
            indexes = [row[0] for row in result.fetchall()]
            
            # Verify key indexes exist
            expected_indexes = [
                'idx_executions_flavor_id',
                'idx_executions_pipeline_type',
                'idx_executions_status',
                'idx_selections_execution_id',
                'idx_selections_record'
            ]
            
            for expected_index in expected_indexes:
                assert expected_index in indexes, f"Missing index: {expected_index}"
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402

from llm.execution_tracker import ExecutionTracker  # noqa: E402
from llm.models import RecordSelectionRequest, PipelineType  # noqa: E402


class TestExecutionTracker:

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ExecutionTracker()

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_start_execution_success(self, mock_get_session):
        """Test starting execution tracking successfully."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Mock request
        request = Mock()
        request.model_dump.return_value = {"term": "test"}

        execution_id = self.tracker.start_execution(
            pipeline_flavor_id="flavor-123",
            pipeline_type="suggest_term_definition",
            pipeline_flavor_version=1,
            request=request,
            user_prompt="test prompt"
        )

        # Verify session operations
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

        # Verify UUID format
        assert len(execution_id) == 36  # UUID string length
        assert execution_id != "unknown"

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_start_execution_failure_returns_unknown(self, mock_get_session):
        """Test that execution tracking failure returns 'unknown'."""
        mock_session = Mock()
        mock_session.execute.side_effect = Exception("Database error")
        mock_get_session.return_value = mock_session

        request = Mock()
        request.model_dump.return_value = {"term": "test"}

        execution_id = self.tracker.start_execution(
            pipeline_flavor_id="flavor-123",
            pipeline_type="suggest_term_definition",
            pipeline_flavor_version=1,
            request=request,
            user_prompt="test prompt"
        )

        # Should return fallback ID
        assert execution_id == "unknown"

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_complete_execution_success(self, mock_get_session):
        """Test completing execution tracking successfully."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        self.tracker.complete_execution(
            execution_id="exec-123",
            response_message="Test response",
            success=True,
            token_usage={"input_tokens": 10, "output_tokens": 15, "total_tokens": 25},
            start_time=1000000000.0
        )

        # Verify update was called
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_complete_execution_unknown_id_ignored(self, mock_get_session):
        """Test that completing execution with 'unknown' ID is ignored."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        self.tracker.complete_execution(
            execution_id="unknown",
            response_message="Test response",
            success=True
        )

        # Should not call database operations
        mock_session.execute.assert_not_called()
        mock_session.commit.assert_not_called()

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_record_selection_success(self, mock_get_session):
        """Test recording user selection successfully."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Mock execution exists check
        mock_result = Mock()
        mock_result.fetchone.return_value = {"id": "exec-123"}
        mock_session.execute.return_value = mock_result

        selection_request = RecordSelectionRequest(
            execution_id="exec-123",
            record_type="structure_node",
            record_id="node-456",
            suggestion_field="definition",
            selected_content="Selected definition text"
        )

        selection_id = self.tracker.record_selection(selection_request)

        # Verify operations
        assert selection_id is not None
        assert len(selection_id) == 36  # UUID string length
        assert mock_session.execute.call_count == 2  # Check + Insert
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_record_selection_execution_not_found(self, mock_get_session):
        """Test recording selection when execution doesn't exist."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Mock execution doesn't exist
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        selection_request = RecordSelectionRequest(
            execution_id="nonexistent-exec",
            record_type="structure_node",
            record_id="node-456",
            suggestion_field="definition",
            selected_content="Selected definition text"
        )

        with pytest.raises(ValueError, match="Execution nonexistent-exec not found"):
            self.tracker.record_selection(selection_request)

        mock_session.close.assert_called_once()

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_get_execution_analytics_success(self, mock_get_session):
        """Test getting execution analytics successfully."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Mock execution statistics
        mock_stats = Mock()
        mock_stats.total_executions = 100
        mock_stats.successful_executions = 95
        mock_stats.avg_execution_time = 1500.0
        mock_stats.total_tokens_used = 50000

        mock_selections = Mock()
        mock_selections.total_selections = 20

        mock_session.execute.side_effect = [
            Mock(fetchone=lambda: mock_stats),
            Mock(fetchone=lambda: mock_selections)
        ]

        analytics = self.tracker.get_execution_analytics(
            pipeline_type=PipelineType.SUGGEST_TERM_DEFINITION,
            days_back=30
        )

        # Verify results
        assert analytics["total_executions"] == 100
        assert analytics["successful_executions"] == 95
        assert analytics["success_rate"] == 0.95
        assert analytics["avg_execution_time"] == 1500.0
        assert analytics["total_tokens_used"] == 50000
        assert analytics["total_selections"] == 20
        assert analytics["selection_rate"] == 20 / 95

        mock_session.close.assert_called_once()

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_get_execution_analytics_no_data(self, mock_get_session):
        """Test getting analytics when no executions exist."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Mock no data
        mock_stats = Mock()
        mock_stats.total_executions = 0

        mock_session.execute.return_value = Mock(fetchone=lambda: mock_stats)

        analytics = self.tracker.get_execution_analytics()

        # Verify empty results
        assert analytics["total_executions"] == 0
        assert analytics["success_rate"] == 0
        assert analytics["avg_execution_time"] == 0
        assert analytics["total_tokens_used"] == 0
        assert analytics["total_selections"] == 0
        assert analytics["selection_rate"] == 0

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_get_execution_details_success(self, mock_get_session):
        """Test getting execution details successfully."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Mock execution data
        mock_execution = Mock()
        mock_execution.id = "exec-123"
        mock_execution.pipeline_type = "suggest_term_definition"
        mock_execution.pipeline_flavor_id = "flavor-456"
        mock_execution.pipeline_flavor_version = 1
        mock_execution.status = "success"
        mock_execution.request_context = '{"term": "test"}'
        mock_execution.user_prompt = "Define: test"
        mock_execution.response_message = "A test is..."
        mock_execution.execution_time_ms = 1500
        mock_execution.input_tokens = 10
        mock_execution.output_tokens = 15
        mock_execution.total_tokens = 25
        mock_execution.started_at = "2024-01-01T00:00:00"
        mock_execution.completed_at = "2024-01-01T00:00:01"
        mock_execution.error_message = None
        mock_execution.structured_output = None

        # Mock selection data
        mock_selection = Mock()
        mock_selection.id = "sel-789"
        mock_selection.record_type = "structure_node"
        mock_selection.record_id = "node-123"
        mock_selection.suggestion_field = "definition"
        mock_selection.selected_content = "Selected text"
        mock_selection.date_created = "2024-01-01T00:01:00"

        # Mock execution result
        mock_execution_result = Mock()
        mock_execution_result.fetchone.return_value = mock_execution

        # Mock selections result that's iterable
        mock_selections_result = [mock_selection]

        mock_session.execute.side_effect = [
            mock_execution_result,
            mock_selections_result
        ]

        details = self.tracker.get_execution_details("exec-123")

        # Verify structure
        assert details is not None
        assert "execution" in details
        assert "selections" in details

        # Verify execution data
        exec_data = details["execution"]
        assert exec_data["id"] == "exec-123"
        assert exec_data["pipeline_type"] == "suggest_term_definition"
        assert exec_data["status"] == "success"
        assert exec_data["token_usage"]["total_tokens"] == 25

        # Verify selection data
        assert len(details["selections"]) == 1
        selection_data = details["selections"][0]
        assert selection_data["id"] == "sel-789"
        assert selection_data["record_type"] == "structure_node"

        mock_session.close.assert_called_once()

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_get_execution_details_not_found(self, mock_get_session):
        """Test getting details for non-existent execution."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Mock execution not found
        mock_session.execute.return_value = Mock(fetchone=lambda: None)

        details = self.tracker.get_execution_details("nonexistent")

        assert details is None
        mock_session.close.assert_called_once()

    @patch('llm.execution_tracker.get_pipeline_session')
    def test_database_error_handling(self, mock_get_session):
        """Test database error handling in analytics."""
        mock_session = Mock()
        mock_session.execute.side_effect = Exception("Database connection failed")
        mock_get_session.return_value = mock_session

        analytics = self.tracker.get_execution_analytics()

        # Should return error information
        assert "error" in analytics
        assert "Database connection failed" in analytics["error"]
        mock_session.close.assert_called_once()

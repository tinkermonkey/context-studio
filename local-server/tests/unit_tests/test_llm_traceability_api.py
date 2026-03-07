import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402

from api.llm_traceability import router  # noqa: E402
from llm.models import PipelineType  # noqa: E402

# Create test client
from fastapi import FastAPI  # noqa: E402
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestLLMTraceabilityAPI:

    @patch('api.llm_traceability.ExecutionTracker')
    def test_record_selection_success(self, mock_tracker_class):
        """Test successful selection recording."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.record_selection.return_value = "selection-123"

        response = client.post("/api/llm/record-selection", json={
            "execution_id": "exec-123",
            "record_type": "structure_node",
            "record_id": "node-456",
            "suggestion_field": "definition",
            "selected_content": "Test definition"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["selection_id"] == "selection-123"
        assert data["message"] == "Selection recorded successfully"

        # Verify tracker was called correctly
        mock_tracker.record_selection.assert_called_once()
        call_args = mock_tracker.record_selection.call_args[0][0]
        assert call_args.execution_id == "exec-123"
        assert call_args.record_type == "structure_node"
        assert call_args.record_id == "node-456"
        assert call_args.suggestion_field == "definition"
        assert call_args.selected_content == "Test definition"

    @patch('api.llm_traceability.ExecutionTracker')
    def test_record_selection_invalid_execution(self, mock_tracker_class):
        """Test selection recording with invalid execution ID."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.record_selection.side_effect = ValueError("Execution not found")

        response = client.post("/api/llm/record-selection", json={
            "execution_id": "nonexistent",
            "record_type": "structure_node",
            "record_id": "node-456",
            "suggestion_field": "definition",
            "selected_content": "Test definition"
        })

        assert response.status_code == 400
        data = response.json()
        assert "Execution not found" in data["detail"]

    @patch('api.llm_traceability.ExecutionTracker')
    def test_record_selection_server_error(self, mock_tracker_class):
        """Test selection recording with server error."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.record_selection.side_effect = Exception("Database error")

        response = client.post("/api/llm/record-selection", json={
            "execution_id": "exec-123",
            "record_type": "structure_node",
            "record_id": "node-456",
            "suggestion_field": "definition",
            "selected_content": "Test definition"
        })

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Failed to record selection"

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_execution_analytics_success(self, mock_tracker_class):
        """Test successful execution analytics retrieval."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_execution_analytics.return_value = {
            "total_executions": 100,
            "successful_executions": 95,
            "success_rate": 0.95,
            "avg_execution_time": 1500.0,
            "total_tokens_used": 50000,
            "total_selections": 20,
            "selection_rate": 0.21
        }

        response = client.get("/api/llm/execution-analytics?days_back=7")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_executions"] == 100
        assert data["data"]["success_rate"] == 0.95
        assert data["filters"]["days_back"] == 7
        assert data["filters"]["pipeline_type"] == "all"

        # Verify tracker was called with correct parameters
        mock_tracker.get_execution_analytics.assert_called_once_with(None, 7)

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_execution_analytics_with_pipeline_type(self, mock_tracker_class):
        """Test execution analytics with pipeline type filter."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_execution_analytics.return_value = {
            "total_executions": 50,
            "successful_executions": 48,
            "success_rate": 0.96,
            "avg_execution_time": 1200.0,
            "total_tokens_used": 25000,
            "total_selections": 10,
            "selection_rate": 0.208
        }

        response = client.get(
            "/api/llm/execution-analytics"
            "?pipeline_type=suggest_term_definition"
            "&days_back=30"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_executions"] == 50
        assert data["filters"]["pipeline_type"] == "suggest_term_definition"
        assert data["filters"]["days_back"] == 30

        # Verify tracker was called with pipeline type
        mock_tracker.get_execution_analytics.assert_called_once()
        call_args = mock_tracker.get_execution_analytics.call_args[0]
        assert call_args[0] == PipelineType.SUGGEST_TERM_DEFINITION
        assert call_args[1] == 30

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_execution_analytics_error(self, mock_tracker_class):
        """Test execution analytics with error."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_execution_analytics.side_effect = Exception("Analytics error")

        response = client.get("/api/llm/execution-analytics")

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Failed to get execution analytics"

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_execution_details_success(self, mock_tracker_class):
        """Test successful execution details retrieval."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_execution_details.return_value = {
            "execution": {
                "id": "exec-123",
                "pipeline_type": "suggest_term_definition",
                "status": "success",
                "execution_time_ms": 1500,
                "token_usage": {
                    "input_tokens": 10,
                    "output_tokens": 15,
                    "total_tokens": 25
                }
            },
            "selections": [
                {
                    "id": "sel-456",
                    "record_type": "structure_node",
                    "suggestion_field": "definition",
                    "selected_content": "Test content"
                }
            ]
        }

        response = client.get("/api/llm/execution-details/exec-123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["execution"]["id"] == "exec-123"
        assert data["data"]["execution"]["status"] == "success"
        assert len(data["data"]["selections"]) == 1

        # Verify tracker was called with correct ID
        mock_tracker.get_execution_details.assert_called_once_with("exec-123")

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_execution_details_not_found(self, mock_tracker_class):
        """Test execution details for non-existent execution."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_execution_details.return_value = None

        response = client.get("/api/llm/execution-details/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "Execution nonexistent not found" in data["detail"]

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_execution_details_error(self, mock_tracker_class):
        """Test execution details with server error."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_execution_details.side_effect = Exception("Database error")

        response = client.get("/api/llm/execution-details/exec-123")

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Failed to get execution details"

    @patch('api.llm_traceability.ExecutionTracker')
    def test_traceability_health_success(self, mock_tracker_class):
        """Test traceability health check success."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_execution_analytics.return_value = {
            "total_executions": 10,
            "success_rate": 0.9
        }

        response = client.get("/api/llm/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "llm_traceability"
        assert data["database_accessible"] is True
        assert "timestamp" in data

    @patch('api.llm_traceability.ExecutionTracker')
    def test_traceability_health_unhealthy(self, mock_tracker_class):
        """Test traceability health check failure."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_execution_analytics.side_effect = Exception("Health check failed")

        response = client.get("/api/llm/health")

        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "LLM traceability service unhealthy"

    def test_record_selection_validation_error(self):
        """Test selection recording with validation error."""

        # Missing required fields
        response = client.post("/api/llm/record-selection", json={
            "execution_id": "exec-123",
            "record_type": "structure_node"
            # Missing required fields
        })

        assert response.status_code == 422  # Validation error

    def test_get_execution_analytics_invalid_pipeline_type(self):
        """Test analytics with invalid pipeline type."""

        response = client.get("/api/llm/execution-analytics?pipeline_type=invalid_type")

        assert response.status_code == 422  # Validation error

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_execution_history_success(self, mock_tracker_class):
        """Test successful execution history retrieval."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_flavor_execution_history.return_value = {
            "executions": [
                {
                    "id": "exec-123",
                    "pipeline_type": "suggest_term_definition",
                    "status": "success",
                    "execution_time_ms": 1500,
                    "token_usage": {
                        "input_tokens": 10,
                        "output_tokens": 15,
                        "total_tokens": 25
                    },
                    "started_at": "2024-01-01T10:00:00Z",
                    "completed_at": "2024-01-01T10:00:01Z"
                }
            ],
            "total_count": 5,
            "flavor_id": "test-flavor-123"
        }

        response = client.get("/api/llm/execution-history?flavor_id=test-flavor-123&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["flavor_id"] == "test-flavor-123"
        assert data["total_count"] == 5
        assert len(data["executions"]) == 1
        assert data["executions"][0]["id"] == "exec-123"
        assert data["executions"][0]["status"] == "success"

        # Verify tracker was called with correct parameters
        mock_tracker.get_flavor_execution_history.assert_called_once_with("test-flavor-123", 10)

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_execution_history_invalid_flavor(self, mock_tracker_class):
        """Test execution history with invalid flavor ID."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_flavor_execution_history.return_value = {
            "executions": [],
            "total_count": 0,
            "flavor_id": "nonexistent-flavor"
        }

        response = client.get("/api/llm/execution-history?flavor_id=nonexistent-flavor&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["flavor_id"] == "nonexistent-flavor"
        assert data["total_count"] == 0
        assert len(data["executions"]) == 0

        # Verify tracker was called with correct parameters
        mock_tracker.get_flavor_execution_history.assert_called_once_with("nonexistent-flavor", 10)

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_execution_history_error(self, mock_tracker_class):
        """Test execution history with server error."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_flavor_execution_history.side_effect = Exception("Database error")

        response = client.get("/api/llm/execution-history?flavor_id=test-flavor-123")

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Failed to get execution history"

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_flavor_analytics_success(self, mock_tracker_class):
        """Test successful flavor analytics retrieval."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_flavor_analytics.return_value = {
            "flavor_id": "test-flavor-123",
            "analytics": {
                "total_executions": 50,
                "successful_executions": 45,
                "success_rate": 0.9,
                "avg_execution_time": 1200.0,
                "total_tokens_used": 25000,
                "total_selections": 15,
                "selection_rate": 0.33
            },
            "time_range_days": 7
        }

        response = client.get("/api/llm/flavor-analytics/test-flavor-123?days_back=7")

        assert response.status_code == 200
        data = response.json()
        assert data["flavor_id"] == "test-flavor-123"
        assert data["time_range_days"] == 7
        assert data["analytics"]["total_executions"] == 50
        assert data["analytics"]["success_rate"] == 0.9
        assert data["analytics"]["total_selections"] == 15

        # Verify tracker was called with correct parameters
        mock_tracker.get_flavor_analytics.assert_called_once_with("test-flavor-123", 7)

    @patch('api.llm_traceability.ExecutionTracker')
    def test_get_flavor_analytics_error(self, mock_tracker_class):
        """Test flavor analytics with server error."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_flavor_analytics.side_effect = Exception("Analytics error")

        response = client.get("/api/llm/flavor-analytics/test-flavor-123")

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Failed to get flavor analytics"

    @patch('api.llm_traceability.ExecutionTracker')
    def test_execution_details_endpoint_renamed(self, mock_tracker_class):
        """Test that execution-details endpoint still works after rename."""

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        mock_tracker.get_execution_details.return_value = {
            "execution": {
                "id": "exec-123",
                "pipeline_type": "suggest_term_definition",
                "status": "success",
                "execution_time_ms": 1500
            },
            "selections": []
        }

        response = client.get("/api/llm/execution-details/exec-123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["execution"]["id"] == "exec-123"

        # Verify tracker was called with correct ID
        mock_tracker.get_execution_details.assert_called_once_with("exec-123")

    def test_get_execution_history_validation_error(self):
        """Test execution history with missing required parameters."""

        # Missing required flavor_id parameter
        response = client.get("/api/llm/execution-history")

        assert response.status_code == 422  # Validation error

    def test_get_flavor_analytics_validation_error(self):
        """Test flavor analytics with invalid days_back parameter."""

        # Invalid days_back parameter (should be int but provided as string)
        response = client.get("/api/llm/flavor-analytics/test-flavor?days_back=invalid")

        assert response.status_code == 422  # Validation error

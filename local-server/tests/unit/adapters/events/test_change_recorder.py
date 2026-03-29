"""Unit tests for ChangeEventRecorder."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../'))

from unittest.mock import Mock
import pytest

from domain.extraction.events import ExtractionCompleted
from domain.pipeline.events import PipelineExecuted
from adapters.events.change_recorder import ChangeEventRecorder


@pytest.fixture
def mock_change_repo():
    """Create a mock change repository."""
    return Mock()


@pytest.fixture
def recorder(mock_change_repo):
    """Create a ChangeEventRecorder with mock repo."""
    return ChangeEventRecorder(mock_change_repo)


class TestChangeEventRecorder:
    """Tests for ChangeEventRecorder."""

    def test_on_extraction_completed_records_change(self, recorder, mock_change_repo):
        """Test that ExtractionCompleted event is recorded."""
        mock_change_repo.record_change.return_value = "change-123"
        event = ExtractionCompleted(
            result_id="result-456",
            entity_count=42,
            duration_ms=1250.5,
        )

        recorder.on_extraction_completed(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "result-456"
        assert call_args.kwargs['entity_type'] == "extraction_result"
        assert call_args.kwargs['operation'] == "create"
        assert call_args.kwargs['new_state']['entity_count'] == 42
        assert call_args.kwargs['new_state']['duration_ms'] == 1250.5

    def test_on_extraction_completed_handles_exception(self, recorder, mock_change_repo):
        """Test that repo exceptions are caught and logged."""
        mock_change_repo.record_change.side_effect = RuntimeError("DB error")
        event = ExtractionCompleted(
            result_id="result-456",
            entity_count=42,
            duration_ms=1250.5,
        )

        # Should not raise
        recorder.on_extraction_completed(event)

        mock_change_repo.record_change.assert_called_once()

    def test_on_pipeline_executed_records_change(self, recorder, mock_change_repo):
        """Test that PipelineExecuted event is recorded."""
        mock_change_repo.record_change.return_value = "change-789"
        event = PipelineExecuted(
            execution_id="exec-123",
            pipeline_id="pipeline-456",
            status="success",
        )

        recorder.on_pipeline_executed(event)

        mock_change_repo.record_change.assert_called_once()
        call_args = mock_change_repo.record_change.call_args
        assert call_args.kwargs['entity_id'] == "exec-123"
        assert call_args.kwargs['entity_type'] == "pipeline_execution"
        assert call_args.kwargs['operation'] == "create"
        assert call_args.kwargs['new_state']['pipeline_id'] == "pipeline-456"
        assert call_args.kwargs['new_state']['status'] == "success"

    def test_on_pipeline_executed_handles_exception(self, recorder, mock_change_repo):
        """Test that repo exceptions are caught and logged."""
        mock_change_repo.record_change.side_effect = RuntimeError("DB error")
        event = PipelineExecuted(
            execution_id="exec-123",
            pipeline_id="pipeline-456",
            status="success",
        )

        # Should not raise
        recorder.on_pipeline_executed(event)

        mock_change_repo.record_change.assert_called_once()

"""
Unit tests for title change detection in EventProcessor.

Tests edge cases and error handling for the title change detection logic.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from utils.event_processor import EventProcessor


class TestTitleChangeDetection:
    """Unit tests for title change detection logic."""

    @pytest.fixture
    def event_processor(self):
        """Create a mock EventProcessor for testing."""
        processor = EventProcessor(
            database_url="sqlite:///:memory:",
            poll_interval=1.0,
            max_events=10
        )
        # Mock the logger to avoid logging during tests
        processor.logger = Mock()
        return processor

    def test_detect_title_change_valid(self, event_processor):
        """Test detection of valid title change."""

        # Create mock event with title change
        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({
            "title": "old title",
            "definition": "test"
        })
        event.new_data = json.dumps({
            "title": "new title",
            "definition": "test"
        })

        # Mock the enqueue method
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify enqueue was called with correct parameters
            mock_enqueue.assert_called_once_with(event.record_id, "new title")

    def test_no_title_change_same_title(self, event_processor):
        """Test that no action is taken when title doesn't change."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({
            "title": "same title",
            "definition": "old definition"
        })
        event.new_data = json.dumps({
            "title": "same title",
            "definition": "new definition"
        })

        # Mock the enqueue method
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify enqueue was NOT called
            mock_enqueue.assert_not_called()

    def test_malformed_json_old_data(self, event_processor):
        """Test handling of malformed JSON in old_data."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = "not valid json{"
        event.new_data = json.dumps({"title": "new title"})

        # Should not raise exception
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify error was logged
            assert event_processor.logger.error.called

            # Verify enqueue was NOT called
            mock_enqueue.assert_not_called()

    def test_malformed_json_new_data(self, event_processor):
        """Test handling of malformed JSON in new_data."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({"title": "old title"})
        event.new_data = "not valid json{"

        # Should not raise exception
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify error was logged
            assert event_processor.logger.error.called

            # Verify enqueue was NOT called
            mock_enqueue.assert_not_called()

    def test_missing_title_in_old_data(self, event_processor):
        """Test handling when title is missing from old_data."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({"definition": "test"})  # No title
        event.new_data = json.dumps({"title": "new title"})

        # Should not trigger re-analysis (no old title to compare)
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify enqueue was NOT called
            mock_enqueue.assert_not_called()

    def test_missing_title_in_new_data(self, event_processor):
        """Test handling when title is missing from new_data."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({"title": "old title"})
        event.new_data = json.dumps({"definition": "test"})  # No title

        # Should not trigger re-analysis (no new title)
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify enqueue was NOT called
            mock_enqueue.assert_not_called()

    def test_empty_title_strings(self, event_processor):
        """Test handling of empty title strings."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({"title": ""})
        event.new_data = json.dumps({"title": ""})

        # Should not trigger re-analysis (empty titles)
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify enqueue was NOT called
            mock_enqueue.assert_not_called()

    def test_null_old_data(self, event_processor):
        """Test handling when old_data is None."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = None
        event.new_data = json.dumps({"title": "new title"})

        # Should not trigger re-analysis (no old data)
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify enqueue was NOT called
            mock_enqueue.assert_not_called()

    def test_null_new_data(self, event_processor):
        """Test handling when new_data is None."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({"title": "old title"})
        event.new_data = None

        # Should not trigger re-analysis (no new data)
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify enqueue was NOT called
            mock_enqueue.assert_not_called()

    def test_whitespace_only_title(self, event_processor):
        """Test handling of whitespace-only titles."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({"title": "   "})
        event.new_data = json.dumps({"title": "   "})

        # Should not trigger re-analysis (whitespace-only titles are functionally empty)
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify enqueue was NOT called (whitespace is treated as valid but no change)
            mock_enqueue.assert_not_called()

    def test_title_change_case_sensitive(self, event_processor):
        """Test that title comparison is case-sensitive."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({"title": "Bank"})
        event.new_data = json.dumps({"title": "bank"})

        # Should trigger re-analysis (case change is considered a change)
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify enqueue WAS called (case change counts as title change)
            mock_enqueue.assert_called_once_with(event.record_id, "bank")

    def test_enqueue_nlp_reanalysis_task_manager_not_initialized(self, event_processor):
        """Test handling when TaskManager is not initialized."""

        with patch('services.task_manager.get_task_manager') as mock_get_tm:
            mock_get_tm.side_effect = RuntimeError("TaskManager not initialized")

            # Should not raise exception
            event_processor._enqueue_nlp_reanalysis(str(uuid4()), "test title")

            # Verify warning was logged
            assert event_processor.logger.warning.called

    def test_enqueue_nlp_reanalysis_exception_handling(self, event_processor):
        """Test exception handling in _enqueue_nlp_reanalysis."""

        with patch('services.task_manager.get_task_manager') as mock_get_tm:
            mock_get_tm.side_effect = Exception("Unexpected error")

            # Should not raise exception
            event_processor._enqueue_nlp_reanalysis(str(uuid4()), "test title")

            # Verify error was logged
            assert event_processor.logger.error.called

    def test_dict_old_data_not_string(self, event_processor):
        """Test handling when old_data is already a dict (not JSON string)."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = {"title": "old title"}  # Already a dict
        event.new_data = {"title": "new title"}  # Already a dict

        # Should handle gracefully
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:
            event_processor._handle_title_change(event)

            # Verify enqueue was called
            mock_enqueue.assert_called_once_with(event.record_id, "new title")


class TestNLPReanalysisEdgeCases:
    """Unit tests for NLP re-analysis edge cases."""

    @pytest.fixture
    def event_processor(self):
        """Create a mock EventProcessor for testing."""
        processor = EventProcessor(
            database_url="sqlite:///:memory:",
            poll_interval=1.0,
            max_events=10
        )
        processor.logger = Mock()
        return processor

    @pytest.mark.asyncio
    async def test_nlp_pipeline_not_initialized(self, event_processor):
        """Test handling when NLP pipeline is not initialized."""

        with patch('nlp.pipeline.get_pipeline') as mock_get_pipeline:
            mock_pipeline = Mock()
            mock_pipeline.is_initialized.return_value = False
            mock_get_pipeline.return_value = mock_pipeline

            result = await event_processor._perform_nlp_reanalysis(str(uuid4()), "test")

            # Should return error result
            assert result['success'] is False
            assert 'error' in result

    @pytest.mark.asyncio
    async def test_nlp_pipeline_unavailable(self, event_processor):
        """Test handling when NLP pipeline is unavailable."""

        with patch('nlp.pipeline.get_pipeline') as mock_get_pipeline:
            mock_pipeline = Mock()
            mock_pipeline.is_initialized.return_value = True
            mock_pipeline.get_nlp.return_value = None
            mock_get_pipeline.return_value = mock_pipeline

            result = await event_processor._perform_nlp_reanalysis(str(uuid4()), "test")

            # Should return error result
            assert result['success'] is False
            assert 'error' in result

    @pytest.mark.asyncio
    async def test_node_not_found(self, event_processor):
        """Test handling when structure node is not found."""

        with patch('nlp.pipeline.get_pipeline') as mock_get_pipeline:
            mock_pipeline = Mock()
            mock_pipeline.is_initialized.return_value = True
            mock_nlp = Mock()
            mock_pipeline.get_nlp.return_value = mock_nlp

            mock_get_pipeline.return_value = mock_pipeline

            # Mock process_nlp_result
            with patch('nlp.processors.process_nlp_result') as mock_process:
                mock_process.return_value = Mock(tokens=[])

                # Mock WordSenseService to raise ValueError (node not found)
                with patch('services.word_sense_service.WordSenseService') as mock_wss:
                    mock_service = Mock()
                    mock_service.update_word_senses.side_effect = ValueError("StructureNode not found")
                    mock_wss.return_value = mock_service

                    # Mock _get_optimized_session
                    with patch.object(event_processor, '_get_optimized_session') as mock_session:
                        mock_session.return_value.__enter__.return_value = Mock()

                        result = await event_processor._perform_nlp_reanalysis(str(uuid4()), "test")

                        # Should return error result
                        assert result['success'] is False
                        assert 'error' in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

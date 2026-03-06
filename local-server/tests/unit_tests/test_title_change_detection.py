"""
Unit tests for title change detection in EventProcessor.

Tests edge cases and error handling for the title change detection logic.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # noqa: E501

import pytest  # noqa: E402
import json  # noqa: E402
from unittest.mock import Mock, patch, MagicMock  # noqa: E402
from uuid import uuid4  # noqa: E402

from utils.event_processor import EventProcessor  # noqa: E402


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
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
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
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
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
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
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
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
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
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
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
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
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
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
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
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
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
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
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

        # Should not trigger re-analysis (whitespace-only titles are functionally empty)  # noqa: E501
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
            event_processor._handle_title_change(event)

            # Verify enqueue was NOT called (whitespace is treated as valid but no change)  # noqa: E501
            mock_enqueue.assert_not_called()

    def test_title_change_case_sensitive(self, event_processor):
        """Test that title comparison is case-sensitive."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({"title": "Bank"})
        event.new_data = json.dumps({"title": "bank"})

        # Should trigger re-analysis (case change is considered a change)
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
            event_processor._handle_title_change(event)

            # Verify enqueue WAS called (case change counts as title change)
            mock_enqueue.assert_called_once_with(event.record_id, "bank")

    def test_enqueue_nlp_reanalysis_task_manager_not_initialized(self, event_processor):  # noqa: E501
        """Test handling when TaskManager is not initialized."""

        with patch('services.task_manager.get_task_manager') as mock_get_tm:
            mock_get_tm.side_effect = RuntimeError("TaskManager not initialized")  # noqa: E501

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
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
            event_processor._handle_title_change(event)

            # Verify enqueue was called
            mock_enqueue.assert_called_once_with(event.record_id, "new title")

    def test_empty_title_validation(self, event_processor):
        """Test validation of empty title after whitespace stripping."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({"title": "old title"})
        event.new_data = json.dumps({"title": "   "})  # Whitespace only

        # Should not trigger re-analysis (empty after strip)
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
            event_processor._handle_title_change(event)

            # Verify warning was logged
            assert event_processor.logger.warning.called

            # Verify enqueue was NOT called
            mock_enqueue.assert_not_called()

    def test_title_length_validation(self, event_processor):
        """Test validation of title length exceeding maximum."""

        event = Mock()
        event.record_id = str(uuid4())
        event.operation = "update"
        event.old_data = json.dumps({"title": "old title"})
        # Create a title longer than MAX_TITLE_LENGTH
        long_title = "a" * (event_processor.MAX_TITLE_LENGTH + 1)
        event.new_data = json.dumps({"title": long_title})

        # Should not trigger re-analysis (title too long)
        with patch.object(event_processor, '_enqueue_nlp_reanalysis') as mock_enqueue:  # noqa: E501
            event_processor._handle_title_change(event)

            # Verify warning was logged
            assert event_processor.logger.warning.called

            # Verify enqueue was NOT called
            mock_enqueue.assert_not_called()

    def test_concurrent_title_changes_race_condition(self, event_processor):
        """Test prevention of concurrent updates for the same node."""
        import threading
        import time

        node_id = str(uuid4())

        event1 = Mock()
        event1.record_id = node_id
        event1.operation = "update"
        event1.old_data = json.dumps({"title": "old title"})
        event1.new_data = json.dumps({"title": "new title 1"})

        event2 = Mock()
        event2.record_id = node_id
        event2.operation = "update"
        event2.old_data = json.dumps({"title": "old title"})
        event2.new_data = json.dumps({"title": "new title 2"})

        enqueue_calls = []

        def slow_enqueue(node_id, title):
            enqueue_calls.append((node_id, title))
            time.sleep(0.1)  # Simulate slow processing

        with patch.object(event_processor, '_enqueue_nlp_reanalysis', side_effect=slow_enqueue):  # noqa: E501
            # Start processing first event in thread 1
            thread1 = threading.Thread(target=event_processor._handle_title_change, args=(event1,))  # noqa: E501
            thread1.start()

            # Small delay to ensure thread1 acquires lock
            time.sleep(0.01)

            # Try to process second event for same node in thread 2
            thread2 = threading.Thread(target=event_processor._handle_title_change, args=(event2,))  # noqa: E501
            thread2.start()

            thread1.join()
            thread2.join()

            # Only one call should have been made (first one that got the lock)
            assert len(enqueue_calls) == 1

            # Verify info log about skipping was called
            assert event_processor.logger.info.called


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

            result = await event_processor._perform_nlp_reanalysis(str(uuid4()), "test")  # noqa: E501

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

            result = await event_processor._perform_nlp_reanalysis(str(uuid4()), "test")  # noqa: E501

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
                with patch('services.word_sense_service.WordSenseService') as mock_wss:  # noqa: E501
                    mock_service = Mock()
                    mock_service.update_word_senses.side_effect = ValueError("StructureNode not found")  # noqa: E501
                    mock_wss.return_value = mock_service

                    # Mock _get_optimized_session
                    with patch.object(event_processor, '_get_optimized_session') as mock_session:  # noqa: E501
                        mock_session.return_value.__enter__.return_value = Mock()  # noqa: E501

                        result = await event_processor._perform_nlp_reanalysis(str(uuid4()), "test")  # noqa: E501

                        # Should return error result
                        assert result['success'] is False
                        assert 'error' in result

    @pytest.mark.asyncio
    async def test_transient_error_retry_success(self, event_processor):
        """Test retry logic succeeds after transient error."""

        with patch('nlp.pipeline.get_pipeline') as mock_get_pipeline:
            mock_pipeline = Mock()
            mock_pipeline.is_initialized.return_value = True
            mock_nlp = Mock()
            mock_nlp.return_value = Mock()  # Mock doc result
            mock_pipeline.get_nlp.return_value = mock_nlp

            mock_get_pipeline.return_value = mock_pipeline

            # Mock process_nlp_result
            with patch('nlp.processors.process_nlp_result') as mock_process:
                mock_process.return_value = Mock(tokens=[])

                # Mock WordSenseService - fail first time, succeed second time
                call_count = [0]

                def update_word_senses_side_effect(*args, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        raise ConnectionError("Temporary connection error")
                    return []

                with patch('services.word_sense_service.WordSenseService') as mock_wss:  # noqa: E501
                    mock_service = Mock()
                    mock_service.extract_word_senses.return_value = []
                    mock_service.update_word_senses.side_effect = update_word_senses_side_effect  # noqa: E501
                    mock_wss.return_value = mock_service

                    # Mock _get_optimized_session and db.begin()
                    with patch.object(event_processor, '_get_optimized_session') as mock_session:  # noqa: E501
                        mock_db = MagicMock()
                        mock_session.return_value.__enter__.return_value = mock_db  # noqa: E501

                        result = await event_processor._perform_nlp_reanalysis(str(uuid4()), "test")  # noqa: E501

                        # Should succeed after retry
                        assert result['success'] is True
                        assert result['attempts'] == 2

    @pytest.mark.asyncio
    async def test_transient_error_retry_exhausted(self, event_processor):
        """Test retry logic exhausts all attempts with transient errors."""

        with patch('nlp.pipeline.get_pipeline') as mock_get_pipeline:
            mock_pipeline = Mock()
            mock_pipeline.is_initialized.return_value = True
            mock_nlp = Mock()
            mock_nlp.return_value = Mock()  # Mock doc result
            mock_pipeline.get_nlp.return_value = mock_nlp

            mock_get_pipeline.return_value = mock_pipeline

            # Mock process_nlp_result
            with patch('nlp.processors.process_nlp_result') as mock_process:
                mock_process.return_value = Mock(tokens=[])

                # Mock WordSenseService - always fail with transient error
                with patch('services.word_sense_service.WordSenseService') as mock_wss:  # noqa: E501
                    mock_service = Mock()
                    mock_service.extract_word_senses.return_value = []
                    mock_service.update_word_senses.side_effect = ConnectionError("Persistent connection error")  # noqa: E501
                    mock_wss.return_value = mock_service

                    # Mock _get_optimized_session and db.begin()
                    with patch.object(event_processor, '_get_optimized_session') as mock_session:  # noqa: E501
                        mock_db = MagicMock()
                        mock_session.return_value.__enter__.return_value = mock_db  # noqa: E501

                        result = await event_processor._perform_nlp_reanalysis(str(uuid4()), "test")  # noqa: E501

                        # Should fail after all retries
                        assert result['success'] is False
                        assert result['attempts'] == event_processor.NLP_RETRY_ATTEMPTS  # noqa: E501
                        assert 'error' in result

    @pytest.mark.asyncio
    async def test_non_transient_error_no_retry(self, event_processor):
        """Test non-transient errors fail immediately without retry."""

        with patch('nlp.pipeline.get_pipeline') as mock_get_pipeline:
            mock_pipeline = Mock()
            mock_pipeline.is_initialized.return_value = True
            mock_nlp = Mock()
            mock_nlp.return_value = Mock()  # Mock doc result
            mock_pipeline.get_nlp.return_value = mock_nlp

            mock_get_pipeline.return_value = mock_pipeline

            # Mock process_nlp_result
            with patch('nlp.processors.process_nlp_result') as mock_process:
                mock_process.return_value = Mock(tokens=[])

                # Mock WordSenseService - fail with non-transient error
                with patch('services.word_sense_service.WordSenseService') as mock_wss:  # noqa: E501
                    mock_service = Mock()
                    mock_service.extract_word_senses.return_value = []
                    mock_service.update_word_senses.side_effect = ValueError("Invalid node ID")  # noqa: E501
                    mock_wss.return_value = mock_service

                    # Mock _get_optimized_session and db.begin()
                    with patch.object(event_processor, '_get_optimized_session') as mock_session:  # noqa: E501
                        mock_db = MagicMock()
                        mock_session.return_value.__enter__.return_value = mock_db  # noqa: E501

                        result = await event_processor._perform_nlp_reanalysis(str(uuid4()), "test")  # noqa: E501

                        # Should fail immediately without retries
                        assert result['success'] is False
                        assert result['attempts'] == 1  # Only first attempt
                        assert 'error' in result

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, event_processor):
        """Test that database transaction is properly managed on error."""

        with patch('nlp.pipeline.get_pipeline') as mock_get_pipeline:
            mock_pipeline = Mock()
            mock_pipeline.is_initialized.return_value = True
            mock_nlp = Mock()
            mock_nlp.return_value = Mock()
            mock_pipeline.get_nlp.return_value = mock_nlp

            mock_get_pipeline.return_value = mock_pipeline

            with patch('nlp.processors.process_nlp_result') as mock_process:
                mock_process.return_value = Mock(tokens=[])

                with patch('services.word_sense_service.WordSenseService') as mock_wss:  # noqa: E501
                    mock_service = Mock()
                    mock_service.extract_word_senses.return_value = []
                    # Simulate error during transaction
                    mock_service.update_word_senses.side_effect = ValueError("Database error")  # noqa: E501
                    mock_wss.return_value = mock_service

                    with patch.object(event_processor, '_get_optimized_session') as mock_session:  # noqa: E501
                        mock_db = MagicMock()
                        mock_session.return_value.__enter__.return_value = mock_db  # noqa: E501

                        result = await event_processor._perform_nlp_reanalysis(str(uuid4()), "test")  # noqa: E501

                        # Verify transaction begin was called
                        assert mock_db.begin.called

                        # Should fail
                        assert result['success'] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

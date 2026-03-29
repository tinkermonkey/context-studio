"""
Integration tests verifying that event handler failures are logged in services.

This test suite validates that ExtractionService and PipelineService properly
capture and log event publishing failures, ensuring operators have visibility
into audit trail gaps.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from unittest.mock import MagicMock, patch
from domain.extraction.services import ExtractionService
from domain.extraction.events import ExtractionCompleted
from domain.pipeline.services import PipelineService
from domain.pipeline.events import PipelineExecuted
from adapters.events.in_process import InProcessEventPublisher


class TestExtractionServiceEventHandlerFailures:
    """Test ExtractionService logs event handler failures."""

    def test_logs_warning_when_extraction_completion_event_fails(self):
        """ExtractionService should log warning when event handlers fail."""
        # Create publisher that simulates handler failure
        publisher = InProcessEventPublisher()

        def failing_handler(event):
            raise ValueError("Simulated handler failure")

        failing_handler.__name__ = "audit_recorder"
        publisher.subscribe(ExtractionCompleted, failing_handler)

        # Mock the extraction service to capture log output
        with patch('domain.extraction.services._logger') as mock_logger:
            # Create a minimal extraction service with the publisher
            service = ExtractionService(
                event_publisher=publisher,
                ontology_repo=MagicMock(),
                graph_service=MagicMock(),
                nlp_processor=MagicMock(),
                llm_provider=MagicMock(),
                reference_source=MagicMock(),
                embedding_service=MagicMock(),
                extraction_repo=MagicMock(),
            )

            # Mock the internal extraction pipeline to avoid complex setup
            with patch.object(service, '_execute_extraction_pipeline', return_value=MagicMock()):
                service.extract_from_text(
                    text="test",
                    classes=["test_class"],
                )

            # Verify logger.warning was called for handler failures
            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args
            assert "Event handlers failed" in call_args[0][0]
            assert "audit_recorder" in call_args[0][2]


class TestPipelineServiceEventHandlerFailures:
    """Test PipelineService logs event handler failures."""

    def test_logs_warning_when_execution_event_fails(self):
        """PipelineService should log warning when event handlers fail."""
        # Create publisher that simulates handler failure
        publisher = InProcessEventPublisher()

        def failing_handler(event):
            raise ValueError("Simulated handler failure")

        failing_handler.__name__ = "audit_recorder"
        publisher.subscribe(PipelineExecuted, failing_handler)

        # Mock the pipeline service to capture log output
        with patch('domain.pipeline.services._logger') as mock_logger:
            # Create a minimal pipeline service with the publisher
            service = PipelineService(
                event_publisher=publisher,
                pipeline_repo=MagicMock(),
                llm_gateway=MagicMock(),
            )

            # Mock the internal pipeline execution
            config = MagicMock()
            config.id = "test_config"
            with patch.object(service, '_execute_pipeline', return_value=("success", None)):
                service.execute_pipeline(config)

            # Verify logger.warning was called for handler failures
            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args
            assert "Event handlers failed" in call_args[0][0]
            assert "audit_recorder" in call_args[0][2]


class TestInProcessEventPublisherFailureReporting:
    """Test InProcessEventPublisher correctly reports failures."""

    def test_publish_returns_failure_tuples(self):
        """InProcessEventPublisher.publish() should return (handler_name, exception) tuples."""
        publisher = InProcessEventPublisher()

        # Subscribe multiple handlers, some that fail
        successes = []

        def good_handler(event):
            successes.append("good_1")
        good_handler.__name__ = "good_handler"

        def bad_handler(event):
            raise ValueError("Intentional failure")
        bad_handler.__name__ = "bad_handler"

        publisher.subscribe(ExtractionCompleted, good_handler)
        publisher.subscribe(ExtractionCompleted, bad_handler)

        # Publish event and check return value
        event = ExtractionCompleted(result_id="test", entity_count=0, duration_ms=100)
        failures = publisher.publish(event)

        # Verify good handler executed and bad handler failure was reported
        assert successes == ["good_1"]
        assert len(failures) == 1
        assert failures[0][0] == "bad_handler"
        assert isinstance(failures[0][1], ValueError)

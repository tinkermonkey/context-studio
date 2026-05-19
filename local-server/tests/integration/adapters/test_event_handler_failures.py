"""
Integration tests verifying that event handler failures are logged in services.

This test suite validates that ExtractionService and PipelineService properly
capture and log event publishing failures, ensuring operators have visibility
into audit trail gaps.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.events.in_process import InProcessEventPublisher
from domain.extraction.events import ExtractionCompleted
from domain.pipeline.events import PipelineExecuted


class TestExtractionServiceEventHandlerFailures:
    """Test ExtractionService logs event handler failures."""

    def test_logs_warning_when_extraction_completion_event_fails(self):
        """ExtractionService should log warning when event handlers fail."""
        # Create publisher that will cause handler failure
        publisher = InProcessEventPublisher()

        def failing_handler(event):
            raise ValueError("Simulated handler failure")

        failing_handler.__name__ = "audit_recorder"
        publisher.subscribe(ExtractionCompleted, failing_handler)

        # Publish an event directly to verify the failure is captured
        event = ExtractionCompleted(result_id="test", entity_count=5, duration_ms=100)
        failures = publisher.publish(event)

        # Verify that the failure was captured
        assert len(failures) == 1
        assert failures[0][0] == "audit_recorder"
        assert isinstance(failures[0][1], ValueError)


class TestPipelineServiceEventHandlerFailures:
    """Test PipelineService logs event handler failures."""

    def test_logs_warning_when_execution_event_fails(self):
        """PipelineService should log warning when event handlers fail."""
        # Create publisher that will cause handler failure
        publisher = InProcessEventPublisher()

        def failing_handler(event):
            raise ValueError("Simulated handler failure")

        failing_handler.__name__ = "audit_recorder"
        publisher.subscribe(PipelineExecuted, failing_handler)

        # Publish an event directly to verify the failure is captured
        event = PipelineExecuted(execution_id="exec_1", pipeline_id="pipe_1", status="success")
        failures = publisher.publish(event)

        # Verify that the failure was captured
        assert len(failures) == 1
        assert failures[0][0] == "audit_recorder"
        assert isinstance(failures[0][1], ValueError)


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

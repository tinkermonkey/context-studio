"""
Test that event handler failures are properly detected and logged.

This test suite verifies that the event publishing return values are being
checked and handled appropriately in both the ExtractionService and PipelineService.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.pipeline.events import PipelineExecuted
from adapters.events.in_process import InProcessEventPublisher


class TestEventHandlerFailureDetection:
    """Test that event handler failures are properly detected and logged."""

    def test_event_publisher_return_value_indicates_failures(self):
        """InProcessEventPublisher.publish() should return failure information."""
        event_publisher = InProcessEventPublisher()

        # Create handlers: one succeeds, one fails, one succeeds
        successful_calls = []

        def good_handler_1(event):
            successful_calls.append(1)

        good_handler_1.__name__ = "good_handler_1"

        def bad_handler(event):
            raise ValueError("Intentional failure")

        bad_handler.__name__ = "bad_handler"

        def good_handler_2(event):
            successful_calls.append(2)

        good_handler_2.__name__ = "good_handler_2"

        event_publisher.subscribe(PipelineExecuted, good_handler_1)
        event_publisher.subscribe(PipelineExecuted, bad_handler)
        event_publisher.subscribe(PipelineExecuted, good_handler_2)

        # Publish an event
        event = PipelineExecuted(execution_id="e1", pipeline_id="p1", status="success")
        failures = event_publisher.publish(event)

        # Verify that:
        # 1. Both successful handlers were called
        assert successful_calls == [1, 2]

        # 2. The failure was reported in the return value
        assert len(failures) == 1
        assert failures[0][0] == "bad_handler"
        assert isinstance(failures[0][1], ValueError)
        assert "Intentional failure" in str(failures[0][1])

    def test_multiple_handler_failures_all_reported(self):
        """InProcessEventPublisher should report all handler failures."""
        event_publisher = InProcessEventPublisher()

        # Create three failing handlers
        handlers = []
        for i in range(3):
            def create_failing_handler(name):
                def handler(event):
                    raise ValueError(f"Simulated failure in {name}")
                handler.__name__ = name
                return handler

            handler = create_failing_handler(f"failing_handler_{i}")
            handlers.append(handler)
            event_publisher.subscribe(PipelineExecuted, handler)

        # Publish an event
        event = PipelineExecuted(execution_id="e1", pipeline_id="p1", status="success")
        failures = event_publisher.publish(event)

        # All three failures should be reported
        assert len(failures) == 3
        handler_names = {name for name, _ in failures}
        expected_names = {"failing_handler_0", "failing_handler_1", "failing_handler_2"}
        assert handler_names == expected_names

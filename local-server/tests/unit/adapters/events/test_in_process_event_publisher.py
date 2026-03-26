"""
Unit tests for InProcessEventPublisher adapter.

Tests verify:
- Event publishing and dispatch to registered handlers
- Multiple handlers for the same event type
- Handlers execute in registration order
- No handlers scenario (event published but no handlers registered)
"""

import sys
import os
from datetime import datetime
from uuid import uuid4


sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from adapters.events.in_process import InProcessEventPublisher
from domain.ontology.events import ClassCreated, ClassUpdated, DomainEvent


class TestInProcessEventPublisher:
    """Tests for InProcessEventPublisher adapter."""

    def test_publish_without_handlers(self):
        """Publishing an event with no registered handlers does not raise an error."""
        publisher = InProcessEventPublisher()
        event = ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-123",
            class_id="class-123",
            title="TestClass",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )

        # Should not raise an error even with no handlers
        publisher.publish(event)

    def test_single_handler_receives_event(self):
        """A registered handler receives the published event."""
        publisher = InProcessEventPublisher()
        received_events = []

        def handler(event: DomainEvent) -> None:
            received_events.append(event)

        event = ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-123",
            class_id="class-123",
            title="TestClass",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )

        publisher.subscribe(ClassCreated, handler)
        publisher.publish(event)

        assert len(received_events) == 1
        assert received_events[0] is event

    def test_multiple_handlers_for_same_event_type(self):
        """Multiple handlers for the same event type all receive the event."""
        publisher = InProcessEventPublisher()
        received_by_handler1 = []
        received_by_handler2 = []

        def handler1(event: DomainEvent) -> None:
            received_by_handler1.append(event)

        def handler2(event: DomainEvent) -> None:
            received_by_handler2.append(event)

        event = ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-123",
            class_id="class-123",
            title="TestClass",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )

        publisher.subscribe(ClassCreated, handler1)
        publisher.subscribe(ClassCreated, handler2)
        publisher.publish(event)

        assert len(received_by_handler1) == 1
        assert len(received_by_handler2) == 1
        assert received_by_handler1[0] is event
        assert received_by_handler2[0] is event

    def test_handlers_execute_in_registration_order(self):
        """Handlers are called in the order they were registered."""
        publisher = InProcessEventPublisher()
        execution_order = []

        def handler1(event: DomainEvent) -> None:
            execution_order.append(1)

        def handler2(event: DomainEvent) -> None:
            execution_order.append(2)

        def handler3(event: DomainEvent) -> None:
            execution_order.append(3)

        event = ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-123",
            class_id="class-123",
            title="TestClass",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )

        publisher.subscribe(ClassCreated, handler1)
        publisher.subscribe(ClassCreated, handler2)
        publisher.subscribe(ClassCreated, handler3)
        publisher.publish(event)

        assert execution_order == [1, 2, 3]

    def test_handlers_only_receive_subscribed_event_types(self):
        """A handler only receives events of the type it subscribed to."""
        publisher = InProcessEventPublisher()
        class_created_events = []
        class_updated_events = []

        def class_created_handler(event: DomainEvent) -> None:
            class_created_events.append(event)

        def class_updated_handler(event: DomainEvent) -> None:
            class_updated_events.append(event)

        created_event = ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-123",
            class_id="class-123",
            title="TestClass",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )

        updated_event = ClassUpdated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-123",
            class_id="class-123",
            changed_fields=("title",),
            old_values={"title": "OldTitle"},
            new_values={"title": "NewTitle"},
        )

        publisher.subscribe(ClassCreated, class_created_handler)
        publisher.subscribe(ClassUpdated, class_updated_handler)

        publisher.publish(created_event)
        publisher.publish(updated_event)

        assert len(class_created_events) == 1
        assert class_created_events[0] is created_event
        assert len(class_updated_events) == 1
        assert class_updated_events[0] is updated_event

    def test_multiple_events_dispatched_correctly(self):
        """Multiple published events are all dispatched to their respective handlers."""
        publisher = InProcessEventPublisher()
        received_events = []

        def handler(event: DomainEvent) -> None:
            received_events.append(event)

        publisher.subscribe(ClassCreated, handler)

        event1 = ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-1",
            class_id="class-1",
            title="Class1",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )

        event2 = ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-2",
            class_id="class-2",
            title="Class2",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )

        publisher.publish(event1)
        publisher.publish(event2)

        assert len(received_events) == 2
        assert received_events[0] is event1
        assert received_events[1] is event2

    def test_handler_exception_isolation(self):
        """If one handler raises an exception, other handlers still execute."""
        publisher = InProcessEventPublisher()
        successful_handlers = []

        def failing_handler(event: DomainEvent) -> None:
            raise ValueError("Handler failed")

        def successful_handler_1(event: DomainEvent) -> None:
            successful_handlers.append(1)

        def successful_handler_2(event: DomainEvent) -> None:
            successful_handlers.append(2)

        event = ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-123",
            class_id="class-123",
            title="TestClass",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )

        publisher.subscribe(ClassCreated, successful_handler_1)
        publisher.subscribe(ClassCreated, failing_handler)
        publisher.subscribe(ClassCreated, successful_handler_2)

        # Publishing should not raise, even though one handler fails
        publisher.publish(event)

        # Both successful handlers should have executed despite the failing handler
        assert len(successful_handlers) == 2
        assert successful_handlers == [1, 2]

    def test_multiple_handler_exceptions_isolated(self):
        """Multiple failing handlers do not prevent other handlers from executing."""
        publisher = InProcessEventPublisher()
        successful_handlers = []

        def failing_handler_1(event: DomainEvent) -> None:
            raise RuntimeError("Handler 1 failed")

        def successful_handler(event: DomainEvent) -> None:
            successful_handlers.append("success")

        def failing_handler_2(event: DomainEvent) -> None:
            raise ValueError("Handler 2 failed")

        event = ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-123",
            class_id="class-123",
            title="TestClass",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )

        publisher.subscribe(ClassCreated, failing_handler_1)
        publisher.subscribe(ClassCreated, successful_handler)
        publisher.subscribe(ClassCreated, failing_handler_2)

        # Publishing should not raise despite multiple failing handlers
        publisher.publish(event)

        # Successful handler should have executed
        assert len(successful_handlers) == 1
        assert successful_handlers[0] == "success"

    def test_exception_does_not_propagate_to_caller(self):
        """Exceptions in handlers do not propagate to the publish() caller."""
        publisher = InProcessEventPublisher()

        def failing_handler(event: DomainEvent) -> None:
            raise Exception("Handler error")

        event = ClassCreated(
            event_id=str(uuid4()),
            occurred_at=datetime.utcnow(),
            aggregate_id="class-123",
            class_id="class-123",
            title="TestClass",
            concept_scheme_id="scheme-456",
            taxonomy_id="tax-789",
        )

        publisher.subscribe(ClassCreated, failing_handler)

        # publish() should not raise even when handler fails
        publisher.publish(event)

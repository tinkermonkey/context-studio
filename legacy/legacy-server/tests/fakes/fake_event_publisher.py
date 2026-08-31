"""
Fake implementation of EventPublisher for testing.

Provides an in-memory event publisher that collects published events and
manages subscriptions for testing event-driven behavior.
"""

from collections.abc import Callable

from domain.ontology.events import DomainEvent


class FakeEventPublisher:
    """In-memory event publisher for testing.

    Collects all published events and supports subscription-based event
    delivery to registered handlers.
    """

    def __init__(self):
        self._events: list[DomainEvent] = []
        self._handlers: dict[type, list[Callable]] = {}

    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event.

        Adds the event to the internal event log and invokes all registered
        handlers for that event type.

        Args:
            event: The domain event to publish.
        """
        self._events.append(event)
        for handler in self._handlers.get(type(event), []):
            handler(event)

    def subscribe(self, event_type: type, handler: Callable) -> None:
        """Subscribe a handler to a specific event type.

        Args:
            event_type: The event class to subscribe to.
            handler: A callable that accepts the event as its only argument.
        """
        self._handlers.setdefault(event_type, []).append(handler)

    def get_events(self) -> list[DomainEvent]:
        """Retrieve all published events.

        Returns:
            A list copy of all events that have been published.
        """
        return list(self._events)

    def get_events_of_type(self, event_type: type) -> list[DomainEvent]:
        """Retrieve all published events of a specific type.

        Args:
            event_type: The event class to filter by.

        Returns:
            A list of events matching the specified type.
        """
        return [e for e in self._events if isinstance(e, event_type)]

    def clear(self) -> None:
        """Clear all published events.

        Useful for resetting state between test scenarios. Does not clear
        registered handlers.
        """
        self._events.clear()

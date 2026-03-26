"""
Fake in-memory implementation of EventPublisher for testing.

This implementation stores published events in memory and supports
event handler subscription and dispatch for testing event-driven workflows.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Callable

from domain.ontology.events import DomainEvent


class FakeEventPublisher:
    """
    In-memory event publisher for testing.

    Stores events in a list and dispatches them to registered handlers.
    Provides methods for test assertions: get_events(), get_events_of_type(),
    and clear().
    """

    def __init__(self) -> None:
        """Initialize empty event list and handler registry."""
        self._events: list[DomainEvent] = []
        self._handlers: dict[type, list[Callable[[DomainEvent], None]]] = {}

    def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event.

        Adds the event to the internal list and dispatches it to all
        registered handlers for its type.

        Args:
            event: The DomainEvent to publish
        """
        self._events.append(event)
        for handler in self._handlers.get(type(event), []):
            handler(event)

    def subscribe(
        self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]
    ) -> None:
        """
        Subscribe a handler to events of a specific type.

        Args:
            event_type: The DomainEvent subclass to subscribe to
            handler: Callable that will handle the event
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def get_events(self) -> list[DomainEvent]:
        """
        Get all published events.

        Returns:
            List of all DomainEvent instances published
        """
        return list(self._events)

    def get_events_of_type(self, event_type: type) -> list[DomainEvent]:
        """
        Get published events of a specific type.

        Args:
            event_type: The DomainEvent subclass to filter by

        Returns:
            List of events matching the specified type
        """
        return [e for e in self._events if isinstance(e, event_type)]

    def clear(self) -> None:
        """
        Clear all published events and registered handlers.

        Useful for resetting the publisher between test cases.
        """
        self._events.clear()
        self._handlers.clear()

"""Fake in-memory implementation of EventPublisher for testing."""

import sys
import os
from typing import Callable

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.ontology.events import DomainEvent


class FakeEventPublisher:
    """In-memory event publisher for unit testing with event storage and handler dispatch."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []
        self._handlers: dict[type[DomainEvent], list[Callable[[DomainEvent], None]]] = {}

    def publish(self, event: DomainEvent) -> None:
        self._events.append(event)
        for handler in self._handlers.get(type(event), []):
            handler(event)

    def subscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def get_events(self) -> list[DomainEvent]:
        return list(self._events)

    def get_events_of_type(self, event_type: type) -> list[DomainEvent]:
        return [e for e in self._events if isinstance(e, event_type)]

    def clear(self) -> None:
        self._events.clear()
        self._handlers.clear()

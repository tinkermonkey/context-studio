"""Fake in-memory implementation of EventPublisher for testing."""

import sys
import os
from typing import Callable, TypeVar

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.events import DomainEvent
from utils.logger import get_logger


logger = get_logger(__name__)

# Contravariant TypeVar allows handlers typed for specific event subclasses
EventT_contra = TypeVar('EventT_contra', bound=DomainEvent, contravariant=True)


class FakeEventPublisher:
    """In-memory event publisher for unit testing with event storage and handler dispatch."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []
        self._handlers: dict[type[DomainEvent], list[Callable[[DomainEvent], None]]] = {}

    def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event to all registered handlers.

        Handler exceptions are isolated to prevent cascade failures. If a handler
        raises an exception, the exception is logged and other handlers continue
        to execute. This mirrors the behavior of InProcessEventPublisher.
        """
        self._events.append(event)
        event_type = type(event)
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                handler_name = getattr(handler, '__name__', repr(handler))
                logger.error(
                    f"Handler {handler_name} raised exception while processing "
                    f"event {event_type.__name__} (id: {event.event_id}): {type(e).__name__}: {str(e)}",
                    exc_info=True,
                )

    def subscribe(self, event_type: type[EventT_contra], handler: Callable[[EventT_contra], None]) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)  # type: ignore[arg-type]

    def get_events(self) -> list[DomainEvent]:
        return list(self._events)

    def get_events_of_type(self, event_type: type) -> list[DomainEvent]:
        return [e for e in self._events if isinstance(e, event_type)]

    def clear(self) -> None:
        self._events.clear()
        self._handlers.clear()

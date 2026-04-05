"""Fake in-memory implementation of EventPublisher for testing."""

import sys
import os
from typing import Callable, TypeVar, overload, cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.events import DomainEvent
from utils.logger import get_logger


logger = get_logger(__name__)

# Contravariant TypeVar allows handlers typed for specific event subclasses
EventT_contra = TypeVar('EventT_contra', bound=DomainEvent, contravariant=True)

# Covariant TypeVar for get_events_of_type to preserve specific event types
EventT = TypeVar('EventT', bound=DomainEvent)


class FakeEventPublisher:
    """In-memory event publisher for unit testing with event storage and handler dispatch."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []
        self._handlers: dict[type[DomainEvent], list[Callable[[DomainEvent], None]]] = {}

    def publish(self, event: DomainEvent) -> list[tuple[str, Exception]]:
        """
        Publish a domain event to all registered handlers.

        Handler exceptions are isolated to prevent cascade failures. If a handler
        raises an exception, the exception is logged and other handlers continue
        to execute. This mirrors the behavior of InProcessEventPublisher.

        Returns:
            List of tuples (handler_name, exception) for any handlers that failed.
            Empty list if all handlers succeeded.
        """
        self._events.append(event)
        event_type = type(event)
        failures: list[tuple[str, Exception]] = []

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
                failures.append((handler_name, e))

        return failures

    def subscribe(self, event_type: type[EventT_contra], handler: Callable[[EventT_contra], None]) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)  # type: ignore[arg-type]

    def get_events(self) -> list[DomainEvent]:
        return list(self._events)

    def get_events_of_type(self, event_type: type[EventT]) -> list[EventT]:
        """
        Get all events of a specific type.

        Args:
            event_type: The event type to filter by (e.g., ChangesetMerged)

        Returns:
            List of events of the specified type with proper type preservation.
        """
        return cast(list[EventT], [e for e in self._events if isinstance(e, event_type)])

    def clear(self) -> None:
        self._events.clear()
        self._handlers.clear()

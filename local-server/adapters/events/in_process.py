"""In-process event publisher implementation using observer pattern."""

from typing import Callable

from domain.ontology.events import DomainEvent


class InProcessEventPublisher:
    """
    In-process event publisher using the observer pattern.

    Handlers execute synchronously within the same transaction boundary.
    This adapter implements the EventPublisher port for local, single-process
    deployments where event handlers need immediate, synchronous execution.
    """

    def __init__(self) -> None:
        """Initialize the event publisher with empty handler registry."""
        self._handlers: dict[type[DomainEvent], list[Callable[[DomainEvent], None]]] = {}

    def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event to all registered handlers.

        Handlers are called synchronously in the order they were registered.

        Args:
            event: The DomainEvent to publish
        """
        event_type = type(event)
        for handler in self._handlers.get(event_type, []):
            handler(event)

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], None],
    ) -> None:
        """
        Subscribe a handler to events of a specific type.

        Multiple handlers can be registered for the same event type.
        Handlers are called in registration order.

        Args:
            event_type: The DomainEvent subclass to subscribe to
            handler: Callable that will handle the event
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

"""
Shared port interfaces for cross-context use.

These ports are shared across bounded contexts to enable decoupled event handling
and other cross-cutting concerns. Using typing.Protocol enables structural subtyping
— implementations need not explicitly inherit from these protocols.
"""

from __future__ import annotations

from typing import Callable, Protocol, TypeVar

from .events import DomainEvent

# Contravariant TypeVar for event handlers
EventT_contra = TypeVar('EventT_contra', bound=DomainEvent, contravariant=True)


class EventPublisher(Protocol):
    """
    Port for publishing and subscribing to domain events.

    Used to decouple event producers from event handlers, enabling event-driven
    workflows and external integrations. This port is shared across all bounded
    contexts that need to publish or subscribe to domain events.
    """

    def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event.

        Args:
            event: The DomainEvent to publish
        """
        ...

    def subscribe(self, event_type: type[EventT_contra], handler: Callable[[EventT_contra], None]) -> None:
        """
        Subscribe a handler to events of a specific type.

        Args:
            event_type: The DomainEvent subclass to subscribe to
            handler: Callable that will handle the event
        """
        ...

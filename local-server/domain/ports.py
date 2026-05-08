"""
Shared port interfaces for cross-context use.

These ports are shared across bounded contexts to enable decoupled event handling
and other cross-cutting concerns. Using typing.Protocol enables structural subtyping
— implementations need not explicitly inherit from these protocols.
"""

from __future__ import annotations

from typing import Callable, Protocol, TypeVar

from .events import DomainEvent
from .versioning.value_objects import ChangeOperation

# Contravariant TypeVar for event handlers
EventT_contra = TypeVar("EventT_contra", bound=DomainEvent, contravariant=True)


# ============================================================================
# Value types used in port contracts
# ============================================================================


class ChangeRecordPort(Protocol):
    """Port for recording change events to the audit trail."""

    def record_change(
        self,
        entity_id: str,
        entity_type: str,
        operation: ChangeOperation,
        new_state: dict,
        previous_state: dict | None = None,
        user_id: str | None = None,
        change_reason: str | None = None,
        changeset_id: str | None = None,
        batch_run_id: str | None = None,
    ) -> str:
        """
        Record a change event.

        Args:
            entity_id: ID of the entity that changed
            entity_type: Type of entity
            operation: Type of operation (ChangeOperation enum)
            new_state: JSON snapshot after change
            previous_state: JSON snapshot before change (optional)
            user_id: Optional user ID
            change_reason: Optional explanation
            changeset_id: Optional changeset reference
            batch_run_id: Optional ID of the batch run (import or extraction) that triggered this change

        Returns:
            The ID of the recorded change event
        """
        ...


class EventPublisher(Protocol):
    """
    Port for publishing and subscribing to domain events.

    Used to decouple event producers from event handlers, enabling event-driven
    workflows and external integrations. This port is shared across all bounded
    contexts that need to publish or subscribe to domain events.
    """

    def publish(self, event: DomainEvent) -> list[tuple[str, Exception]]:
        """
        Publish a domain event.

        Args:
            event: The DomainEvent to publish

        Returns:
            List of tuples (handler_name, exception) for any handlers that failed.
            Empty list if all handlers succeeded.
        """
        ...

    def subscribe(
        self, event_type: type[EventT_contra], handler: Callable[[EventT_contra], None]
    ) -> None:
        """
        Subscribe a handler to events of a specific type.

        Args:
            event_type: The DomainEvent subclass to subscribe to
            handler: Callable that will handle the event
        """
        ...

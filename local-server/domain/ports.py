"""
Shared port interfaces for cross-context use.

These ports are shared across bounded contexts to enable decoupled event handling
and other cross-cutting concerns. Using typing.Protocol enables structural subtyping
— implementations need not explicitly inherit from these protocols.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypeVar

from .events import DomainEvent

# Contravariant TypeVar for event handlers
EventT_contra = TypeVar('EventT_contra', bound=DomainEvent, contravariant=True)


# ============================================================================
# Value types used in port contracts
# ============================================================================

class ChangeRecordPort(Protocol):
    """Port for recording change events to the audit trail."""

    def record_change(
        self,
        entity_id: str,
        entity_type: str,
        operation: str,
        new_state: dict,
        previous_state: dict | None = None,
        user_id: str | None = None,
        change_reason: str | None = None,
        changeset_id: str | None = None,
    ) -> str:
        """
        Record a change event.

        Args:
            entity_id: ID of the entity that changed
            entity_type: Type of entity
            operation: Type of operation ('create', 'update', 'delete')
            new_state: JSON snapshot after change
            previous_state: JSON snapshot before change (optional)
            user_id: Optional user ID
            change_reason: Optional explanation
            changeset_id: Optional changeset reference

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

    def subscribe(self, event_type: type[EventT_contra], handler: Callable[[EventT_contra], None]) -> None:
        """
        Subscribe a handler to events of a specific type.

        Args:
            event_type: The DomainEvent subclass to subscribe to
            handler: Callable that will handle the event
        """
        ...


class LLMProvider(Protocol):
    """
    Port for LLM completion and model introspection.

    Implementations provide access to language models for text generation
    and information about available models. This port is shared across both
    the extraction and pipeline bounded contexts.
    """

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """
        Request a completion from an LLM.

        Args:
            system_prompt: System context for the model
            user_prompt: User message to respond to
            model: Model identifier
            temperature: Sampling temperature (0.0–1.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional JSON schema for structured output
            timeout: Request timeout in seconds (provider-specific behavior)

        Returns:
            LLMResponse with generated content and metadata
        """
        ...

    def is_model_available(self, model: str) -> bool:
        """
        Check if a specific model is available.

        Args:
            model: Model identifier

        Returns:
            True if the model can be used, False otherwise
        """
        ...

    def list_available_models(self) -> list[str]:
        """
        Get list of available model identifiers.

        Returns:
            List of model names that can be used with complete()
        """
        ...

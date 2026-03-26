"""Event adapters for domain event publishing and subscription."""

from adapters.events.in_process import InProcessEventPublisher

__all__ = ["InProcessEventPublisher"]

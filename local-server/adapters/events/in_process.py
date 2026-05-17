"""In-process event publisher implementation using observer pattern."""

from typing import Callable, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from domain.events import DomainEvent
from utils.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Contravariant TypeVar allows handlers typed for specific event subclasses
# E.g., a handler expecting GraphInvalidated can be assigned to Callable[[DomainEvent], None]
EventT_contra = TypeVar("EventT_contra", bound=DomainEvent, contravariant=True)


class InProcessEventPublisher:
    """
    In-process event publisher using the observer pattern.

    Handlers execute synchronously within the same transaction boundary.
    This adapter implements the EventPublisher port for local, single-process
    deployments where event handlers need immediate, synchronous execution.

    Handler exceptions are isolated to prevent cascade failures. If a handler
    raises an exception, the exception is logged and other handlers continue
    to execute. This ensures the system remains consistent even if an event
    handler fails.
    """

    def __init__(self) -> None:
        """Initialize the event publisher with empty handler registry."""
        self._handlers: dict[type[DomainEvent], list[Callable[[DomainEvent], None]]] = (
            {}
        )

    def publish(self, event: DomainEvent) -> list[tuple[str, Exception]]:
        """
        Publish a domain event to all registered handlers.

        Handlers are called synchronously in the order they were registered.
        Each handler's exceptions are isolated to prevent cascade failures.
        If a handler raises an exception, it is logged and other handlers
        continue to execute.

        Args:
            event: The DomainEvent to publish

        Returns:
            List of tuples (handler_name, exception) for any handlers that failed.
            Empty list if all handlers succeeded.
        """
        event_type = type(event)
        event_type_name = event_type.__name__
        handler_count = len(self._handlers.get(event_type, []))

        with tracer.start_as_current_span(f"event.publish.{event_type_name}") as span:
            span.set_attribute("event.id", str(event.event_id))
            span.set_attribute("event.type", event_type_name)
            span.set_attribute("event.handler_count", handler_count)

            try:
                failures: list[tuple[str, Exception]] = []

                for handler in self._handlers.get(event_type, []):
                    try:
                        handler(event)
                    except Exception as e:
                        handler_name = getattr(handler, "__name__", repr(handler))
                        logger.error(
                            f"Handler {handler_name} raised exception while processing "
                            f"event {event_type.__name__} (id: {event.event_id}): {type(e).__name__}: {str(e)}",
                            exc_info=True,
                        )
                        failures.append((handler_name, e))

                if failures:
                    span.set_status(Status(StatusCode.ERROR))
                    for handler_name, exception in failures:
                        span.record_exception(exception)

                return failures
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise

    def subscribe(
        self,
        event_type: type[EventT_contra],
        handler: Callable[[EventT_contra], None],
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
        self._handlers[event_type].append(handler)  # type: ignore[arg-type]

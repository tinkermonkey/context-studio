"""
Event publishing adapters for Context Studio.

This package contains adapters that implement the EventPublisher port
defined in domain/ontology/ports.py.

The EventPublisher port defines:
- subscribe(event_type: type, handler: Callable) -> None: Register handler for event type
- publish(event: DomainEvent) -> None: Publish event to all subscribed handlers
- unsubscribe(event_type: type, handler: Callable) -> None: Unregister handler

Adapter implementations support:
- In-memory publish-subscribe (simplest, used for Phase 0)
- Message queues (RabbitMQ, Kafka for distributed systems)
- Database-backed event store (for event sourcing)
- Webhooks (push events to external systems)

Per rearchitecture/architecture_design.md §5.8, the in-memory event publisher
is sufficient for the initial phases. As the system grows, additional adapters
can be added to integrate with message brokers or event stores without
changing the domain code.

Handlers receive DomainEvent instances (from domain/ontology/events.py and
other bounded contexts' events.py files). Handlers run synchronously in the
current phase but may be made asynchronous in later phases.
"""

"""Event adapters for domain event publishing and subscription."""


def __getattr__(name: str):
    """Lazy import of event adapters to avoid side effects at module load time."""
    if name == "InProcessEventPublisher":
        from adapters.events.in_process import InProcessEventPublisher

        return InProcessEventPublisher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["InProcessEventPublisher"]

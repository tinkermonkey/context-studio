"""
Domain events for the ontology bounded context.

Events are immutable signals emitted when domain operations complete.
All events inherit from DomainEvent and use frozen dataclasses for immutability.
No framework or external dependencies - pure Python only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    """
    Base class for all domain events.

    Provides a unique event_id and timestamp for all domain events.
    Frozen to ensure immutability.
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate that event fields are not empty."""
        for field_name, field_value in self.__dataclass_fields__.items():
            if field_name in ("event_id", "occurred_at"):
                continue
            actual_value = getattr(self, field_name)
            if isinstance(actual_value, str) and actual_value == "":
                raise ValueError(
                    f"Event field {field_name!r} cannot be empty. "
                    f"All required fields must have meaningful values."
                )
            if isinstance(actual_value, (tuple, list)) and len(actual_value) == 0:
                # Allow empty collections for optional fields (e.g., changed_fields)
                pass


@dataclass(frozen=True)
class ClassCreated(DomainEvent):
    """Emitted when a new class (concept) is created."""

    class_id: str = field(default="")
    title: str = field(default="")
    scheme_id: str = field(default="")
    taxonomy_id: str = field(default="")


@dataclass(frozen=True)
class ClassUpdated(DomainEvent):
    """Emitted when a class is modified."""

    class_id: str = field(default="")
    changed_fields: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class ClassDeleted(DomainEvent):
    """Emitted when a class is deleted."""

    class_id: str = field(default="")
    title: str = field(default="")


@dataclass(frozen=True)
class ClassMoved(DomainEvent):
    """Emitted when a class is moved to a different parent."""

    class_id: str = field(default="")
    old_parent_id: str = field(default="")
    new_parent_id: str = field(default="")


@dataclass(frozen=True)
class RelationshipCreated(DomainEvent):
    """Emitted when a relationship between entities is created."""

    relationship_id: str = field(default="")
    source_id: str = field(default="")
    target_id: str = field(default="")
    predicate_id: str = field(default="")


@dataclass(frozen=True)
class RelationshipDeleted(DomainEvent):
    """Emitted when a relationship is deleted."""

    relationship_id: str = field(default="")


@dataclass(frozen=True)
class PropertyDefinitionCreated(DomainEvent):
    """Emitted when a property definition is created."""

    property_id: str = field(default="")
    label: str = field(default="")


@dataclass(frozen=True)
class SchemeCreated(DomainEvent):
    """Emitted when a concept scheme is created."""

    scheme_id: str = field(default="")
    title: str = field(default="")
    taxonomy_id: str = field(default="")


@dataclass(frozen=True)
class TaxonomyCreated(DomainEvent):
    """Emitted when a taxonomy is created."""

    taxonomy_id: str = field(default="")
    title: str = field(default="")


@dataclass(frozen=True)
class GraphInvalidated(DomainEvent):
    """Emitted when the graph state becomes invalid and requires recalculation."""

    taxonomy_id: str = field(default="")
    reason: str = field(default="")

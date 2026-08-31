"""
API Models for Change Events

This module contains the Pydantic models for the change_events API.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventTypeEnum(str, Enum):
    """Event types for change events."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class RecordTypeEnum(str, Enum):
    """Record types for change events."""

    STRUCTURE_NODE = "structure_node"
    STRUCTURE_NODE_LINK = "structure_node_link"
    PREDICATE = "predicate"


class ChangeEventOut(BaseModel):
    """Model for change event output/response."""

    id: int
    event_type: str
    record_type: str
    record_id: str | None = None
    old_data: dict[str, Any] | None = None
    new_data: dict[str, Any] | None = None
    event_timestamp: str  # ISO8601 string
    processed: bool

    model_config = ConfigDict(from_attributes=True)


class ChangeEventUpdate(BaseModel):
    """Model for updating a change event."""

    processed: bool = Field(..., description="Mark event as processed")

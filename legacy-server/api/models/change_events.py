"""
API Models for Change Events

This module contains the Pydantic models for the change_events API.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from enum import Enum


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
    record_id: Optional[str] = None
    old_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None
    event_timestamp: str  # ISO8601 string
    processed: bool

    model_config = ConfigDict(from_attributes=True)


class ChangeEventUpdate(BaseModel):
    """Model for updating a change event."""

    processed: bool = Field(..., description="Mark event as processed")

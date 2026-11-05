"""Domain entities for versioning context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from domain.versioning.value_objects import ChangeOperation


@dataclass
class ChangeEvent:
    """Record of a single change to an entity."""

    id: str
    entity_id: str
    entity_type: str
    operation: ChangeOperation
    new_state: dict
    timestamp: datetime
    previous_state: Optional[dict] = None
    user_id: Optional[str] = None
    change_reason: Optional[str] = None
    batch_run_id: Optional[str] = None
    processed: bool = False

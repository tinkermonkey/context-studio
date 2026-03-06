"""
Domain value enums for the versioning bounded context.

Enums represent domain concepts in the versioning bounded context.
They are immutable and framework-free, depending only on Python stdlib.
"""

from enum import Enum


class ChangeType(str, Enum):
    """
    Enumeration of change types.

    Attributes:
        CREATED: Entity was newly created
        UPDATED: Entity was modified
        DELETED: Entity was deleted
    """

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"

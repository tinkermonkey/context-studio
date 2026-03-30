"""
Exception classes for the Version Control & Collaboration domain.

These exceptions represent domain-specific errors that may occur
during versioning operations.
"""


class VersioningError(Exception):
    """Base exception for all versioning domain errors."""

    pass


class VersionNotFoundError(VersioningError):
    """Raised when a requested version does not exist."""

    pass


class ChangesetStateError(VersioningError):
    """Raised when an invalid changeset state transition is attempted."""

    pass


class ConflictResolutionError(VersioningError):
    """Raised when conflict resolution fails."""

    pass


class SyncError(VersioningError):
    """Raised when a synchronization operation fails."""

    pass

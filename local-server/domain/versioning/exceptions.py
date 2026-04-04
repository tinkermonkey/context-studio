"""Exceptions for versioning domain."""


class VersioningError(Exception):
    """Base exception for versioning domain errors."""

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
    """Raised when synchronization fails."""

    pass

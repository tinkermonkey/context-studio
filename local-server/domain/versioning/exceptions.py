"""Exceptions for versioning domain."""


class VersionNotFoundError(Exception):
    """Raised when a requested version does not exist."""

    pass


class ChangesetStateError(Exception):
    """Raised when an invalid changeset state transition is attempted."""

    pass


class ConflictResolutionError(Exception):
    """Raised when conflict resolution fails."""

    pass


class SyncError(Exception):
    """Raised when synchronization fails."""

    pass

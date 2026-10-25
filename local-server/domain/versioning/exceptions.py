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


class ProposalStateError(VersioningError):
    """Raised when an invalid proposal state transition is attempted."""

    pass


class ConflictResolutionError(VersioningError):
    """Raised when conflict resolution fails."""

    pass


class SyncError(VersioningError):
    """Raised when synchronization fails."""

    pass


class UnknownChangeEventError(VersioningError):
    """Raised when a request names change event ids that do not exist."""

    def __init__(self, missing_ids: list[str]):
        self.missing_ids = missing_ids
        super().__init__(f"Unknown change event ids: {', '.join(missing_ids)}")


class RevertConflictError(VersioningError):
    """Raised when a revert would delete entities that others still depend on.

    Attributes:
        blocking: (dependent_kind, dependent_id, referenced_id) for each dependent
            that was not created by the run being reverted
    """

    def __init__(self, run_id: str, blocking: list[tuple[str, str, str]]):
        self.run_id = run_id
        self.blocking = blocking
        counts: dict[str, int] = {}
        for kind, _, _ in blocking:
            counts[kind] = counts.get(kind, 0) + 1
        summary = ", ".join(f"{kind}: {count}" for kind, count in sorted(counts.items()))
        examples = ", ".join(
            f"{kind} {dependent_id} -> {referenced_id}"
            for kind, dependent_id, referenced_id in blocking[:5]
        )
        more = f" and {len(blocking) - 5} more" if len(blocking) > 5 else ""
        super().__init__(
            f"Cannot revert run {run_id}: entities outside this run depend on entities it "
            f"created ({summary}). Nothing was changed. Examples: {examples}{more}"
        )

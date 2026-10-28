"""Exceptions for versioning domain."""

from dataclasses import dataclass
from typing import Optional


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


class ChangeProposalNotFoundError(VersioningError):
    """Raised when a change proposal does not exist."""

    def __init__(self, proposal_id: str):
        self.proposal_id = proposal_id
        super().__init__(f"Change proposal {proposal_id} not found")


class ChangeProposalStateError(VersioningError):
    """Raised when a change proposal or its operations can't take the requested decision."""

    pass


@dataclass(frozen=True)
class OperationError:
    """
    Why one proposed operation is invalid.

    Attributes:
        seq: The operation's seq, or None for a problem with the proposal as a whole
        code: A stable machine-readable code (e.g. target_not_found, unknown_ref)
        message: What is wrong, for a person or an agent to fix
    """

    seq: Optional[int]
    code: str
    message: str


class ProposalValidationError(VersioningError):
    """Raised when a change proposal is invalid; nothing is stored.

    Attributes:
        errors: Every problem found, per operation
    """

    def __init__(self, errors: list[OperationError]):
        self.errors = errors
        detail = "; ".join(
            f"{'seq ' + str(e.seq) if e.seq is not None else 'proposal'}: {e.code}: {e.message}"
            for e in errors
        )
        super().__init__(f"Invalid change proposal ({len(errors)} errors): {detail}")

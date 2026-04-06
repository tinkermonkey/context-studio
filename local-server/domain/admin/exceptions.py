"""
Exception classes for the System Administration domain.

These exceptions represent domain-specific errors that may occur
during system administration operations.
"""


class AdminError(Exception):
    """Base exception for all admin domain errors."""

    pass


class ConfigurationError(AdminError):
    """Raised when a configuration operation fails."""

    pass


class TaskNotFoundError(AdminError):
    """Raised when a background task is not found."""

    pass


class InvalidStateTransitionError(AdminError):
    """Raised when an invalid state transition is attempted."""

    pass

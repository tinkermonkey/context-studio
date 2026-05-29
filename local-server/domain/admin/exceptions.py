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


class DatasetNotFoundError(AdminError):
    """Raised when a dataset is not found."""

    pass


class ActiveDatasetError(AdminError):
    """Raised when attempting to delete or modify the active dataset."""

    pass


class DemoDatasetNotFoundError(AdminError):
    """Raised when a requested demo dataset name is not registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Demo dataset '{name}' is not available")


class DemoDatasetAlreadyLoadedError(AdminError):
    """Raised when attempting to load a demo dataset whose root taxonomy already exists."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Demo dataset '{name}' is already loaded. "
            "Delete the existing taxonomy or load into a fresh database."
        )


class DemoDatasetMalformedError(AdminError):
    """Raised when a demo dataset's canon JSON has structural defects.

    Examples: dangling parent_class_identifier, cyclic class hierarchy,
    concept_scheme referencing an unknown taxonomy, malformed paper fixtures.
    Surfaces as HTTP 422 so the caller knows the input is the problem, not
    the server.
    """

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        super().__init__(f"Demo dataset '{name}' is malformed: {reason}")

"""Exceptions for reference source adapters."""


class ReferenceSourceError(Exception):
    """Base exception for reference source operations."""

    pass


class ReferenceSourceNetworkError(ReferenceSourceError):
    """Network connectivity issue accessing a reference source."""

    pass


class ReferenceSourceTimeoutError(ReferenceSourceError):
    """Request to a reference source timed out."""

    pass


class ReferenceSourceHTTPError(ReferenceSourceError):
    """HTTP error response from a reference source."""

    pass


class ReferenceSourceParseError(ReferenceSourceError):
    """Failed to parse response from a reference source."""

    pass

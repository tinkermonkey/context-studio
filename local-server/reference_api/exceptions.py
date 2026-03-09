class ReferenceError(Exception):
    """Base exception for reference service errors"""

    pass


class SourceError(ReferenceError):
    """General error from a reference API source"""

    pass


class SourceTimeoutError(SourceError):
    """Timeout error from a reference API source"""

    pass


class SourceUnavailableError(SourceError):
    """Source is unavailable or unreachable"""

    pass


class ConfigurationError(ReferenceError):
    """Configuration error"""

    pass


class ValidationError(ReferenceError):
    """Request validation error"""

    pass

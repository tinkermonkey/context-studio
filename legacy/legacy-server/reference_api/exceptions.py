class ReferenceError(Exception):
    """Base exception for reference service errors"""



class SourceError(ReferenceError):
    """General error from a reference API source"""



class SourceTimeoutError(SourceError):
    """Timeout error from a reference API source"""



class SourceUnavailableError(SourceError):
    """Source is unavailable or unreachable"""



class ConfigurationError(ReferenceError):
    """Configuration error"""



class ValidationError(ReferenceError):
    """Request validation error"""


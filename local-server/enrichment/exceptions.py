class EnrichmentError(Exception):
    """Base exception for enrichment service errors"""
    pass

class SourceError(EnrichmentError):
    """General error from a reference API source"""
    pass

class SourceTimeoutError(SourceError):
    """Timeout error from a reference API source"""
    pass

class SourceUnavailableError(SourceError):
    """Source is unavailable or unreachable"""
    pass

class ConfigurationError(EnrichmentError):
    """Configuration error"""
    pass

class ValidationError(EnrichmentError):
    """Request validation error"""
    pass

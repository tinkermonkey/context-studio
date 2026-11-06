"""
Exceptions raised by decision models.

Only DecisionModelNotConfiguredError and DecisionModelUnavailableError mean
"another instance might answer": a fallback is used for those. The others
(a request the service rejects, an unusable response) would fail the same way
again, or point at a problem a person should fix, so they are raised to the
caller instead of quietly paying for a fallback on every call.
"""


class DecisionModelError(Exception):
    """A decision model could not answer (request failed or the answer was unusable)."""


class DecisionModelNotConfiguredError(DecisionModelError):
    """The instance is missing what it needs to make a call (e.g. credentials)."""


class DecisionModelUnavailableError(DecisionModelError):
    """The service could not be reached or is overloaded (transport error, 429, 5xx)."""


class DecisionModelRequestError(DecisionModelError):
    """The service rejected the request (4xx other than 429, e.g. a revoked token)."""


class UnknownDecisionModelError(DecisionModelError):
    """No decision-model instance has the requested name."""

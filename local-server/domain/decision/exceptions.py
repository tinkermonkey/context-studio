"""
Exceptions raised by decision models.
"""


class DecisionModelError(Exception):
    """A decision model could not answer (request failed or the answer was unusable)."""


class DecisionModelNotConfiguredError(DecisionModelError):
    """The instance is missing what it needs to make a call (e.g. credentials)."""


class UnknownDecisionModelError(DecisionModelError):
    """No decision-model instance has the requested name."""

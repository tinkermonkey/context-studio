"""
Questions a decision model answers, and the answers it gives.

A decision model reads a piece of text (the state) and answers structured
questions about it with probabilities rather than free text. Three kinds of
question are supported:

- ChoiceQuestion: pick one option; the answer is a distribution over options.
- ScoreQuestion: place the state on an ordered scale of levels.
- YesNoQuestion: the probability that a statement about the state is true.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence, Union

NONE_OPTION = "none"
NONE_OPTION_DESCRIPTION = "None of the listed options apply"


@dataclass(frozen=True)
class ChoiceQuestion:
    """
    Pick one of several options.

    criteria maps each option to a description of when it applies. The 'none'
    option is offered as well unless offer_none is False or the criteria
    already include it.
    """

    instructions: str
    criteria: Mapping[str, str]
    offer_none: bool = True

    def __post_init__(self) -> None:
        if not self.options():
            raise ValueError("A choice question needs at least one option")

    def options(self) -> dict[str, str]:
        """The options to offer, including 'none' when it is offered."""
        options = dict(self.criteria)
        if self.offer_none and NONE_OPTION not in options:
            options[NONE_OPTION] = NONE_OPTION_DESCRIPTION
        return options


@dataclass(frozen=True)
class ScoreQuestion:
    """Place the state on an ordered scale. levels[0] is the lowest level."""

    instructions: str
    levels: Sequence[str]

    def __post_init__(self) -> None:
        if len(self.levels) < 2:
            raise ValueError("A score question needs at least two levels")


@dataclass(frozen=True)
class YesNoQuestion:
    """Whether a statement (the instructions) is true of the state."""

    instructions: str


Question = Union[ChoiceQuestion, ScoreQuestion, YesNoQuestion]


@dataclass(frozen=True, kw_only=True)
class AnswerMeta:
    """
    Fields every answer carries.

    model: the configured instance name that answered (not the vendor model id).
    latency_ms: the wall time of the request that produced the answer.
    cost_usd: this answer's share of the request's cost; None when the
        instance has no price configured.
    calibrated: False when the probabilities are an LLM's own estimate rather
        than a calibrated decision model's, so thresholds can treat them
        differently.
    """

    model: str
    latency_ms: float
    cost_usd: Optional[float] = None
    calibrated: bool = True


@dataclass(frozen=True, kw_only=True)
class ChoiceAnswer(AnswerMeta):
    """The chosen option, the distribution over options and the model's confidence."""

    choice: Optional[str]
    probabilities: Mapping[str, float] = field(default_factory=dict)
    confidence: Optional[float] = None


@dataclass(frozen=True, kw_only=True)
class ScoreAnswer(AnswerMeta):
    """
    The score on the 0..len(levels)-1 scale (possibly fractional: an expected
    level) and the probability of each level, in level order.
    """

    score: Optional[float]
    probabilities: Sequence[float] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class YesNoAnswer(AnswerMeta):
    """The probability that the statement is true."""

    p_yes: Optional[float]


Answer = Union[ChoiceAnswer, ScoreAnswer, YesNoAnswer]


@dataclass(frozen=True)
class DecisionModelInfo:
    """A configured decision-model instance as listed to callers (no credentials)."""

    name: str
    adapter: str
    model: str
    configured: bool
    is_default: bool = False
    fallback: Optional[str] = None

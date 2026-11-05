"""
Parsing for decision-model answers in the Workers AI state-plus-questions wire format.

Follows DR's classify-eval decision-model backend (choiceOf / scoreOf / noulOf): read the
documented field first, then the alternatives some deployments use, and derive
what is missing (the arg-max choice, the expected score) from the distribution.

One difference, found in recorded responses: score probabilities arrive as an
object keyed by level index ({"0": 0.12, "1": 0.46, ...}), not only as a list,
so both forms are read.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional


def _number(value: Any) -> Optional[float]:
    """A finite float, or None for anything else (bools, strings, NaN)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def choice_of(
    answer: Mapping[str, Any],
) -> tuple[Optional[str], dict[str, float], Optional[float]]:
    """(choice, probabilities by option, confidence) from a choice answer."""
    raw = answer.get("probabilities")
    probabilities: dict[str, float] = {}
    if isinstance(raw, Mapping):
        for option, p in raw.items():
            number = _number(p)
            if number is not None:
                probabilities[str(option)] = number

    choice: Optional[str] = None
    for key in ("choice", "answer", "value"):
        if isinstance(answer.get(key), str):
            choice = answer[key]
            break
    if choice is None and probabilities:
        choice = max(probabilities, key=lambda option: probabilities[option])
    return choice, probabilities, _number(answer.get("confidence"))


def _score_distribution(answer: Mapping[str, Any], levels: int) -> list[float]:
    """Level probabilities in level order, from a list or an index-keyed object."""
    for key in ("probabilities", "distribution"):
        raw = answer.get(key)
        if isinstance(raw, list):
            numbers = [_number(p) for p in raw]
            if numbers and all(n is not None for n in numbers):
                return [n for n in numbers if n is not None]
        elif isinstance(raw, Mapping) and raw:
            by_index: dict[int, float] = {}
            for index, p in raw.items():
                number = _number(p)
                try:
                    position = int(index)
                except (TypeError, ValueError):
                    continue
                if number is not None and 0 <= position < levels:
                    by_index[position] = number
            if by_index:
                return [by_index.get(i, 0.0) for i in range(levels)]
    return []


def score_of(answer: Mapping[str, Any], levels: int) -> tuple[Optional[float], list[float]]:
    """(score on the 0..levels-1 scale, probability of each level) from a score answer."""
    distribution = _score_distribution(answer, levels)
    score = _number(answer.get("score"))
    if score is None:
        score = _number(answer.get("value"))
    if score is None and distribution:
        score = sum(p * i for i, p in enumerate(distribution))
    # A score reported on a 1..N scale without a distribution: clamp to the top level
    if score is not None and not distribution and score >= levels:
        score = float(levels - 1)
    return score, distribution


def yes_no_of(answer: Mapping[str, Any]) -> Optional[float]:
    """The probability of 'yes' from a yes/no ('noul') answer."""
    for key in ("noul", "probability", "p_yes", "value", "score"):
        number = _number(answer.get(key))
        if number is not None:
            return number
    return None

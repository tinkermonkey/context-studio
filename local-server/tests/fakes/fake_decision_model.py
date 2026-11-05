"""
Fake DecisionModel for tests: answers from scripted probabilities, records calls.
"""

from typing import Mapping, Optional

from domain.decision.exceptions import (
    DecisionModelNotConfiguredError,
    DecisionModelUnavailableError,
)
from domain.decision.value_objects import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
    YesNoAnswer,
)


class FakeDecisionModel:
    """
    A DecisionModel that answers without I/O.

    choice questions: the scripted option (by question name) gets probability
    `p`, the rest share 1 - p; unscripted questions pick their first option.
    score questions: all mass on the scripted level (default 0).
    yes_no questions: the scripted p_yes (default 0.5).
    """

    def __init__(
        self,
        name: str = "fake",
        *,
        choices: Optional[Mapping[str, str]] = None,
        scores: Optional[Mapping[str, int]] = None,
        p_yes: Optional[Mapping[str, float]] = None,
        p: float = 0.9,
        configured: bool = True,
        fail: bool = False,
        error: Optional[Exception] = None,
        cost_usd: Optional[float] = 0.0,
    ) -> None:
        self._name = name
        self._choices = dict(choices or {})
        self._scores = dict(scores or {})
        self._p_yes = dict(p_yes or {})
        self._p = p
        self._configured = configured
        # fail=True raises DecisionModelUnavailableError; error= raises that error
        self._error = error or (DecisionModelUnavailableError(f"{name} failed") if fail else None)
        self._cost = cost_usd
        self.calls: list[tuple[str, dict[str, Question]]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_configured(self) -> bool:
        return self._configured

    def decide(self, state: str, questions: Mapping[str, Question]) -> dict[str, Answer]:
        if not self._configured:
            raise DecisionModelNotConfiguredError(f"{self._name} is not configured")
        self.calls.append((state, dict(questions)))
        if self._error is not None:
            raise self._error
        meta = {"model": self._name, "latency_ms": 0.0, "cost_usd": self._cost}
        answers: dict[str, Answer] = {}
        for name, question in questions.items():
            if isinstance(question, ChoiceQuestion):
                options = list(question.options())
                choice = self._choices.get(name, options[0])
                rest = (1 - self._p) / max(1, len(options) - 1)
                probabilities = {o: self._p if o == choice else rest for o in options}
                answers[name] = ChoiceAnswer(
                    choice=choice, probabilities=probabilities, confidence=self._p, **meta
                )
            elif isinstance(question, ScoreQuestion):
                level = self._scores.get(name, 0)
                distribution = [1.0 if i == level else 0.0 for i in range(len(question.levels))]
                answers[name] = ScoreAnswer(score=float(level), probabilities=distribution, **meta)
            else:
                answers[name] = YesNoAnswer(p_yes=self._p_yes.get(name, 0.5), **meta)
        return answers

    async def decide_async(
        self, state: str, questions: Mapping[str, Question]
    ) -> dict[str, Answer]:
        return self.decide(state, questions)

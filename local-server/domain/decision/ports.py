"""
Port interfaces for decision models.

A DecisionModel answers structured questions about a piece of text with
probabilities. Each configured instance (named in config.json) is one
DecisionModel; DecisionModels looks instances up by name.
"""

from __future__ import annotations

from typing import Mapping, Optional, Protocol

from domain.decision.value_objects import Answer, DecisionModelInfo, Question


class DecisionModel(Protocol):
    """Port for one configured decision-model instance."""

    @property
    def name(self) -> str:
        """The instance name from config (what answers report as their model)."""
        ...

    @property
    def is_configured(self) -> bool:
        """Whether the instance has what it needs to make a call."""
        ...

    def decide(self, state: str, questions: Mapping[str, Question]) -> dict[str, Answer]:
        """
        Answer every question about the state.

        Returns one answer per question name, of the kind matching the question
        (ChoiceAnswer for ChoiceQuestion, and so on).

        Raises:
            DecisionModelNotConfiguredError: if the instance is not configured
            DecisionModelError: if the call fails or an answer is missing
        """
        ...

    async def decide_async(
        self, state: str, questions: Mapping[str, Question]
    ) -> dict[str, Answer]:
        """Async variant of decide."""
        ...


class DecisionModels(Protocol):
    """Port for looking up configured decision-model instances."""

    def get(self, name: Optional[str] = None) -> DecisionModel:
        """
        The named instance, or the default when name is None.

        Raises:
            UnknownDecisionModelError: if no instance has that name, or no
                default is configured
        """
        ...

    def describe(self) -> list[DecisionModelInfo]:
        """Every configured instance, without credentials."""
        ...

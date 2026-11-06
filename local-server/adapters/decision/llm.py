"""
Decision model served by a chat LLM through the LLM provider router.

The model is asked for a probability distribution per question as JSON. LLM
probabilities are the model's own estimate, not calibrated, so every answer
is marked calibrated=False for thresholds to treat differently.

Provider errors raise DecisionModelUnavailableError (a fallback may answer);
a reply with no usable answer raises DecisionModelError. At most
`concurrency` calls are in flight at once per instance.
"""

from __future__ import annotations

import json
import time
from typing import Any, Mapping, Optional

from adapters.decision.common import ConcurrencyLimit, cost_share, finish_answers, request_cost
from domain.decision.exceptions import (
    DecisionModelError,
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
from domain.pipelines.ports import LLMProvider, LLMResponse
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a decision model. You read a piece of text (the state) and answer \
structured questions about it with probabilities.

Question kinds:
- choice: give a probability for every listed option (they sum to 1).
- score: give a probability for every level, in the listed order, lowest first (they sum to 1).
- yes_no: give the probability that the statement is true of the state.

Reply with only a JSON object, one key per question name:
- choice: {"probabilities": {"<option>": <p>, ...}}
- score: {"probabilities": [<p for level 0>, <p for level 1>, ...]}
- yes_no: {"p_yes": <p>}"""


def build_user_prompt(state: str, questions: Mapping[str, Question]) -> str:
    """The state and the questions, as JSON the model answers against."""
    described: dict[str, dict[str, Any]] = {}
    for name, question in questions.items():
        if isinstance(question, ChoiceQuestion):
            described[name] = {
                "kind": "choice",
                "instructions": question.instructions,
                "options": question.options(),
            }
        elif isinstance(question, ScoreQuestion):
            described[name] = {
                "kind": "score",
                "instructions": question.instructions,
                "levels": list(question.levels),
            }
        else:
            described[name] = {"kind": "yes_no", "instructions": question.instructions}
    return json.dumps({"state": state, "questions": described}, indent=2, ensure_ascii=False)


def first_json_object(content: str) -> Optional[dict[str, Any]]:
    """The first JSON object in the text, ignoring code fences or prose around it."""
    decoder = json.JSONDecoder()
    start = content.find("{")
    while start != -1:
        try:
            value, _end = decoder.raw_decode(content, start)
        except json.JSONDecodeError:
            start = content.find("{", start + 1)
            continue
        if isinstance(value, dict):
            return value
        start = content.find("{", start + 1)
    return None


def _probability(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return min(1.0, max(0.0, float(value)))


def _normalized(values: list[float]) -> list[float]:
    total = sum(values)
    return [v / total for v in values] if total > 0 else values


def _parse_one(question: Question, entry: Any, meta: Mapping[str, Any]) -> Optional[Answer]:
    """One typed answer, or None when the reply's entry is missing or unusable."""
    if isinstance(question, ChoiceQuestion):
        raw = entry.get("probabilities") if isinstance(entry, Mapping) else None
        raw = raw if isinstance(raw, Mapping) else {}
        options = list(question.options())
        weights = [_probability(raw.get(option)) or 0.0 for option in options]
        if not any(weights):
            return None
        probabilities = dict(zip(options, _normalized(weights)))
        choice = max(probabilities, key=lambda option: probabilities[option])
        return ChoiceAnswer(choice=choice, probabilities=probabilities, **meta)
    if isinstance(question, ScoreQuestion):
        levels = list(question.levels)
        raw = entry.get("probabilities") if isinstance(entry, Mapping) else None
        if isinstance(raw, Mapping):
            # Keyed by level name or by index
            raw = [raw.get(level, raw.get(str(i))) for i, level in enumerate(levels)]
        if not isinstance(raw, list) or len(raw) != len(levels):
            return None
        weights = [_probability(p) or 0.0 for p in raw]
        if not any(weights):
            return None
        distribution = _normalized(weights)
        score = sum(p * i for i, p in enumerate(distribution))
        return ScoreAnswer(score=score, probabilities=distribution, **meta)
    # yes_no: {"p_yes": p}, or a bare number
    p_yes = _probability(entry.get("p_yes") if isinstance(entry, Mapping) else entry)
    return None if p_yes is None else YesNoAnswer(p_yes=p_yes, **meta)


def parse_llm_answers(
    content: str,
    questions: Mapping[str, Question],
    *,
    model_name: str,
    latency_ms: float,
    cost_usd: Optional[float],
) -> dict[str, Answer]:
    """
    Turn the model's JSON reply into one answer per question. A question
    without a usable answer gets an empty answer (value None) and is logged.

    Raises:
        DecisionModelError: if the reply holds no JSON object or no usable answer
    """
    data = first_json_object(content)
    if data is None:
        raise DecisionModelError(f"{model_name}: reply holds no JSON object")
    meta: dict[str, Any] = {
        "model": model_name,
        "latency_ms": latency_ms,
        "cost_usd": cost_share(cost_usd, questions),
        "calibrated": False,
    }
    parsed = {name: _parse_one(q, data.get(name), meta) for name, q in questions.items()}
    return finish_answers(parsed, questions, meta)


class LLMDecisionModel:
    """DecisionModel adapter over an LLMProvider (the provider router), with JSON output."""

    def __init__(
        self,
        name: str,
        *,
        llm: Optional[LLMProvider],
        model: str,
        price_per_mtok_in: Optional[float] = None,
        price_per_mtok_out: Optional[float] = None,
        concurrency: int = 4,
        timeout_seconds: float = 60.0,
        max_tokens: int = 2000,
    ) -> None:
        self._name = name
        self._llm = llm
        self._model = model
        self._price_in = price_per_mtok_in
        self._price_out = price_per_mtok_out
        self._timeout = timeout_seconds
        self._max_tokens = max_tokens
        self._limit = ConcurrencyLimit(concurrency)

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_configured(self) -> bool:
        return self._llm is not None and self._llm.is_model_available(self._model)

    def _check(self, questions: Mapping[str, Question]) -> LLMProvider:
        if self._llm is None or not self.is_configured:
            raise DecisionModelNotConfiguredError(
                f"Decision model '{self._name}': no LLM provider serves '{self._model}'"
            )
        if not questions:
            raise ValueError("At least one question is required")
        return self._llm

    def _parse(
        self, response: LLMResponse, questions: Mapping[str, Question], started: float
    ) -> dict[str, Answer]:
        return parse_llm_answers(
            response.content,
            questions,
            model_name=self._name,
            latency_ms=(time.perf_counter() - started) * 1000,
            cost_usd=request_cost(
                response.tokens_in, response.tokens_out, self._price_in, self._price_out
            ),
        )

    def _kwargs(self, state: str, questions: Mapping[str, Question]) -> dict[str, Any]:
        return {
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": build_user_prompt(state, questions),
            "model": self._model,
            "temperature": 0.0,
            "max_tokens": self._max_tokens,
            "response_format": "json",
            "timeout": self._timeout,
        }

    def decide(self, state: str, questions: Mapping[str, Question]) -> dict[str, Answer]:
        llm = self._check(questions)
        with self._limit.slot():
            started = time.perf_counter()
            try:
                response = llm.complete(**self._kwargs(state, questions))
            except Exception as e:
                raise DecisionModelUnavailableError(f"{self._name}: {type(e).__name__}: {e}") from e
        return self._parse(response, questions, started)

    async def decide_async(
        self, state: str, questions: Mapping[str, Question]
    ) -> dict[str, Answer]:
        llm = self._check(questions)
        async with self._limit.async_slot():
            started = time.perf_counter()
            try:
                response = await llm.complete_async(**self._kwargs(state, questions))
            except Exception as e:
                raise DecisionModelUnavailableError(f"{self._name}: {type(e).__name__}: {e}") from e
        return self._parse(response, questions, started)

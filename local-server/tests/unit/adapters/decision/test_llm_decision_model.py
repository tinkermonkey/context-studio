"""
LLM decision-model adapter: prompt and JSON output through an LLMProvider,
answers marked calibrated=False.
"""

import asyncio
import json
import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest

from adapters.decision.llm import LLMDecisionModel
from domain.decision.exceptions import DecisionModelError, DecisionModelNotConfiguredError
from domain.decision.value_objects import (
    ChoiceAnswer,
    ChoiceQuestion,
    ScoreAnswer,
    ScoreQuestion,
    YesNoAnswer,
    YesNoQuestion,
)
from tests.fakes.fake_llm_provider import FakeLLMProvider

QUESTIONS = {
    "kind": ChoiceQuestion(instructions="Which kind?", criteria={"activity": "A", "asset": "B"}),
    "significance": ScoreQuestion(instructions="How big?", levels=["low", "mid", "high"]),
    "is_maintenance": YesNoQuestion(instructions="Routine maintenance."),
}

REPLY = {
    "kind": {"probabilities": {"activity": 0.6, "asset": 0.2, "none": 0.2}},
    "significance": {"probabilities": [0.0, 1.0, 1.0]},
    "is_maintenance": {"p_yes": 0.75},
}


def make(reply, **kwargs):
    llm = FakeLLMProvider(
        response_content=reply if isinstance(reply, str) else json.dumps(reply),
        tokens_in=1000,
        tokens_out=200,
    )
    return llm, LLMDecisionModel("llm-instance", llm=llm, model="test-model", **kwargs)


def test_answers_parse_and_are_marked_uncalibrated():
    _llm, model = make(REPLY)
    answers = model.decide("Replaced the filter.", QUESTIONS)

    kind = answers["kind"]
    assert isinstance(kind, ChoiceAnswer)
    assert kind.choice == "activity"
    assert kind.probabilities == pytest.approx({"activity": 0.6, "asset": 0.2, "none": 0.2})
    significance = answers["significance"]
    assert isinstance(significance, ScoreAnswer)
    # Normalized to sum to 1, score is the expected level
    assert significance.probabilities == pytest.approx([0.0, 0.5, 0.5])
    assert significance.score == pytest.approx(1.5)
    maintenance = answers["is_maintenance"]
    assert isinstance(maintenance, YesNoAnswer)
    assert maintenance.p_yes == 0.75
    for answer in answers.values():
        assert answer.calibrated is False
        assert answer.model == "llm-instance"


def test_requests_json_output_with_state_and_options_in_the_prompt():
    llm, model = make(REPLY)
    model.decide("Replaced the filter.", QUESTIONS)
    args = llm.last_call_args
    assert args["response_format"] == "json"
    assert args["model"] == "test-model"
    prompt = json.loads(args["user_prompt"])
    assert prompt["state"] == "Replaced the filter."
    assert list(prompt["questions"]["kind"]["options"]) == ["activity", "asset", "none"]
    assert prompt["questions"]["significance"]["levels"] == ["low", "mid", "high"]
    assert prompt["questions"]["is_maintenance"]["kind"] == "yes_no"


def test_code_fenced_reply_is_accepted():
    _llm, model = make("```json\n" + json.dumps(REPLY) + "\n```")
    assert model.decide("x", QUESTIONS)["kind"].choice == "activity"


def test_score_probabilities_keyed_by_level_name():
    reply = {**REPLY, "significance": {"probabilities": {"low": 0, "mid": 0, "high": 1}}}
    _llm, model = make(reply)
    assert model.decide("x", QUESTIONS)["significance"].score == pytest.approx(2.0)


def test_cost_uses_configured_prices_split_across_answers():
    _llm, model = make(REPLY, price_per_mtok_in=3.0, price_per_mtok_out=15.0)
    answers = model.decide("x", QUESTIONS)
    total = sum(a.cost_usd for a in answers.values())
    assert total == pytest.approx(1000 * 3.0 / 1e6 + 200 * 15.0 / 1e6)


def test_cost_is_none_without_a_price():
    _llm, model = make(REPLY)
    assert all(a.cost_usd is None for a in model.decide("x", QUESTIONS).values())


@pytest.mark.parametrize(
    "reply",
    [
        "not json",
        "[1, 2]",
        json.dumps({k: v for k, v in REPLY.items() if k != "kind"}),
        json.dumps({**REPLY, "kind": {"probabilities": {"other": 1.0}}}),
        json.dumps({**REPLY, "is_maintenance": {"p_yes": "likely"}}),
    ],
)
def test_unusable_replies_raise(reply):
    _llm, model = make(reply)
    with pytest.raises(DecisionModelError):
        model.decide("x", QUESTIONS)


def test_provider_errors_become_decision_model_errors():
    llm = FakeLLMProvider(should_fail=True)
    model = LLMDecisionModel("llm-instance", llm=llm, model="test-model")
    with pytest.raises(DecisionModelError, match="LLM provider error"):
        model.decide("x", QUESTIONS)


def test_unavailable_model_is_not_configured():
    llm = FakeLLMProvider()
    model = LLMDecisionModel("llm-instance", llm=llm, model="unknown-model")
    assert model.is_configured is False
    with pytest.raises(DecisionModelNotConfiguredError):
        model.decide("x", QUESTIONS)
    assert LLMDecisionModel("x", llm=None, model="test-model").is_configured is False


def test_decide_async():
    _llm, model = make(REPLY)
    answers = asyncio.run(model.decide_async("x", QUESTIONS))
    assert answers["is_maintenance"].p_yes == 0.75

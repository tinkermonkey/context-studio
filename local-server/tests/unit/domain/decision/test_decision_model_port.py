"""
The DecisionModel port, exercised through the fake: question kinds, the 'none'
option, and answer metadata.
"""

import asyncio
import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest

from domain.decision.exceptions import DecisionModelError, DecisionModelNotConfiguredError
from domain.decision.ports import DecisionModel
from domain.decision.value_objects import (
    NONE_OPTION,
    ChoiceAnswer,
    ChoiceQuestion,
    ScoreAnswer,
    ScoreQuestion,
    YesNoAnswer,
    YesNoQuestion,
)
from tests.fakes.fake_decision_model import FakeDecisionModel

QUESTIONS = {
    "kind": ChoiceQuestion(
        instructions="What kind of record is this?",
        criteria={"activity": "Something done", "asset": "A thing owned"},
    ),
    "significance": ScoreQuestion(
        instructions="How significant is it?", levels=["trivial", "minor", "major"]
    ),
    "is_maintenance": YesNoQuestion(instructions="This is routine maintenance."),
}


def test_choice_question_offers_none_by_default():
    options = QUESTIONS["kind"].options()
    assert list(options) == ["activity", "asset", NONE_OPTION]


def test_choice_question_can_opt_out_of_none():
    question = ChoiceQuestion(instructions="?", criteria={"a": "A", "b": "B"}, offer_none=False)
    assert list(question.options()) == ["a", "b"]


def test_choice_question_keeps_callers_own_none_description():
    question = ChoiceQuestion(instructions="?", criteria={"a": "A", NONE_OPTION: "Not a record"})
    assert question.options()[NONE_OPTION] == "Not a record"


def test_decide_returns_one_answer_of_the_matching_kind_per_question():
    model: DecisionModel = FakeDecisionModel(
        "house",
        choices={"kind": "activity"},
        scores={"significance": 2},
        p_yes={"is_maintenance": 0.8},
    )

    answers = model.decide("Replaced the furnace filter.", QUESTIONS)

    assert set(answers) == set(QUESTIONS)
    kind = answers["kind"]
    assert isinstance(kind, ChoiceAnswer)
    assert kind.choice == "activity"
    assert set(kind.probabilities) == {"activity", "asset", NONE_OPTION}
    assert sum(kind.probabilities.values()) == pytest.approx(1.0)
    significance = answers["significance"]
    assert isinstance(significance, ScoreAnswer)
    assert significance.score == 2.0
    assert len(significance.probabilities) == 3
    maintenance = answers["is_maintenance"]
    assert isinstance(maintenance, YesNoAnswer)
    assert maintenance.p_yes == 0.8


def test_every_answer_carries_instance_name_latency_cost_and_calibration():
    answers = FakeDecisionModel("house", cost_usd=0.001).decide("x", QUESTIONS)
    for answer in answers.values():
        assert answer.model == "house"
        assert answer.latency_ms >= 0
        assert answer.cost_usd == 0.001
        assert answer.calibrated is True


def test_decide_async_matches_decide():
    model = FakeDecisionModel(choices={"kind": "asset"})
    answers = asyncio.run(model.decide_async("x", QUESTIONS))
    assert answers["kind"].choice == "asset"


def test_unconfigured_instance_raises_not_configured():
    with pytest.raises(DecisionModelNotConfiguredError):
        FakeDecisionModel(configured=False).decide("x", QUESTIONS)


def test_failing_instance_raises_a_decision_model_error():
    with pytest.raises(DecisionModelError):
        FakeDecisionModel(fail=True).decide("x", QUESTIONS)


def test_score_question_needs_two_levels():
    with pytest.raises(ValueError):
        ScoreQuestion(instructions="?", levels=["only"])


def test_choice_question_needs_an_option():
    with pytest.raises(ValueError):
        ChoiceQuestion(instructions="?", criteria={}, offer_none=False)
    # 'none' alone counts as an option
    assert list(ChoiceQuestion(instructions="?", criteria={}).options()) == [NONE_OPTION]

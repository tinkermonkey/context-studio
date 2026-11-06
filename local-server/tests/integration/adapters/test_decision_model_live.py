"""
Opt-in live call to a configured decision-model instance (one request).

Skipped unless both are given:
    pytest -m external_network tests/integration/adapters/test_decision_model_live.py \
        --decision-model-config /path/to/config.json [--decision-model-instance clef-flash]

Credentials are read from that config.json only; nothing is printed or recorded.
"""

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from adapters.decision.registry import build_decision_models
from config import DecisionModelsConfig
from domain.decision.value_objects import (
    NONE_OPTION,
    ChoiceAnswer,
    ChoiceQuestion,
    ScoreAnswer,
    ScoreQuestion,
    YesNoAnswer,
    YesNoQuestion,
)

pytestmark = pytest.mark.external_network


@pytest.fixture()
def live_model(request):
    path = request.config.getoption("--decision-model-config")
    if not path:
        pytest.skip("pass --decision-model-config to run the live decision-model test")
    with open(path) as f:
        section = json.load(f).get("decision_models") or {}
    registry = build_decision_models(DecisionModelsConfig(**section))
    name = request.config.getoption("--decision-model-instance")
    model = registry.get(name)
    if not model.is_configured:
        pytest.skip(f"decision model '{name}' is not configured in {path}")
    return model


def test_live_call_answers_every_question_kind(live_model, request):
    requested = request.config.getoption("--decision-model-instance")
    questions = {
        "kind": ChoiceQuestion(
            instructions="What kind of house record does this text describe?",
            criteria={
                "activity": "Something a person did at the house",
                "asset": "A physical thing the house contains",
                "issue": "A problem with the house",
            },
        ),
        "significance": ScoreQuestion(
            instructions="How significant is this event for the upkeep of the house?",
            levels=["trivial", "minor", "moderate", "major"],
        ),
        "is_maintenance": YesNoQuestion(instructions="This text describes routine maintenance."),
    }

    answers = live_model.decide(
        "Austin replaced the furnace filter in the basement on Saturday morning.", questions
    )

    kind = answers["kind"]
    assert isinstance(kind, ChoiceAnswer)
    assert kind.choice in {"activity", "asset", "issue", NONE_OPTION}
    assert set(kind.probabilities) == {"activity", "asset", "issue", NONE_OPTION}
    significance = answers["significance"]
    assert isinstance(significance, ScoreAnswer)
    assert significance.score is not None and 0 <= significance.score <= 3
    assert len(significance.probabilities) == 4
    maintenance = answers["is_maintenance"]
    assert isinstance(maintenance, YesNoAnswer)
    assert maintenance.p_yes is not None and 0 <= maintenance.p_yes <= 1
    for answer in answers.values():
        # The requested instance answered itself, not a fallback
        assert answer.model == requested
        assert answer.latency_ms > 0

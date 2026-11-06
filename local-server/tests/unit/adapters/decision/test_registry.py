"""
Decision-model registry built from config: lookup by name or default, swapping
the default in config, fallbacks, and listing without credentials.
"""

import logging
import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest
from pydantic import ValidationError

from adapters.decision.llm import LLMDecisionModel
from adapters.decision.registry import build_decision_models
from adapters.decision.workers_ai import WorkersAIDecisionModel
from config import DecisionModelsConfig, Settings
from domain.decision.exceptions import (
    DecisionModelError,
    DecisionModelNotConfiguredError,
    DecisionModelRequestError,
    UnknownDecisionModelError,
)
from domain.decision.value_objects import ChoiceQuestion
from tests.fakes.fake_decision_model import FakeDecisionModel
from tests.fakes.fake_llm_provider import FakeLLMProvider

QUESTIONS = {"kind": ChoiceQuestion(instructions="?", criteria={"a": "A", "b": "B"})}


def config_with_default(default: str) -> DecisionModelsConfig:
    """The decision_models section as config.json would hold it."""
    return Settings(
        **{
            "decision_models": {
                "default": default,
                "models": {
                    "primary": {
                        "adapter": "workers_ai",
                        "model": "@cf/vendor/model-large",
                        "price_per_mtok_in": 0.24,
                        "options": {"account_id": "acct-secret-id", "api_token": "token-secret"},
                    },
                    "light": {
                        "adapter": "workers_ai",
                        "model": "@cf/vendor/model-small",
                        "options": {"account_id": "acct-secret-id", "api_token": "token-secret"},
                    },
                    "llm": {"adapter": "llm", "model": "test-model"},
                },
            }
        }
    ).decision_models


def test_config_section_parses_into_settings():
    config = config_with_default("primary")
    assert config.default == "primary"
    assert config.models["primary"].adapter == "workers_ai"
    assert config.models["primary"].concurrency == 4
    assert config.models["light"].price_per_mtok_in is None


def test_missing_section_means_no_instances():
    assert Settings().decision_models.models == {}


def test_instances_are_built_by_adapter():
    registry = build_decision_models(config_with_default("primary"), FakeLLMProvider())
    assert isinstance(registry.get("primary"), WorkersAIDecisionModel)
    assert isinstance(registry.get("llm"), LLMDecisionModel)


@pytest.mark.parametrize("default", ["primary", "light", "llm"])
def test_swapping_the_default_in_config_changes_the_instance(default):
    registry = build_decision_models(config_with_default(default), FakeLLMProvider())
    assert registry.get().name == default
    assert registry.default_name == default


def test_unknown_name_and_missing_default_raise():
    registry = build_decision_models(config_with_default("nope"), FakeLLMProvider())
    with pytest.raises(UnknownDecisionModelError):
        registry.get()
    with pytest.raises(UnknownDecisionModelError):
        registry.get("missing")


def test_unknown_adapter_is_listed_unconfigured_and_raises_on_use():
    config = DecisionModelsConfig(models={"odd": {"adapter": "carrier_pigeon", "model": "m"}})
    registry = build_decision_models(config)
    (info,) = registry.describe()
    assert info.configured is False
    with pytest.raises(DecisionModelNotConfiguredError):
        registry.get("odd").decide("x", QUESTIONS)


def test_describe_lists_instances_without_credentials():
    registry = build_decision_models(config_with_default("primary"), FakeLLMProvider())
    infos = {info.name: info for info in registry.describe()}

    assert set(infos) == {"primary", "light", "llm"}
    assert infos["primary"].is_default is True
    assert infos["primary"].configured is True
    assert infos["primary"].model == "@cf/vendor/model-large"
    assert infos["llm"].configured is True
    assert "secret" not in repr(registry.describe())


def test_workers_ai_without_credentials_is_unconfigured():
    config = DecisionModelsConfig(models={"cf": {"adapter": "workers_ai", "model": "@cf/vendor/m"}})
    (info,) = build_decision_models(config).describe()
    assert info.configured is False


# ---- fallbacks ----


def fallback_registry(primary: FakeDecisionModel, backup: FakeDecisionModel):
    config = DecisionModelsConfig(
        default="primary",
        models={
            "primary": {"adapter": "fake-primary", "model": "m", "fallback": "backup"},
            "backup": {"adapter": "fake-backup", "model": "m"},
        },
    )
    builders = {"fake-primary": lambda _n, _c: primary, "fake-backup": lambda _n, _c: backup}
    return build_decision_models(config, builders=builders)


def test_fallback_answers_when_primary_is_unconfigured():
    primary = FakeDecisionModel("primary", configured=False)
    backup = FakeDecisionModel("backup", choices={"kind": "b"})
    model = fallback_registry(primary, backup).get()

    answers = model.decide("x", QUESTIONS)

    assert model.name == "primary"
    assert model.is_configured is True
    assert answers["kind"].model == "backup"
    assert primary.calls == []


def test_fallback_answers_when_primary_errors():
    primary = FakeDecisionModel("primary", fail=True)
    backup = FakeDecisionModel("backup")
    answers = fallback_registry(primary, backup).get().decide("x", QUESTIONS)
    assert answers["kind"].model == "backup"
    assert len(primary.calls) == 1


@pytest.mark.parametrize(
    "error",
    [DecisionModelRequestError("HTTP 401: revoked token"), DecisionModelError("unusable reply")],
)
def test_request_errors_and_unusable_replies_do_not_fall_back(error):
    primary = FakeDecisionModel("primary", error=error)
    backup = FakeDecisionModel("backup")
    with pytest.raises(type(error)):
        fallback_registry(primary, backup).get().decide("x", QUESTIONS)
    assert backup.calls == []


def test_invalid_adapter_options_leave_the_instance_unconfigured():
    config = DecisionModelsConfig(
        models={"cf": {"adapter": "workers_ai", "model": "m", "options": {"account_id": 42}}}
    )
    registry = build_decision_models(config)
    assert registry.describe()[0].configured is False
    with pytest.raises(DecisionModelNotConfiguredError):
        registry.get("cf").decide("x", QUESTIONS)


def test_old_flat_credentials_are_not_read():
    # Credentials belong under options; flat ones are ignored, so the instance is unconfigured
    config = DecisionModelsConfig(
        models={"cf": {"adapter": "workers_ai", "model": "m", "account_id": "a", "api_token": "t"}}
    )
    assert build_decision_models(config).describe()[0].configured is False


def test_primary_answers_when_healthy():
    primary = FakeDecisionModel("primary")
    backup = FakeDecisionModel("backup")
    answers = fallback_registry(primary, backup).get().decide("x", QUESTIONS)
    assert answers["kind"].model == "primary"
    assert backup.calls == []


async def test_fallback_async():
    primary = FakeDecisionModel("primary", fail=True)
    backup = FakeDecisionModel("backup")
    answers = await fallback_registry(primary, backup).get().decide_async("x", QUESTIONS)
    assert answers["kind"].model == "backup"


def test_describe_reports_each_instance_own_configured_flag():
    primary = FakeDecisionModel("primary", configured=False)
    backup = FakeDecisionModel("backup")
    infos = {i.name: i for i in fallback_registry(primary, backup).describe()}
    assert infos["primary"].configured is False
    assert infos["primary"].fallback == "backup"


def test_fallback_loops_and_missing_fallbacks_are_ignored():
    config = DecisionModelsConfig(
        models={
            "a": {"adapter": "fake", "model": "m", "fallback": "b"},
            "b": {"adapter": "fake", "model": "m", "fallback": "a"},
            "c": {"adapter": "fake", "model": "m", "fallback": "missing"},
        }
    )
    built: dict[str, FakeDecisionModel] = {}

    def builder(name, _cfg):
        built[name] = FakeDecisionModel(name, fail=True)
        return built[name]

    registry = build_decision_models(config, builders={"fake": builder})
    # a -> b -> (a again: stop); both fail, so the error surfaces instead of looping
    with pytest.raises(Exception):
        registry.get("a").decide("x", QUESTIONS)
    assert len(built["a"].calls) == 1
    assert len(built["b"].calls) == 1
    assert registry.get("c") is built["c"]


# ---- secrets stay out of logs and errors ----

TOKEN = "tok-DO-NOT-LEAK-9f8e7d"


def test_invalid_options_never_put_the_token_in_logs_or_errors(caplog):
    # base_url has the wrong type, so options fail validation with the token beside it
    config = DecisionModelsConfig(
        models={
            "cf": {
                "adapter": "workers_ai",
                "model": "m",
                "options": {"account_id": TOKEN, "api_token": TOKEN, "base_url": {"x": TOKEN}},
            }
        }
    )
    with caplog.at_level(logging.DEBUG):
        registry = build_decision_models(config)
        with pytest.raises(DecisionModelNotConfiguredError) as raised:
            registry.get("cf").decide("x", QUESTIONS)

    assert "base_url" in str(raised.value)
    assert TOKEN not in str(raised.value)
    assert TOKEN not in caplog.text
    assert "invalid options" in caplog.text


def test_invalid_instance_config_never_echoes_the_token():
    # 'model' is missing: the error's input would be the whole instance, options included
    bad = {"models": {"cf": {"adapter": "workers_ai", "options": {"api_token": TOKEN}}}}
    with pytest.raises(ValidationError) as raised:
        DecisionModelsConfig(**bad)
    assert TOKEN not in str(raised.value)
    with pytest.raises(ValidationError) as raised:
        Settings(decision_models=bad)
    assert TOKEN not in str(raised.value)


def test_unknown_keys_are_named_without_their_values(caplog):
    # The old flat shape, plus a typo inside options
    config = DecisionModelsConfig(
        models={
            "cf": {
                "adapter": "workers_ai",
                "model": "m",
                "api_token": TOKEN,
                "options": {"account_id": "a", "api_tokn": TOKEN},
            }
        }
    )
    with caplog.at_level(logging.WARNING):
        build_decision_models(config)
    assert "unknown keys api_token" in caplog.text
    assert "unknown options api_tokn" in caplog.text
    assert TOKEN not in caplog.text

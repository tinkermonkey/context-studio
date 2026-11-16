"""
Unit tests: the one rule by which every orchestrator takes the model,
temperature and output-token limit of an LLM call
(domain/pipelines/orchestration/base.py): what the run's input names, then
what the configuration the orchestrator was built with names. No orchestrator
has a model of its own.
"""

import pytest

from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.individual_extraction.configurations.open_v1 import (
    IndividualOpenV1Config,
)
from domain.pipelines.individual_extraction.configurations.open_v1 import (
    get_open_v1_config as individual_open_v1_config,
)
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)
from domain.pipelines.orchestration.base import implementation_settings, llm_parameters
from domain.pipelines.ports import LLMResponse
from domain.pipelines.schema_extraction.configurations.open_v1 import (
    SchemaOpenV1Config,
)
from domain.pipelines.schema_extraction.configurations.open_v1 import (
    get_open_v1_config as schema_open_v1_config,
)
from domain.pipelines.schema_extraction.open_orchestrator import (
    OpenSchemaExtractionOrchestrator,
)

CONFIG = {"model": "configured", "temperature": 0.2, "max_tokens": 3000}


class TestTheRule:
    def test_the_runs_input_wins(self):
        named = {"model": "named", "temperature": 0.9, "max_tokens": 500}

        assert llm_parameters(named, CONFIG, 2000) == named

    def test_what_the_input_leaves_out_is_the_configurations(self):
        assert llm_parameters({"text": "t"}, CONFIG, 2000) == CONFIG

    def test_each_parameter_is_taken_on_its_own(self):
        assert llm_parameters({"max_tokens": 700}, CONFIG, 2000) == {**CONFIG, "max_tokens": 700}

    def test_a_temperature_of_zero_in_the_input_is_a_temperature(self):
        assert llm_parameters({"temperature": 0.0}, CONFIG, 2000)["temperature"] == 0.0

    def test_no_limit_named_is_the_stages_own(self):
        assert llm_parameters({"model": "m"}, {}, 2000) == {
            "model": "m",
            "temperature": 0.0,
            "max_tokens": 2000,
        }

    def test_no_limit_named_and_none_of_the_stages_is_none(self):
        assert llm_parameters({"model": "m"}, None)["max_tokens"] is None

    @pytest.mark.parametrize("input_data, config", [({}, {}), ({"model": ""}, None)])
    def test_no_model_named_is_an_input_error(self, input_data, config):
        with pytest.raises(PipelineInputError, match="model is required"):
            llm_parameters(input_data, config, 2000)


class TestNoModelOfTheirOwn:
    def test_implementation_settings_carry_no_run_parameters(self):
        settings = implementation_settings({**CONFIG, "top_n": 8, "sources": ["DBpedia"]})

        assert settings == {"top_n": 8, "sources": ["DBpedia"]}

    @pytest.mark.parametrize("parser", [IndividualOpenV1Config, SchemaOpenV1Config])
    def test_a_configuration_that_names_no_model_parses_to_none(self, parser):
        assert parser.from_dict({}).model == ""

    @pytest.mark.parametrize(
        "parser, registered",
        [
            (IndividualOpenV1Config, individual_open_v1_config),
            (SchemaOpenV1Config, schema_open_v1_config),
        ],
    )
    def test_the_registered_configuration_names_its_model(self, parser, registered):
        assert parser.from_dict(registered()).model == registered()["model"] != ""


class RecordingLLM:
    """Answers every call with the same body and records what each was asked to use."""

    def __init__(self, body: str = "{}") -> None:
        self._body = body
        self.calls: list[dict] = []

    async def complete_async(self, **request):
        self.calls.append(request)
        return LLMResponse(
            content=self._body,
            tokens_in=1,
            tokens_out=1,
            duration_ms=1.0,
            finish_reason="stop",
            model=request["model"],
        )

    def parameters(self) -> list[tuple]:
        return [(c["model"], c["temperature"], c["max_tokens"]) for c in self.calls]


def _open_individual(llm, config):
    return OpenIndividualExtractionOrchestrator(
        llm_provider=llm,
        nlp_processor=None,
        embedding_service=None,
        schema_index=None,
        config=config,
    )


def _open_schema(llm, config):
    return OpenSchemaExtractionOrchestrator(
        llm_provider=llm, nlp_processor=None, embedding_service=None, clusterer=None, config=config
    )


class TestOpenV1TakesTheRunsParameters:
    """open_v1's LLM calls follow the rule; they used to read the configuration only."""

    async def test_individual_open_v1_uses_what_the_runs_input_names(self):
        llm = RecordingLLM()
        orchestrator = _open_individual(llm, individual_open_v1_config())
        orchestrator._run_input = {"model": "named", "temperature": 0.4, "max_tokens": 700}

        await orchestrator._request_canonical_labels({"gateway": "Service"}, "The gateway.")

        assert llm.parameters() == [("named", 0.4, 700)]

    async def test_individual_open_v1_uses_its_configurations_otherwise(self):
        llm = RecordingLLM()
        config = individual_open_v1_config()

        await _open_individual(llm, config)._request_canonical_labels(
            {"gateway": "Service"}, "The gateway."
        )

        assert llm.parameters() == [(config["model"], config["temperature"], config["max_tokens"])]

    async def test_individual_open_v1_built_with_no_configuration_has_no_model_to_call(self):
        llm = RecordingLLM()

        # Canonicalization is best-effort: without a model it asks nothing
        mapping = await _open_individual(llm, None)._request_canonical_labels(
            {"gateway": "Service"}, "The gateway."
        )

        assert llm.calls == []
        assert mapping == {}

    async def test_schema_open_v1_uses_what_the_runs_input_names(self):
        llm = RecordingLLM()
        orchestrator = _open_schema(llm, schema_open_v1_config())
        orchestrator._run_input = {"model": "named", "max_tokens": 900}

        await orchestrator._llm_definitions(["Gateway"], "The gateway routes requests.")

        assert llm.parameters() == [("named", 0.0, 900)]

    async def test_schema_open_v1_uses_its_configurations_otherwise(self):
        llm = RecordingLLM()
        config = schema_open_v1_config()

        await _open_schema(llm, config)._llm_definitions(
            ["Gateway"], "The gateway routes requests."
        )

        assert llm.parameters() == [(config["model"], config["temperature"], config["max_tokens"])]
